import base64
import copy
import hashlib
import hmac
import json
import os
import time
import unittest
from datetime import datetime
from unittest.mock import patch,Mock
from app import notifications as push
from app.snapshot import prepare_snapshot
from tests import test_production


def subscription(endpoint='https://web.push.apple.com/example'):
    enc=lambda v:base64.urlsafe_b64encode(v).decode().rstrip('=')
    return {'endpoint':endpoint,'keys':{'p256dh':enc(b'\x04'+b'a'*64),'auth':enc(b'b'*16)}}


class PushTests(unittest.TestCase):
    def test_subscription_only_accepts_known_https_push_hosts_and_keys(self):
        self.assertEqual(push.validate_subscription(subscription()),subscription())
        for url in ['http://web.push.apple.com/a','https://web.push.apple.com.evil.test/a','https://localhost/a','https://127.0.0.1/a','https://user@web.push.apple.com/a','https://web.push.apple.com:444/a']:
            with self.assertRaises(ValueError):push.validate_subscription(subscription(url))
        value=subscription();value['keys']['auth']='short'
        with self.assertRaises(ValueError):push.validate_subscription(value)

    def test_signed_job_rejects_unsigned_stale_and_changed_payload_before_sending(self):
        with patch.dict(os.environ,{'PUSH_JOB_SECRET':'fixture-secret'}),patch.object(push,'send_push') as send:
            self.assertEqual(push.daily_job(b'{}','')[1],401)
            raw=json.dumps({'sent_at':time.time()-600}).encode();signature=hmac.new(b'fixture-secret',raw,hashlib.sha256).hexdigest()
            self.assertEqual(push.daily_job(raw,signature)[1],401)
            self.assertEqual(push.daily_job(raw+b' ',signature)[1],401)
            send.assert_not_called()

    def test_start_month_is_validated_saved_and_preserved_for_old_clients(self):
        with patch.object(push,'configured',return_value=True),patch.object(push.supabase,'request',return_value='fixture') as request:
            push.save_subscription({'subscription':subscription(),'hour':9,'start_month':'2026-12'},'fixture-token')
            self.assertEqual(request.call_args.args[2]['p_start_month'],'2026-12')
            push.save_subscription({'subscription':subscription(),'reference_month':'2026-10','start_month':'2026-12'},'fixture-token')
            self.assertEqual(request.call_args.args[2]['p_start_month'],'2026-10')
            for month in ['', '2026-13', '0000-01', None]:
                with self.assertRaises(ValueError):push.save_subscription({'subscription':subscription(),'start_month':month},'fixture-token')
            push.save_subscription({'subscription':subscription(),'hour':10},'fixture-token')
            self.assertNotIn('p_start_month',request.call_args.args[2])

    def test_selected_past_and_future_months_are_sent_on_consecutive_days(self):
        from datetime import timedelta
        from app.recurrence import add_month
        now=datetime.now(push.ZONE)
        names=['cards','imports','budgets','entries','cash_items','monthly_plans','card_settlements','accounts','recurring_rules','recurrence_states','card_events','entry_matches','investor_profiles','savings_schedules']
        for offset in (-1,1):
            month=add_month(now.strftime('%Y-%m'),offset)
            data={name:[] for name in names}
            data['cash_items']=[{'id':'chosen-income','description':'Chosen salary','kind':'income','category':'Salário','amount_cents':500000,'due_date':month+'-01','settled':True},{'id':'chosen-cost','description':'Chosen cost','kind':'expense','category':'Mercado','amount_cents':10000,'due_date':month+'-02','settled':True},{'id':'other-income','description':'Current month','kind':'income','category':'Salário','amount_cents':900000,'due_date':now.strftime('%Y-%m')+'-01','settled':True}]
            data['monthly_plans']=[{'month':month,'opening_cents':0,'savings_target_cents':100000,'saved_cents':0,'savings_override':True}]
            expected=prepare_snapshot(copy.deepcopy(data),month)['finance']
            self.assertEqual(expected['remaining_cents'],390000)
            for step in (0,1):
                day=(now+timedelta(days=step)).date().isoformat()
                raw=json.dumps({'sent_at':time.time(),'day':day,('reference_month' if step==0 else 'start_month'):month,'data':data,'subscription':subscription()}).encode()
                signature=hmac.new(b'fixture-secret',raw,hashlib.sha256).hexdigest()
                with patch.dict(os.environ,{'PUSH_JOB_SECRET':'fixture-secret'}),patch.object(push,'datetime') as clock,patch.object(push,'send_push',return_value='sent') as send:
                    clock.now.return_value=now+timedelta(days=step)
                    result,status=push.daily_job(raw,signature)
                self.assertEqual((result,status),({'ok':True,'status':'sent'},200))
                self.assertEqual(send.call_args.args[1],push.notification(expected,day))

    def test_manual_test_uses_the_exact_selected_month(self):
        for month in ['2000-01','2099-01']:
            row={'id':'00000000-0000-4000-8000-000000000001',**subscription(),'start_month':month}
            with patch.object(push.supabase,'request',side_effect=[[row],True]),patch.object(push,'snapshot',return_value={'finance':{'month':month,'remaining_cents':1000,'deficit_cents':0}}) as snapshot,patch.object(push,'send_push',return_value='sent'):
                self.assertTrue(push.test_push({'id':row['id']},'fixture-token')['ok'])
            self.assertEqual(snapshot.call_args.args[1],month)

    def test_notification_deficit_and_zero_are_not_misrepresented_as_available(self):
        data={'month':'2026-12','remaining_cents':432712,'deficit_cents':0}
        result=push.notification(data,'2026-12-01')
        self.assertIn('R$ 4.327,12',result['body']);self.assertIn('dezembro de 2026',result['body'])
        self.assertIn('reserva',result['body']);self.assertIn('Conforme seus registros',result['body'])
        result=push.notification(dict(data,remaining_cents=0,deficit_cents=1000),'2026-12-01')
        self.assertIn('excedido em R$ 10,00',result['body']);self.assertNotIn('Disponível',result['body'])

    def test_worker_uses_canonical_dashboard_calculation_and_current_brasilia_month(self):
        names=['cards','imports','budgets','entries','cash_items','monthly_plans','card_settlements','accounts','recurring_rules','recurrence_states','card_events','entry_matches','investor_profiles','savings_schedules']
        data={key:[] for key in names}
        month=datetime.now(push.ZONE).strftime('%Y-%m');day=datetime.now(push.ZONE).date().isoformat()
        data['cash_items']=[{'id':'income','description':'Salary','kind':'income','category':'Salário','amount_cents':500000,'due_date':month+'-01','settled':True},{'id':'cost','description':'Market','kind':'expense','category':'Mercado','amount_cents':10000,'due_date':month+'-02','settled':True}]
        data['monthly_plans']=[{'month':month,'opening_cents':0,'savings_target_cents':100000,'saved_cents':0,'savings_override':True}]
        expected=prepare_snapshot(copy.deepcopy(data),month)['finance'];self.assertEqual(expected['remaining_cents'],390000)
        raw=json.dumps({'sent_at':time.time(),'day':day,'data':data,'subscription':subscription()}).encode()
        signature=hmac.new(b'fixture-secret',raw,hashlib.sha256).hexdigest()
        with patch.dict(os.environ,{'PUSH_JOB_SECRET':'fixture-secret'}),patch.object(push,'send_push',return_value='sent') as send:
            result,status=push.daily_job(raw,signature)
        self.assertEqual(status,200);self.assertEqual(result['status'],'sent')
        self.assertEqual(send.call_args.args[1],push.notification(expected,day))

    def test_real_encryption_and_vapid_round_trip_without_network(self):
        import secrets
        import http_ece
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        enc=lambda v:base64.urlsafe_b64encode(v).decode().rstrip('=')
        receiver=ec.generate_private_key(ec.SECP256R1());sender=ec.generate_private_key(ec.SECP256R1());auth=secrets.token_bytes(16)
        value=subscription();value['keys']={'p256dh':enc(receiver.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)),'auth':enc(auth)}
        key=enc(sender.private_numbers().private_value.to_bytes(32,'big'))
        payload={'title':'Clareza','body':'Disponível: R$ 42,00'}
        with patch.dict(os.environ,{'VAPID_PRIVATE_KEY':key}),patch('pywebpush.requests.post',return_value=Mock(status_code=201)) as post:
            self.assertEqual(push.send_push(value,payload),'sent')
        sent=post.call_args.kwargs
        self.assertEqual(json.loads(http_ece.decrypt(sent['data'],private_key=receiver,auth_secret=auth,version='aes128gcm')),payload)
        self.assertTrue(sent['headers']['Authorization'].startswith('vapid '))

    def test_expired_push_is_removed_and_transient_failure_is_retried(self):
        from pywebpush import WebPushException
        for code,expected in [(410,'expired'),(404,'expired'),(429,'retry'),(503,'retry')]:
            response=Mock(status_code=code)
            with patch.dict(os.environ,{'VAPID_PRIVATE_KEY':'fixture-key'}),patch('pywebpush.webpush',side_effect=WebPushException('failure',response=response)):
                self.assertEqual(push.send_push(subscription(),{'body':'fixture'}),expected)


class PushRouteTests(unittest.TestCase):
    call=test_production.WSGITests.call
    def test_push_static_assets_and_worker_auth_gate(self):
        response,body=self.call('/push-sw.js');self.assertEqual(response['status'],'200 OK');self.assertIn(b'showNotification',body)
        response,body=self.call('/notifications.js');self.assertEqual(response['status'],'200 OK')
        response,body=self.call('/api/push/settings');self.assertTrue(response['status'].startswith('401'))
        with patch.dict(os.environ,{'PUSH_JOB_SECRET':'fixture-secret'}):
            response,body=self.call('/api/push/daily','POST',b'{}')
        self.assertTrue(response['status'].startswith('401'))
