import csv
import io
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation

CATEGORIES = ['Alimentação', 'Mercado', 'Transporte', 'Saúde', 'Compras', 'Lazer', 'Assinaturas', 'Juros e tarifas', 'Outros']

def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.lower().strip()) if not unicodedata.combining(c))

def cents(value):
    value = value.replace('R$', '').replace(' ', '').strip()
    if ',' in value:
        value = value.replace('.', '').replace(',', '.')
    try:
        number = Decimal(value)
        if not number.is_finite() or number != number.quantize(Decimal('0.01')):
            raise ValueError('Valor deve ter no máximo duas casas decimais.')
        return int(number * 100)
    except InvalidOperation:
        raise ValueError('Valor monetário inválido.')

def suggest(description):
    text = normalize(description)
    for terms, category in [(['supermercado', 'mercado'], 'Mercado'), (['uber', '99app', 'posto'], 'Transporte'), (['restaurante', 'ifood', 'padaria'], 'Alimentação'), (['farmacia', 'clinica'], 'Saúde'), (['netflix', 'spotify'], 'Assinaturas')]:
        if any(term in text for term in terms):
            return category
    return 'Outros'

def parse_csv(data):
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('cp1252')
    if not text.strip():
        raise ValueError('Arquivo vazio.')
    delimiter = ';' if text.splitlines()[0].count(';') > text.splitlines()[0].count(',') else ','
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    aliases = {'data': 'date', 'date': 'date', 'descricao': 'description', 'description': 'description', 'estabelecimento': 'description', 'valor': 'amount', 'amount': 'amount', 'parcela': 'installment', 'tipo': 'kind'}
    headers = {h: aliases.get(normalize(h)) for h in (reader.fieldnames or [])}
    if not {'date', 'description', 'amount'}.issubset(set(headers.values())):
        raise ValueError('CSV precisa das colunas data, descricao e valor. Use o modelo disponível.')
    result = []
    for line, raw in enumerate(reader, 2):
        row = {headers[k]: v for k, v in raw.items() if k in headers and headers[k]}
        try:
            date = None
            for fmt in ['%Y-%m-%d', '%d/%m/%Y']:
                try:
                    date = datetime.strptime(row['date'].strip(), fmt).date().isoformat()
                    break
                except ValueError:
                    pass
            if not date or not row['description'].strip():
                raise ValueError('Data ou descrição inválida.')
            amount = cents(row['amount'])
            kind = normalize(row.get('kind', 'compra') or 'compra')
            if kind not in ['compra', 'estorno', 'credito', 'juros', 'tarifa']:
                raise ValueError('Tipo desconhecido; pagamentos e subtotais não são compras.')
            if kind in ['estorno', 'credito']:
                amount = -abs(amount)
            if amount < 0 and kind == 'compra':
                kind = 'credito'
            installment = row.get('installment', '') or ''
            current, total = 1, 1
            if installment:
                match = re.fullmatch(r'(\d{1,3})/(\d{1,3})', installment.strip())
                if not match:
                    raise ValueError('Parcela deve seguir o formato 2/10.')
                current, total = map(int, match.groups())
                if not 1 <= current <= total <= 120:
                    raise ValueError('Parcelamento inválido.')
            result.append(dict(date=date, description=row['description'].strip(), amount=amount, kind=kind, current=current, total=total, category='Juros e tarifas' if kind in ['juros', 'tarifa'] else suggest(row['description']), source_line=line))
        except (ValueError, AttributeError) as error:
            raise ValueError('Linha %s: %s' % (line, error))
    if not result:
        raise ValueError('Arquivo sem lançamentos.')
    return result

def fingerprint(row):
    return (row['date'], normalize(row['description']), row['amount'], row['kind'], row['current'], row['total'])

def reconcile(rows, expected):
    return sum(r['amount'] for r in rows) - expected

def future_commitment(rows):
    return sum(max(0, r['total'] - r['current']) * r['amount'] for r in rows if r['amount'] > 0)
