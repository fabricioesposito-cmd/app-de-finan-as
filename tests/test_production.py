import io
import json
import time
import unittest
from unittest.mock import patch
from email.message import Message
from app.wsgi import application
from app.server import Handler,SESSIONS

class WSGITests(unittest.TestCase):
    def call(self,path='/',method='GET',body=b'',headers=None,scheme='https'):
        env={'PATH_INFO':path.split('?')[0],'QUERY_STRING':path.partition('?')[2],'REQUEST_METHOD':method,'wsgi.input':io.BytesIO(body),'CONTENT_LENGTH':str(len(body)),'wsgi.url_scheme':scheme,**(headers or {})}
        response={}
        data=b''.join(application(env,lambda status,headers:response.update(status=status,headers=dict(headers))))
        return response,data

    def test_public_assets_health_and_auth_gate(self):
        response,data=self.call('/healthz');self.assertEqual(response['status'],'200 OK');self.assertEqual(json.loads(data),{'status':'ok'})
        response,data=self.call('/manifest.webmanifest');self.assertEqual(response['headers']['Content-Type'],'application/manifest+json');self.assertEqual(json.loads(data)['display'],'standalone')
        response,data=self.call('/api/state?month=2026-11');self.assertFalse(json.loads(data)['authenticated'])
        response,data=self.call('/icon-192.png');self.assertTrue(data.startswith(b'\x89PNG'))
        response,data=self.call('/',method='HEAD');self.assertEqual(data,b'');self.assertGreater(int(response['headers']['Content-Length']),0)

    def test_login_cookie_secure_and_sessions_are_server_side(self):
        with patch('app.server.supabase.request',return_value=dict(access_token='fake-access',refresh_token='fake-refresh',expires_in=3600,user={'email':'test@example.invalid'})):
            # Retrieve the current CSRF token the same way the browser does.
            _,data=self.call('/api/state');token=json.loads(data)['token']
            response,data=self.call('/api/login','POST',json.dumps({'email':'test@example.invalid','password':'fake-password'}).encode(),{'HTTP_X_APP_TOKEN':token})
        self.assertIn('; Secure',response['headers']['Set-Cookie']);self.assertIn('HttpOnly',response['headers']['Set-Cookie'])
        self.assertNotIn('fake-access',data.decode());self.assertNotIn('fake-refresh',response['headers']['Set-Cookie'])

    def test_method_and_body_limits(self):
        response,_=self.call('/',method='DELETE');self.assertTrue(response['status'].startswith('405'))
        response={};application({'CONTENT_LENGTH':'5000001','wsgi.input':io.BytesIO()},lambda status,headers:response.update(status=status))
        self.assertTrue(response['status'].startswith('413'))

class SessionRefreshTests(unittest.TestCase):
    def test_refresh_preserves_session_identity_and_preview_owner(self):
        handler=object.__new__(Handler);handler.headers=Message();handler.headers['Cookie']='finance_session=fixture'
        SESSIONS['fixture']=dict(id='fixture',token='old',refresh_token='refresh',email='test@example.invalid',expires=time.time()+1,session_expires=time.time()+1000)
        with patch('app.server.supabase.request',return_value=dict(access_token='new',refresh_token='rotated',expires_in=3600)) as request:
            session=handler.session()
        self.assertEqual(session['id'],'fixture');self.assertEqual(session['token'],'new')
        self.assertEqual(request.call_args.args[2],{'refresh_token':'refresh'})
        SESSIONS.pop('fixture',None)
