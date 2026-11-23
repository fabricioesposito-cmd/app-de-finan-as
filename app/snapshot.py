from app import supabase
from concurrent.futures import ThreadPoolExecutor
from app.planning import monthly_summary
from app.finance import financial_view
from app.savings import savings_plan
from app.recurrence import occurrences,pending_card_entries,add_month


def snapshot(token,month):
    def get(table):return supabase.all_rows('/rest/v1/'+table+'?select=*&order='+('user_id,description' if table=='category_rules' else 'id'),token=token)
    names=['cards','imports','budgets','entries','cash_items','monthly_plans','card_settlements','accounts','recurring_rules','recurrence_states','card_events','entry_matches','investor_profiles','savings_schedules']
    with ThreadPoolExecutor(max_workers=6) as executor:
        data=dict(zip(names,executor.map(get,names)))
    data['entries']=[dict(row['payload'],id=row['id'],import_id=row['import_id'],origin='import',registered_at=row.get('registered_at')) for row in data['entries']]
    # Keep the original statement total as evidence; apply only explicit user edits.
    for batch in data['imports']:
        delta=sum(e['amount']-e.get('original_amount',e['amount']) for e in data['entries'] if e['import_id']==batch['id'])
        batch['original_expected']=batch['expected']
        batch['expected']+=delta
        batch['edited_delta_cents']=delta
    account_names={a['id']:a['name'] for a in data['accounts']}
    def calculate(selected):
        projected=occurrences(data['recurring_rules'],data['recurrence_states'],selected)
        extra=pending_card_entries(data['card_events'],projected,data['entry_matches'],selected)
        items=data['cash_items']+[r for r in projected if r['channel']=='cash']
        items=[dict(i,account_name=account_names.get(i.get('account_id'),'Não informado')) for i in items]
        plan,_,_=savings_plan(data['monthly_plans'],data['savings_schedules'],selected)
        return monthly_summary(selected,items,data['imports'],data['cards'],data['card_settlements'],plan,extra),extra,projected
    imported_entries=list(data['entries'])
    data['planning'],extra,data['occurrences']=calculate(month)
    data['entries']+=extra
    data['unmatched_card_entries']=extra
    data['profile']=data['investor_profiles'][0] if data['investor_profiles'] else None
    data['finance']=financial_view(data,month,data['profile'])
    _,data['active_savings_schedule'],data['savings_override']=savings_plan(data['monthly_plans'],data['savings_schedules'],month)
    data['horizon']=[]
    for offset in range(12):
        future=add_month(month,offset)
        if offset==0:finance=data['finance']
        else:
            summary,future_extra,future_occurrences=calculate(future)
            temporary=dict(data,planning=summary,entries=imported_entries+future_extra,occurrences=future_occurrences)
            finance=financial_view(temporary,future,data['profile'])
        data['horizon'].append(dict(month=future,income_cents=finance['income_cents'],costs_cents=finance['costs_cents'],savings_target_cents=finance['reserved_cents'],free_to_use_cents=finance['remaining_cents'],shortfall_cents=finance['deficit_cents']))
    return data
