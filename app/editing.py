"""Edit existing purchases through the authenticated user's Data API access."""
from datetime import date
from uuid import UUID
from app.domain import cents
from app.planning import valid_month,item_payload
from app import supabase


def update_purchase(data,token):
    source=data.get('source')
    if source not in ['event','import']:raise ValueError('Origem inválida.')
    row_id=str(UUID(data['id']))
    table='entries' if source=='import' else 'card_events'
    path='/rest/v1/'+table+'?id=eq.'+row_id
    rows=supabase.request(path,token=token)
    if not rows:raise ValueError('Lançamento não encontrado na sua conta. Atualize a lista.')
    original=rows[0]
    description=str(data.get('description','')).strip()
    category=str(data.get('category','')).strip()
    if not 1<=len(description)<=150 or not 1<=len(category)<=60:raise ValueError('Confira a descrição e a categoria.')
    amount=cents(str(data['amount']))
    if not 0<amount<=9000000000000:raise ValueError('Informe um valor positivo.')
    purchase_date=date.fromisoformat(data['date']).isoformat()
    if source=='import':
        payload=dict(original['payload'])
        old=payload['amount']
        payload.update(description=description,category=category,date=purchase_date,amount=-amount if old<0 else amount,
                       original_amount=payload.get('original_amount',old),user_edited=True)
        change={'payload':payload}
    else:
        card_id=str(UUID(data['card_id']));month=valid_month(data['month'])
        # Matches bind both the source card and invoice month. Edit the imported
        # transaction instead, or explicitly unlink before moving the source.
        matches=supabase.request('/rest/v1/entry_matches?event_id=eq.'+row_id,token=token)
        if matches:raise ValueError('Esta compra já está vinculada à fatura. Edite o lançamento importado na lista.')
        cards=supabase.request('/rest/v1/cards?id=eq.'+card_id,token=token)
        if not cards:raise ValueError('Cartão não encontrado na sua conta.')
        change=dict(description=description,category=category,amount_cents=amount,purchase_date=purchase_date,card_id=card_id,month=month)
    supabase.request(path,'PATCH',change,token)
    saved=supabase.request(path,token=token)
    if not saved or any(saved[0].get(k)!=v for k,v in change.items()):
        raise ValueError('Não foi possível confirmar a edição. Atualize a lista antes de tentar novamente.')


def update_cash_item(data,token):
    row_id=str(UUID(data['id']))
    path='/rest/v1/cash_items?id=eq.'+row_id
    if not supabase.request(path,token=token):
        raise ValueError('Lançamento não encontrado na sua conta. Atualize a lista.')
    payload=item_payload(data)
    if 'account_id' in data:payload['account_id']=str(UUID(data['account_id'])) if data['account_id'] else None
    supabase.request(path,'PATCH',payload,token)
    saved=supabase.request(path,token=token)
    if not saved or any(saved[0].get(k)!=v for k,v in payload.items()):
        raise ValueError('A alteração não foi confirmada. Atualize a lista antes de tentar novamente.')
    return saved[0]


def update_fixed_bill(data,token):
    return update_recurring_expense(data,token,allowed_types=('bill',))


def update_recurring_expense(data,token,allowed_types=('bill','subscription','installment')):
    rule_id=str(UUID(data['id']))
    path='/rest/v1/recurring_rules?id=eq.'+rule_id
    rules=supabase.request(path,token=token)
    if not rules:raise ValueError('Recorrência não encontrada na sua conta.')
    rule=rules[0]
    kind='installment' if rule['schedule_type']=='installment' else rule.get('commitment_type') or ('subscription' if rule['category']=='Assinaturas' else 'bill')
    if rule['kind']!='expense' or kind not in allowed_types:
        raise ValueError('Esta edição é exclusiva para contas, assinaturas e parcelamentos.')
    description=str(data.get('description','')).strip();category=str(data.get('category','')).strip()
    if not 1<=len(description)<=150 or not 1<=len(category)<=60:raise ValueError('Informe a descrição e a categoria.')
    amount=cents(str(data['amount']));due_day=int(data['due_day'])
    if not 0<amount<=9000000000000 or not 1<=due_day<=31:raise ValueError('Confira o valor e o dia de vencimento.')
    payload=dict(description=description,category=category,amount_cents=amount,due_day=due_day)
    if not rule.get('commitment_type'):payload['commitment_type']=kind
    # Finite schedules distribute their total; keep it consistent with the edited standard amount.
    if amount!=rule['amount_cents'] and rule.get('total_amount_cents') is not None and rule.get('occurrence_count'):
        total=amount*rule['occurrence_count']
        if total>9000000000000:raise ValueError('O total das parcelas ultrapassa o valor permitido.')
        payload['total_amount_cents']=total
    supabase.request(path,'PATCH',payload,token)
    saved=supabase.request(path,token=token)
    if not saved or any(saved[0].get(k)!=v for k,v in payload.items()):
        raise ValueError('Edição não confirmada. Atualize a lista antes de tentar novamente.')
    return saved[0]
