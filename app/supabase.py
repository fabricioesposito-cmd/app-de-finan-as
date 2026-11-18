import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CONFIG = json.loads((Path(__file__).resolve().parent.parent / 'config.json').read_text())
CONFIG['url']=os.environ.get('SUPABASE_URL',CONFIG['url']).rstrip('/')
CONFIG['publishable_key']=os.environ.get('SUPABASE_PUBLISHABLE_KEY',CONFIG['publishable_key'])

def request(path, method='GET', data=None, token=None):
    headers = {'apikey': CONFIG['publishable_key'], 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(CONFIG['url'] + path, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
    try:
        with urlopen(req, timeout=25) as response:
            content = response.read()
            return json.loads(content) if content else None
    except HTTPError as error:
        detail = json.loads(error.read() or '{}')
        raise ValueError(detail.get('msg') or detail.get('message') or detail.get('error_description') or 'Falha no Supabase.')
    except URLError:
        raise ValueError('Não foi possível conectar ao Supabase.')


def all_rows(path, token):
    result = []
    offset = 0
    separator = '&' if '?' in path else '?'
    while True:
        page = request(path + separator + 'limit=500&offset=' + str(offset), token=token)
        result.extend(page)
        if len(page) < 500:
            return result
        offset += len(page)
