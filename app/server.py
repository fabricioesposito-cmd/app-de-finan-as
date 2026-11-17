import csv
import hashlib
import io
import json
import os
import secrets
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote
from app import supabase
from app.domain import CATEGORIES, cents, parse_csv
from app.pdf_import import parse_pdf

ROOT = Path(__file__).resolve().parent.parent
SESSIONS = {}
TOKEN = secrets.token_urlsafe(32)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def session(self):
        cookie = SimpleCookie(self.headers.get('Cookie', ''))
        sid = cookie.get('finance_session')
        session = SESSIONS.get(sid.value) if sid else None
        return session if session and session['expires'] > time.time() else None

    def send(self, data, status=200, mime='application/json', cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode() if mime == 'application/json' else data
        self.send_response(status)
        headers = {'Content-Type':mime+('' if mime=='application/pdf' else '; charset=utf-8'),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'",'Referrer-Policy':'no-referrer'}
        for key,value in headers.items(): self.send_header(key,value)
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            if self.path == '/api/state':
                session = self.session()
                if not session:
                    self.send(dict(authenticated=False,token=TOKEN)); return
                def get(table): return supabase.all_rows('/rest/v1/'+table+'?select=*&order='+('user_id,description' if table=='category_rules' else 'id'),token=session['token'])
                entries = [dict(row['payload'],id=row['id'],import_id=row['import_id']) for row in get('entries')]
                self.send(dict(authenticated=True,email=session['email'],cards=get('cards'),imports=get('imports'),entries=entries,budgets=get('budgets'),categories=CATEGORIES,token=TOKEN))
            elif self.path == '/api/export':
                session = self.session()
                if not session:
                    self.send({'error':'Entre na sua conta.'},401); return
                rows=supabase.all_rows('/rest/v1/entries?select=payload,imports(month,cards(name))&order=id',token=session['token'])
                out=io.StringIO(); writer=csv.writer(out,delimiter=';')
                writer.writerow(['data','descricao','valor','categoria','mes_fatura','cartao'])
                def safe(value):
                    value=str(value)
                    return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value
                for row in rows:
                    e=row['payload']; amount=e['amount']
                    value=('-' if amount<0 else '')+str(abs(amount)//100)+','+str(abs(amount)%100).zfill(2)
                    writer.writerow([e['date'],safe(e['description']),value,safe(e['category']),row['imports']['month'],safe(row['imports']['cards']['name'])])
                self.send(out.getvalue().encode('utf-8-sig'),mime='text/csv')
            else:
                files={'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css'),'/modelo.csv':('../examples/fatura.csv','text/csv'),'/modelo.pdf':('../examples/fatura-ficticia.pdf','application/pdf')}
                if self.path not in files:
                    self.send({'error':'Não encontrado'},404); return
                name,mime=files[self.path]
                self.send((ROOT/'static'/name).read_bytes(),mime=mime)
        except ValueError as error:
            self.send({'error':str(error)},400)

    def do_POST(self):
        if self.headers.get('X-App-Token') != TOKEN:
            self.send({'error':'Atualize a página para continuar.'},403); return
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=5_000_000: raise ValueError('Envie um arquivo de até 5 MB.')
            body=self.rfile.read(size)
            session=self.session()
            if self.path in ['/api/login','/api/signup']:
                data=json.loads(body)
                path='/auth/v1/token?grant_type=password' if self.path=='/api/login' else '/auth/v1/signup'
                auth=supabase.request(path,'POST',{'email':data['email'],'password':data['password']})
                if not auth.get('access_token'):
                    self.send({'ok':True,'message':'Confira seu e-mail para confirmar o cadastro. Depois entre com sua senha.'}); return
                sid=secrets.token_urlsafe(32)
                SESSIONS[sid]={'token':auth['access_token'],'email':auth['user']['email'],'expires':time.time()+auth['expires_in']}
                self.send({'ok':True},cookie='finance_session='+sid+'; HttpOnly; SameSite=Strict; Path=/; Max-Age='+str(auth['expires_in'])); return
            if not session:
                self.send({'error':'Entre na sua conta para continuar.'},401); return
            token=session['token']
            if self.path in ['/api/preview','/api/preview-pdf']:
                result = parse_pdf(body, self.headers.get('X-Invoice-Month',''), unquote(self.headers.get('X-PDF-Password',''))) if self.path.endswith('-pdf') else {'rows':parse_csv(body)}
                rows=result['rows']
                rules={r['description']:r['category'] for r in supabase.all_rows('/rest/v1/category_rules?select=*&order=user_id,description',token=token)}
                for row in rows:
                    if row['description'] in rules:
                        row['category']=rules[row['description']]; row['rule_applied']=True
                result['digest']=hashlib.sha256(body).hexdigest()
                self.send(result); return
            data=json.loads(body)
            if self.path=='/api/cards':
                supabase.request('/rest/v1/cards','POST',dict(name=data['name'].strip(),issuer=data['issuer'].strip(),closing=int(data['closing']),due=int(data['due']),limit_cents=cents(data['limit'])),token)
            elif self.path=='/api/confirm':
                if any(r.get('needs_review') and not r.get('user_reviewed') for r in data['rows']):
                    raise ValueError('Confirme a conferência das linhas extraídas do PDF.')
                supabase.request('/rest/v1/rpc/confirm_import','POST',dict(p_card=data['card'],p_month=data['month'],p_digest=data['digest'],p_expected=cents(data['expected']),p_rows=data['rows']),token)
            elif self.path=='/api/undo':
                supabase.request('/rest/v1/imports?id=eq.'+quote(str(data['id']),safe=''),'DELETE',token=token)
            elif self.path=='/api/budget':
                if data['category'] not in CATEGORIES: raise ValueError('Categoria inválida.')
                existing=supabase.request('/rest/v1/budgets?month=eq.'+quote(data['month'])+'&category=eq.'+quote(data['category']),token=token)
                payload=dict(month=data['month'],category=data['category'],limit_cents=cents(data['limit']))
                supabase.request('/rest/v1/budgets'+('?id=eq.'+existing[0]['id'] if existing else ''),'PATCH' if existing else 'POST',payload,token)
            elif self.path=='/api/logout':
                cookie=SimpleCookie(self.headers.get('Cookie','')); sid=cookie.get('finance_session')
                if sid: SESSIONS.pop(sid.value,None)
                self.send({'ok':True},cookie='finance_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'); return
            else: raise ValueError('Operação desconhecida.')
            self.send({'ok':True})
        except (ValueError,KeyError,TypeError,IndexError) as error:
            self.send({'error':str(error) if isinstance(error,ValueError) else 'Dados inválidos.'},400)

if __name__=='__main__':
    port=int(os.environ.get('PORT','8765'))
    print('App local: http://127.0.0.1:%s' % port,flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
