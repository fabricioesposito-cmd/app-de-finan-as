"""Owner-scoped Web Push, with the exact same budget model as the dashboard."""
import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from urllib.parse import urlsplit, quote
from uuid import UUID
from zoneinfo import ZoneInfo
from app import supabase
from app.snapshot import snapshot, prepare_snapshot

ZONE=ZoneInfo('America/Sao_Paulo')


def configured():
    return bool(os.environ.get('VAPID_PRIVATE_KEY') and os.environ.get('VAPID_PUBLIC_KEY') and os.environ.get('PUSH_JOB_SECRET'))


def validate_subscription(value):
    try:
        endpoint=value['endpoint']
        url=urlsplit(endpoint)
        host=url.hostname or ''
        allowed=(host in ('fcm.googleapis.com','updates.push.services.mozilla.com') or host.endswith('.push.apple.com') or host.endswith('.notify.windows.com'))
        if not allowed or url.scheme!='https' or url.port not in (None,443) or url.username or url.password or url.fragment or len(endpoint)>4096:
            raise ValueError()
        keys={}
        for key,size in [('p256dh',65),('auth',16)]:
            text=value['keys'][key]
            if not isinstance(text,str) or len(text)>100:raise ValueError()
            decoded=base64.b64decode(text+'='*((-len(text))%4),altchars=b'-_',validate=True)
            if len(decoded)!=size or (key=='p256dh' and decoded[0]!=4):raise ValueError()
            keys[key]=text
        return {'endpoint':endpoint,'keys':keys}
    except (KeyError,TypeError,ValueError):
        raise ValueError('Inscrição de notificações inválida. Ative novamente neste aparelho.') from None


def settings(token):
    rows=supabase.request('/rest/v1/push_subscriptions?select=id,endpoint,enabled,hour,last_sent_at&order=created_at',token=token)
    return {'configured':configured(),'public_key':os.environ.get('VAPID_PUBLIC_KEY',''),'timezone':'America/Sao_Paulo','subscriptions':rows}


def save_subscription(data,token):
    if not configured():raise ValueError('As notificações ainda não estão disponíveis no servidor.')
    subscription=validate_subscription(data.get('subscription'))
    hour=int(data.get('hour',9))
    if not 0<=hour<=23:raise ValueError('Escolha um horário entre 0 e 23 horas.')
    return supabase.request('/rest/v1/rpc/save_push_subscription','POST',{'p_endpoint':subscription['endpoint'],'p_keys':subscription['keys'],'p_hour':hour},token)


def disable_subscription(data,token):
    key=str(UUID(data['id']))
    supabase.request('/rest/v1/push_subscriptions?id=eq.'+key,'PATCH',{'enabled':False},token)


def brl(cents):
    whole,fraction=divmod(abs(int(cents)),100)
    return ('-' if cents<0 else '')+'R$ '+f'{whole:,}'.replace(',','.')+f',{fraction:02d}'


def notification(finance,day,test=False):
    month=finance['month']
    names=['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']
    label=names[int(month[5:])-1]+' de '+month[:4]
    if finance['deficit_cents']:
        body='Seu orçamento de '+label+' está excedido em '+brl(finance['deficit_cents'])+'.'
    else:
        body='Disponível para gastar em '+label+': '+brl(finance['remaining_cents'])+'.'
    body+=' Compromissos, gastos e reserva já considerados. Conforme seus registros.'
    return {'title':'Clareza · '+('Teste de notificação' if test else 'Seu resumo diário'),'body':body,'tag':'clareza-'+('test' if test else day),'url':'/','icon':'/icon-192.png'}


def send_push(subscription,payload):
    # Revalidate even for database-originated jobs: never POST to arbitrary URLs.
    subscription=validate_subscription(subscription)
    from pywebpush import webpush, WebPushException
    try:
        response=webpush(subscription_info=subscription,data=json.dumps(payload,ensure_ascii=False),vapid_private_key=os.environ['VAPID_PRIVATE_KEY'],vapid_claims={'sub':os.environ.get('VAPID_SUBJECT','https://clareza-financas.onrender.com')},ttl=3600,timeout=15)
        return 'sent' if 200<=response.status_code<300 else 'retry'
    except WebPushException as error:
        status=error.response.status_code if error.response is not None else None
        return 'expired' if status in (404,410) else 'retry'
    except Exception:
        # Never return endpoint, auth keys or personal payload in errors/logs.
        return 'retry'


def test_push(data,token):
    key=str(UUID(data['id']))
    rows=supabase.request('/rest/v1/push_subscriptions?id=eq.'+key+'&enabled=eq.true',token=token)
    if not rows:raise ValueError('Ative as notificações neste aparelho primeiro.')
    row=rows[0]
    # Atomic owner-scoped rate limit survives server restarts.
    allowed=supabase.request('/rest/v1/rpc/claim_push_test','POST',{'p_id':key},token)
    if not allowed:raise ValueError('Aguarde um minuto antes de enviar outro teste.')
    now=datetime.now(ZONE)
    finance=snapshot(token,now.strftime('%Y-%m'))['finance']
    status=send_push({'endpoint':row['endpoint'],'keys':row['keys']},notification(finance,now.date().isoformat(),True))
    if status=='expired':
        disable_subscription({'id':key},token)
        raise ValueError('A permissão deste aparelho expirou. Ative novamente.')
    if status!='sent':raise ValueError('Não foi possível enviar o teste. Tente novamente em instantes.')
    return {'ok':True}


def daily_job(body,signature):
    secret=os.environ.get('PUSH_JOB_SECRET','')
    if not secret or not hmac.compare_digest(hmac.new(secret.encode(),body,hashlib.sha256).hexdigest(),signature or ''):
        return {'error':'Não autorizado.'},401
    try:
        data=json.loads(body)
        if abs(time.time()-float(data['sent_at']))>300:return {'error':'Requisição expirada.'},401
        now=datetime.now(ZONE)
        if data['day']!=now.date().isoformat():return {'error':'Dia inválido.'},400
        finance=prepare_snapshot(data['data'],now.strftime('%Y-%m'))['finance']
        status=send_push(data['subscription'],notification(finance,data['day']))
        return {'ok':status in ('sent','expired'),'status':status},200 if status in ('sent','expired') else 503
    except (KeyError,TypeError,ValueError):
        return {'error':'Dados de notificação inválidos.'},400
