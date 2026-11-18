"""Leitura financeira única para a interface reconstruída. Valores sempre em centavos."""
from collections import defaultdict

SOURCE_LINKS=[
 {'title':'CVM: reserva de emergência','url':'https://www.gov.br/investidor/pt-br/investir/antes-de-investir/defina-seus-objetivos/emergencias-e-aposentadoria'},
 {'title':'CVM: objetivos e perfil','url':'https://www.gov.br/investidor/pt-br/investir/antes-de-investir/respeite-o-seu-perfil-de-investidor/entenda-o-suitability'},
 {'title':'CVM: títulos públicos','url':'https://www.gov.br/investidor/pt-br/investir/como-investir/tipos-de-investimentos/titulos-publicos'},
 {'title':'FGC: produtos e condições da garantia','url':'https://www.fgc.org.br/sobre-garantia-fgc'}]


def rule_type(rule):
    if rule['kind']=='income':return 'income'
    if rule.get('schedule_type')=='installment':return 'installment'
    return rule.get('commitment_type') or ('subscription' if rule['category']=='Assinaturas' else 'bill')


def financial_view(data,month,profile=None):
    plan=data['planning'];rules={r['id']:r for r in data['recurring_rules']}
    batches={i['id']:i for i in data['imports']};matches={m['entry_id']:m for m in data['entry_matches']}
    rows=[]
    for item in plan['items']:
        is_rule=bool(item.get('rule_id'));r=rules.get(item.get('rule_id'),{})
        rows.append(dict(id=item['id'],rule_id=item.get('rule_id'),description=item['description'],kind=item['kind'],category=item['category'],amount_cents=item['amount_cents'],date=item['due_date'],month=item.get('budget_month') or item['due_date'][:7],channel='cash',account_id=item.get('account_id'),card_id=None,recurring=is_rule,type=rule_type(r) if r else 'variable',settled=item['settled'],origin='recurrence' if is_rule else 'manual',source=item.get('account_name','Não informado')))
    card_names={c['id']:c['name'] for c in data['cards']}
    for entry in data['entries']:
        batch=batches.get(entry.get('import_id'),{})
        entry_month=entry.get('month') or batch.get('month')
        if entry_month!=month:continue
        match=matches.get(entry['id'],{})
        rid=entry.get('rule_id') or match.get('rule_id');r=rules.get(rid)
        card=entry.get('card_id') or batch.get('card_id')
        kind=rule_type(r) if r else 'installment' if entry.get('total',1)>1 else 'subscription' if entry.get('future_mode')=='monthly' else 'variable'
        rows.append(dict(id=entry['id'],rule_id=rid,event_id=entry.get('event_id'),description=entry['description'],kind='expense',category=entry['category'],amount_cents=entry['amount'],date=entry['date'],channel='card',card_id=card,account_id=None,recurring=kind in ['subscription','bill','installment'],type=kind,settled=entry.get('origin')!='recurrence',origin=entry.get('origin','import'),source=card_names.get(card,'Cartão'),current=entry.get('current',1),total=entry.get('total',1)))
    # Ajustes agregados e créditos acima do saldo da fatura não criam renda fictícia.
    for bill in plan['bills']:
        detailed=sum(r['amount_cents'] for r in rows if r['channel']=='card' and r['card_id']==bill['card_id'])
        delta=bill['amount_cents']-detailed
        if delta:rows.append(dict(id='adjustment:'+bill['card_id'],description='Ajuste da fatura · '+bill['name'],kind='expense',category='Outros',amount_cents=delta,date=bill['due_date'],channel='card',card_id=bill['card_id'],recurring=False,type='adjustment',settled=False,origin='adjustment',source=bill['name']))
    incomes=[r for r in rows if r['kind']=='income'];costs=[r for r in rows if r['kind']=='expense']
    recurring_income=sum(r['amount_cents'] for r in incomes if r['recurring'])
    extra_income=sum(r['amount_cents'] for r in incomes if not r['recurring'])
    fixed=sum(r['amount_cents'] for r in costs if r['recurring'])
    variable=sum(r['amount_cents'] for r in costs if not r['recurring'])
    reserved=max(plan['savings_target_cents'],plan['saved_cents'])
    before=recurring_income+extra_income-fixed-variable
    available=before-reserved
    categories=defaultdict(int);types=defaultdict(int)
    for row in costs:categories[row['category']]+=row['amount_cents'];types[row['type']]+=row['amount_cents']
    result=dict(month=month,rows=rows,income_cents=recurring_income+extra_income,recurring_income_cents=recurring_income,extra_income_cents=extra_income,recurring_costs_cents=fixed,variable_costs_cents=variable,costs_cents=fixed+variable,base_residual_cents=recurring_income-fixed,spend_budget_cents=recurring_income+extra_income-fixed-reserved,reserved_cents=reserved,signed_remaining_cents=available,remaining_cents=max(0,available),deficit_cents=max(0,-available),before_reserve_cents=before,current_cash_cents=plan['current_cash_cents'],paid_cents=plan['paid_cents'],pending_cents=plan['payable_cents'],income_ranking=sorted(incomes,key=lambda r:r['amount_cents'],reverse=True),expense_ranking=sorted(costs,key=lambda r:r['amount_cents'],reverse=True),categories=[{'name':name,'amount_cents':amount} for name,amount in sorted(categories.items(),key=lambda p:p[1],reverse=True)],recurrence_groups=[{'type':name,'amount_cents':amount} for name,amount in types.items()],warnings=[])
    if plan['missing_cards']:result['warnings'].append('Sem fatura ou previsão para: '+', '.join(plan['missing_cards'])+'. O disponível pode estar incompleto.')
    for batch in data['imports']:
        if batch.get('month')==month and batch.get('edited_delta_cents'):
            result['warnings'].append('Fatura com valores editados: o planejamento usa os lançamentos corrigidos. O total original da importação foi preservado para conferência.')
    if recurring_income==0:result['warnings'].append('Cadastre a renda recorrente para ter uma base mensal de orçamento.')
    if available<0:result['warnings'].append('Os compromissos, gastos e reserva ultrapassam a renda deste mês.')
    result['suggestion']=investment_suggestion(result,profile,missing_cards=bool(plan['missing_cards']))
    return result


def investment_suggestion(finance,profile=None,missing_cards=False):
    profile=profile or {}
    rate=profile.get('savings_rate',10)
    amount=min(max(finance['before_reserve_cents'],0),max(finance['recurring_income_cents'],0)*rate//100)
    result=dict(amount_cents=amount,rate=rate,phase='profile',title='Planeje sua reserva',message='Defina objetivo, prazo, custos essenciais e situação das dívidas para ver opções de investimento.',options=[],sources=SOURCE_LINKS,emergency_target_cents=0,emergency_gap_cents=0)
    essentials=profile.get('essential_costs_cents',0)
    target=essentials*profile.get('reserve_months',6)
    gap=max(0,target-profile.get('emergency_balance_cents',0))
    result.update(emergency_target_cents=target,emergency_gap_cents=gap)
    if finance['before_reserve_cents']<=0:
        result.update(amount_cents=0,phase='deficit',title='Equilibre o mês primeiro',message='Não há sobra prevista para uma nova reserva. Revise custos e receitas antes de planejar aportes.');return result
    if missing_cards:
        result.update(amount_cents=0,phase='incomplete',title='Complete os compromissos do mês',message='Há cartão sem fatura ou previsão. Informe seus custos antes de estimar um aporte.');return result
    if profile.get('expensive_debt')=='yes':
        result.update(amount_cents=0,phase='debt',title='Compare o custo das dívidas',message='Com dívidas de juros altos, compare o custo efetivo da dívida antes de novos investimentos. A simulação não reserva um aporte automaticamente.');return result
    complete=all([profile.get('goal'),profile.get('risk'),profile.get('horizon_months'),essentials>0,profile.get('expensive_debt')=='no'])
    if not complete:return result
    liquid=[{'name':'Tesouro Selic','description':'Alternativa de renda fixa pública para comparar em objetivos líquidos. O preço pode oscilar e a venda antecipada segue preços e regras do Tesouro.'},{'name':'CDB com liquidez diária','description':'Compare emissor, resgate, carência, taxas e tributos. A cobertura do FGC depende do produto e das condições e limites aplicáveis.'}]
    if gap>0 or profile['goal']=='emergency':
        result.update(phase='emergency',title='Forme sua reserva de emergência',message='Priorize baixo risco e acesso ao dinheiro. A meta é o número de meses de custos essenciais que você escolheu, não uma garantia de suficiência.',options=liquid)
    elif profile.get('needs_liquidity',True) or profile['horizon_months']<=24:
        result.update(phase='liquidity',title='Alinhe o investimento ao resgate',message='Para dinheiro que pode ser usado no curto prazo, compare alternativas de baixo risco e liquidez compatível.',options=liquid)
    else:
        result.update(phase='goals',title='Invista de acordo com seu objetivo',message='A reserva informada cobre a meta escolhida. Compare prazo, risco e diversificação; a seleção de produtos exige a avaliação de perfil da instituição.',options=[{'name':'Renda fixa com prazo alinhado','description':'Compare títulos públicos e bancários com vencimento compatível. Em títulos como Tesouro IPCA+, vender antes do vencimento pode causar perdas.'},{'name':'Diversificação para o longo prazo','description':'Avalie classes e fundos compatíveis com seu perfil, custos e capacidade de suportar perdas. O app não escolhe ações, fundos específicos nem executa aplicações.'}])
    return result
