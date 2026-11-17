from app import supabase
from concurrent.futures import ThreadPoolExecutor
from app.planning import monthly_summary
from app.recurrence import occurrences,pending_card_entries,add_month


def snapshot(token,month):
    def get(table):return supabase.all_rows('/rest/v1/'+table+'?select=*&order='+('user_id,description' if table=='category_rules' else 'id'),token=token)
    names=['cards','imports','budgets','entries','cash_items','monthly_plans','card_settlements','accounts','recurring_rules','recurrence_states','card_events','entry_matches']
    with ThreadPoolExecutor(max_workers=6) as executor:
        data=dict(zip(names,executor.map(get,names)))
    data['entries']=[dict(row['payload'],id=row['id'],import_id=row['import_id'],origin='import') for row in data['entries']]
    account_names={a['id']:a['name'] for a in data['accounts']}
    def calculate(selected):
        projected=occurrences(data['recurring_rules'],data['recurrence_states'],selected)
        extra=pending_card_entries(data['card_events'],projected,data['entry_matches'],selected)
        items=data['cash_items']+[r for r in projected if r['channel']=='cash']
        items=[dict(i,account_name=account_names.get(i.get('account_id'),'Não informado')) for i in items]
        plan=next((p for p in data['monthly_plans'] if p['month']==selected),None)
        return monthly_summary(selected,items,data['imports'],data['cards'],data['card_settlements'],plan,extra),extra,projected
    data['planning'],extra,data['occurrences']=calculate(month)
    data['entries']+=extra
    data['unmatched_card_entries']=extra
    data['horizon']=[]
    for offset in range(12):
        future=add_month(month,offset);summary,_,_=calculate(future)
        data['horizon'].append({k:summary[k] for k in ['month','income_cents','costs_cents','savings_target_cents','free_to_use_cents','shortfall_cents']})
    return data
