"""Entrada em português com regras locais. Não é um modelo de IA remoto."""
import re
from datetime import date,timedelta
from uuid import uuid4,UUID
from app.domain import cents,normalize,suggest
from app.recurrence import card_month
from app.planning import valid_month


def parse_message(message,cards,accounts,today):
    if not isinstance(message,str) or not 1<=len(message.strip())<=1000:raise ValueError('Escreva uma mensagem de até 1.000 caracteres.')
    text=normalize(message)
    if re.search(r'(quanto|qual).*(posso gastar|disponivel|sobr|guardar)',text):return {'query':True}
    if not re.search(r'\b(compra|comprei|gastei|paguei|pagar|recebi|salario|assinatura|assinei|receber|aluguel)\b',text):
        raise ValueError('Não identifiquei um lançamento. Use, por exemplo: “Comprei no mercado por R$ 120 no cartão principal”.')
    day=date.fromisoformat(today)
    if 'ontem' in text:day-=timedelta(days=1)
    if 'amanha' in text:day+=timedelta(days=1)
    date_pattern=r'\b(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\b'
    explicit=re.search(date_pattern,text)
    if explicit:
        year=int(explicit[3]) if explicit[3] else day.year
        if year<100:year+=2000
        try:day=date(year,int(explicit[2]),int(explicit[1]))
        except ValueError:raise ValueError('Data inválida. Confira o dia e o mês informados.')
    # Dates and installment counts are never candidates for a purchase amount.
    rest=re.sub(date_pattern,' ',text)
    rest=re.sub(r'\bem\s+\d+\s*(?:x\b|vezes|parcelas)', ' ',rest)
    tokens=list(re.finditer(r'(?<![\w/])(?:r\$\s*)?(\d+(?:[.,]\d+)*)(?![\w/])',rest))
    priced=[m for m in tokens if 'r$' in m[0] or re.search(r'[.,]\d{2}$',m[1])]
    candidates=priced or tokens
    amount=None;number=None
    if len(candidates)==1:
        number=candidates[0][1]
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+',number):number=number.replace('.','')
        amount=cents(number)
    elif len(candidates)>1:
        raise ValueError('Encontrei mais de um valor. Informe uma compra por mensagem, por exemplo: gastei 10,00 no mercado no dia 11/11.')
    kind='income' if re.search(r'\b(recebi|salario|receber)\b',text) else 'expense'
    channel='card' if re.search(r'\bcartao\b',text) and kind=='expense' else 'cash'
    card=None;account=None
    if channel=='card':
        matches=[c for c in cards if normalize(c['name']) in text]
        if len(matches)==1:card=matches[0]
        elif len(cards)==1:card=cards[0]
    else:
        matches=[a for a in accounts if normalize(a['name']) in text]
        if len(matches)==1:account=matches[0]
    installments=re.search(r'\bem\s+(\d{1,3})\s*(?:x\b|vezes|parcelas)',text)
    mode='installment' if installments else 'monthly' if any(t in text for t in ['todo mes','mensal','assinatura','assinei']) else 'once'
    # Remove structured fields before deriving the merchant, regardless of word order.
    description=message
    description=re.sub(date_pattern,' ',description)
    description=re.sub(r'\b(?:no\s+dia|dia)\b|\b(?:hoje|ontem|amanh[aã])\b',' ',description,flags=re.I)
    description=re.sub(r'\bem\s+\d+\s*(?:x\b|parcelas|vezes)|\btodo\s+m[eê]s|\bmensal\b',' ',description,flags=re.I)
    description=re.sub(r'(?:com\s+(?:o|a)|no|pelo)\s+cart[aã]o(?:\s+[\wÀ-ÿ-]+)?',' ',description,flags=re.I)
    for source in ([card] if card else [])+([account] if account else []):
        description=re.sub(re.escape(source['name']),' ',description,flags=re.I)
    description=re.sub(r'\bna\s+conta\b',' ',description,flags=re.I)
    description=re.sub(r'(?<![\w/])(?:R\$\s*)?\d+(?:[.,]\d+)*(?![\w/])',' ',description,flags=re.I)
    description=re.sub(r'^(?:eu\s+)?(?:fiz\s+(?:uma\s+)?compra|comprei|gastei|paguei|recebi|assinei)\b',' ',description,flags=re.I)
    description=re.sub(r'\b(?:no\s+valor(?:\s+de)?|por|de|no|na|em|com|meu|minha)\b',' ',description,flags=re.I)
    description=re.sub(r'\s+',' ',description).strip(' .,$-')[:150] or 'Compra informada'
    return dict(key=str(uuid4()),description=description,kind=kind,channel=channel,amount_cents=amount,date=day.isoformat(),month=card_month(day.isoformat(),card) if card else day.isoformat()[:7],card_id=card['id'] if card else None,account_id=account['id'] if account else None,category='Salário' if kind=='income' and 'salario' in text else 'Outras receitas' if kind=='income' else suggest(description),mode=mode,installments=int(installments[1]) if installments else 1,end_month=None,settled=not bool(re.search(r'\b(vou|pagar|receber|amanha)\b',text)),match_pattern=description)


def validate_draft(data):
    out={k:data.get(k) for k in ['description','kind','channel','category','date','month','card_id','account_id','mode','end_month','match_pattern','fulfill_rule_id','commitment_type']}
    if not isinstance(out['description'],str) or not 1<=len(out['description'].strip())<=150:raise ValueError('Informe a descrição.')
    if out['kind'] not in ['income','expense'] or out['channel'] not in ['cash','card'] or out['mode'] not in ['once','monthly','installment']:raise ValueError('Tipo de lançamento inválido.')
    out['amount_cents']=cents(str(data['amount']))
    if not 0<out['amount_cents']<=9000000000000:raise ValueError('Informe um valor positivo.')
    out['date']=date.fromisoformat(out['date']).isoformat();valid_month(out['month'])
    if out['end_month']:valid_month(out['end_month'])
    if out['end_month'] and out['end_month']<out['month']:raise ValueError('Fim da recorrência anterior ao início.')
    if type(data.get('settled')) is not bool:raise ValueError('Situação inválida.')
    out['settled']=data['settled'];out['installments']=int(data.get('installments',1))
    if not 1<=out['installments']<=600:raise ValueError('Número de parcelas inválido.')
    if out['mode']=='installment' and out['amount_cents']<out['installments']:raise ValueError('Valor insuficiente para dividir nas parcelas.')
    if not isinstance(out['category'],str) or not 1<=len(out['category'])<=60:raise ValueError('Informe a categoria.')
    if out['channel']=='card':
        if out['kind']!='expense' or not out['card_id']:raise ValueError('Escolha um cartão para a compra.')
        out['card_id']=str(UUID(out['card_id']));out['account_id']=None
    else:
        out['card_id']=None
        out['account_id']=str(UUID(out['account_id'])) if out['account_id'] else None
    if out['fulfill_rule_id']:out['fulfill_rule_id']=str(UUID(out['fulfill_rule_id']))
    out['commitment_type']='income' if out['kind']=='income' else 'installment' if out['mode']=='installment' else (out['commitment_type'] or ('subscription' if out['category']=='Assinaturas' else 'bill'))
    if out['commitment_type'] not in ['income','bill','subscription','installment']:raise ValueError('Tipo de compromisso inválido.')
    out['description']=out['description'].strip();out['match_pattern']=str(out['match_pattern'] or out['description'])[:150]
    return out
