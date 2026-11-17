import calendar
import re
from datetime import date
from app.domain import normalize
from app.planning import valid_month


def add_month(month, offset):
    valid_month(month)
    index=int(month[:4])*12+int(month[5:])-1+offset
    year,mon=divmod(index,12)
    if not 1<=year<=9999: raise ValueError('Mês fora do intervalo permitido.')
    return '%04d-%02d'%(year,mon+1)


def month_distance(start,end):
    return (int(end[:4])-int(start[:4]))*12+int(end[5:])-int(start[5:])


def card_month(purchase_date,card):
    day=date.fromisoformat(purchase_date)
    closing=min(card['closing'],calendar.monthrange(day.year,day.month)[1])
    offset=(1 if day.day>closing else 0)+(1 if card['due']<=card['closing'] else 0)
    return add_month(day.isoformat()[:7],offset)


def occurrences(rules,states,month):
    valid_month(month)
    result=[];overrides={(s['rule_id'],s['month']):s for s in states}
    for rule in rules:
        if month<rule['start_month'] or (rule.get('end_month') and month>rule['end_month']):continue
        delta=month_distance(rule['start_month'],month);interval=rule.get('interval_months',1)
        if delta%interval:continue
        index=delta//interval;count=rule.get('occurrence_count')
        if count and index>=count:continue
        override=overrides.get((rule['id'],month),{})
        if override.get('status')=='skipped':continue
        amount=rule['amount_cents']
        if rule.get('total_amount_cents') is not None and count:
            amount=rule['total_amount_cents']//count+(index<rule['total_amount_cents']%count)
        if override.get('amount_override_cents') is not None:amount=override['amount_override_cents']
        year,mon=map(int,month.split('-'));day=min(rule['due_day'],calendar.monthrange(year,mon)[1])
        result.append(dict(id='rule:'+rule['id']+':'+month,rule_id=rule['id'],description=rule['description'],kind=rule['kind'],channel=rule['channel'],category=rule['category'],amount_cents=int(amount),due_date=month+'-'+str(day).zfill(2),settled=override.get('status')=='realized',card_id=rule.get('card_id'),account_id=rule.get('account_id'),current=(index+rule.get('first_installment',1)) if rule.get('schedule_type')=='installment' else 1,total=rule.get('total_installments') or count or 1,month=month,match_pattern=rule.get('match_pattern') or rule['description'],origin='recurrence'))
    return result


def pending_card_entries(events,occurrences_list,matches,month):
    used_events={m['event_id'] for m in matches if m.get('event_id')}
    used_rules={(m['rule_id'],m['month']) for m in matches if m.get('rule_id')}
    result=[]
    for event in events:
        if event['month']!=month or event['id'] in used_events:continue
        result.append(dict(id='event:'+event['id'],event_id=event['id'],card_id=event['card_id'],month=month,date=event['purchase_date'],description=event['description'],amount=event['amount_cents'],category=event['category'],kind='compra',current=1,total=1,origin='manual'))
    for occurrence in occurrences_list:
        if occurrence['channel']!='card' or (occurrence['rule_id'],month) in used_rules:continue
        result.append(dict(id=occurrence['id'],rule_id=occurrence['rule_id'],card_id=occurrence['card_id'],month=month,date=occurrence['due_date'],description=occurrence['description'],amount=occurrence['amount_cents'],category=occurrence['category'],kind='compra',current=occurrence['current'],total=occurrence['total'],origin='recurrence',match_pattern=occurrence['match_pattern']))
    return result


def annotate_matches(rows,sources):
    reserved=set()
    for row in rows:
        row['match_candidates']=[]
        if row['amount']<=0:continue
        exact=[]
        for source in sources:
            # Uma diferença de centavos em previsão não decide a associação; fica para revisão explícita.
            if abs(source['amount']-row['amount'])>1:continue
            kind='event' if source.get('event_id') else 'rule';key=source.get('event_id') or source['rule_id']
            row['match_candidates'].append(dict(id=key,type=kind,label=source['description'],amount=source['amount']))
            pattern=normalize(source.get('match_pattern') or source['description'])
            description=normalize(row['description'])
            same_name=pattern and (pattern in description or description in pattern)
            same_date=kind=='rule' or source['date']==row['date']
            if same_name and same_date and (kind,key) not in reserved:exact.append((kind,key))
        if len(exact)==1:
            row['match_type'],row['match_id']=exact[0];reserved.add(exact[0])
    return rows
