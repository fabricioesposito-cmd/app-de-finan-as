"""WSGI entry point for Gunicorn; shares the same routes as the local server."""
import io
import json
import logging
import os
from email.message import Message
from http import HTTPStatus
from app.server import Handler

MAX_BODY=5_000_000


def application(environ,start_response):
    handler=object.__new__(Handler)
    handler.path=environ.get('PATH_INFO','/')+('?' + environ['QUERY_STRING'] if environ.get('QUERY_STRING') else '')
    handler.headers=Message()
    for key,value in environ.items():
        if key.startswith('HTTP_'):handler.headers[key[5:].replace('_','-')]=str(value)
    handler.headers['Content-Type']=environ.get('CONTENT_TYPE','')
    length=environ.get('CONTENT_LENGTH','') or '0'
    try:size=int(length)
    except ValueError:size=-1
    if not 0<=size<=MAX_BODY:
        body=json.dumps({'error':'Envie um arquivo de até 5 MB.'}).encode()
        start_response('413 Payload Too Large',[('Content-Type','application/json'),('Cache-Control','no-store')]);return [body]
    handler.headers['Content-Length']=str(size)
    handler.rfile=io.BytesIO(environ['wsgi.input'].read(size) if size else b'')
    result={}
    def send(data,status=200,mime='application/json',cookie=None):
        body=json.dumps(data,ensure_ascii=False).encode() if mime=='application/json' else data
        headers=[('Content-Type',mime),('Content-Length',str(len(body))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'"),('Referrer-Policy','no-referrer')]
        if cookie:headers.append(('Set-Cookie',cookie+('; Secure' if environ.get('wsgi.url_scheme')=='https' or os.environ.get('SECURE_COOKIES')=='1' else '')))
        result.update(status=status,headers=headers,body=body)
    handler.send=send
    try:
        method=environ.get('REQUEST_METHOD','GET')
        if method in ['GET','HEAD']:handler.do_GET()
        elif method=='POST':handler.do_POST()
        else:send({'error':'Método não permitido.'},405)
    except Exception:
        logging.exception('Clareza request failed')
        send({'error':'Não foi possível concluir. Tente novamente.'},500)
    start_response(str(result['status'])+' '+HTTPStatus(result['status']).phrase,result['headers'])
    return [b'' if environ.get('REQUEST_METHOD')=='HEAD' else result['body']]
