"""Planejamento do mês por valores declarados, separado do saldo bancário real."""
import calendar
import re
from datetime import date
from app.domain import cents


def valid_month(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',value):
        raise ValueError('Mês inválido.')
    date.fromisoformat(value+'-01')
    return value


def item_payload(data):
    description=str(data.get('description','')).strip()
    kind=data.get('kind')
    category=str(data.get('category','')).strip()
    if not 1<=len(description)<=150 or kind not in ['income','expense'] or not 1<=len(category)<=60:
        raise ValueError('Preencha descrição, tipo e categoria.')
    amount=cents(str(data['amount']))
    if not 0<amount<=9000000000000:
        raise ValueError('Informe um valor positivo para a conta ou receita.')
    due=date.fromisoformat(data['due_date']).isoformat()
    if type(data.get('settled',False)) is not bool:
        raise ValueError('Situação inválida.')
    return dict(description=description,kind=kind,category=category,amount_cents=amount,due_date=due,settled=data.get('settled',False))


def monthly_summary(month, items, imports, cards, settlements, plan=None):
    valid_month(month)
    plan=plan or {}
    selected=[i for i in items if i['due_date'][:7]==month]
    income=sum(i['amount_cents'] for i in selected if i['kind']=='income')
    received=sum(i['amount_cents'] for i in selected if i['kind']=='income' and i['settled'])
    expenses=sum(i['amount_cents'] for i in selected if i['kind']=='expense')
    paid_expenses=sum(i['amount_cents'] for i in selected if i['kind']=='expense' and i['settled'])
    bills=[]; pending_cards=[]; pending_ids=[]
    for card in cards:
        batches=[i for i in imports if i['card_id']==card['id'] and i['month']==month]
        payments=[p for p in settlements if p['card_id']==card['id'] and p['month']==month]
        paid=sum(p['paid_cents'] for p in payments)
        net=sum(i['expected'] for i in batches)
        if not batches and not payments:
            pending_cards.append(card['name']);pending_ids.append(card['id']);continue
        # Crédito de fatura não é dinheiro recebido. Um pagamento já realizado permanece no caixa mesmo se a importação for desfeita.
        override=next((p['bill_total_cents'] for p in payments if p.get('bill_total_cents') is not None),None)
        amount=max(0,override if override is not None else net,paid)
        due_day=min(card['due'],calendar.monthrange(int(month[:4]),int(month[5:]))[1])
        bills.append(dict(card_id=card['id'],name=card['name'],amount_cents=amount,imported_cents=net,paid_cents=paid,pending_cents=max(0,amount-paid),due_date=month+'-'+str(due_day).zfill(2),has_import=bool(batches),bill_total_cents=override,overpaid=paid>max(0,override if override is not None else net)))
    card_total=sum(b['amount_cents'] for b in bills)
    card_paid=sum(b['paid_cents'] for b in bills)
    opening=plan.get('opening_cents',0)
    target=plan.get('savings_target_cents',0)
    saved=plan.get('saved_cents',0)
    forecast=opening+income-expenses-card_total
    actual=opening+received-paid_expenses-card_paid-saved
    projected_savings=min(max(forecast,0),max(target,saved))
    return dict(month=month,opening_cents=opening,income_cents=income,received_cents=received,receivable_cents=income-received,
                expenses_cents=expenses,card_cents=card_total,costs_cents=expenses+card_total,
                paid_cents=paid_expenses+card_paid,payable_cents=expenses-paid_expenses+card_total-card_paid,
                forecast_cents=forecast,current_cash_cents=actual,savings_target_cents=target,saved_cents=saved,
                can_save_cents=max(0,forecast),planned_save_cents=projected_savings,
                free_to_use_cents=max(0,forecast-max(target,saved)),shortfall_cents=max(0,-forecast),
                savings_gap_cents=max(0,max(target,saved)-max(0,forecast)),
                bills=bills,missing_cards=pending_cards,missing_card_ids=pending_ids,has_plan=bool(plan),items=selected)
