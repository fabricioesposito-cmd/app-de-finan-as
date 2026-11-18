import unittest
from unittest.mock import patch
from app.snapshot import snapshot
from app.profile import profile_payload
from app.finance import investment_suggestion

CARD={'id':'card1','name':'Principal','due':18,'closing':11,'issuer':'Fictício','limit_cents':1000000}
RULE={'id':'salary','description':'Salário','kind':'income','channel':'cash','category':'Salário','amount_cents':800000,'total_amount_cents':None,'start_month':'2026-11','end_month':None,'due_day':15,'interval_months':1,'occurrence_count':None,'schedule_type':'monthly','card_id':None,'account_id':None,'match_pattern':'Salário','commitment_type':'income'}

def state_for(extra=None):
    fixtures={'cards':[CARD],'recurring_rules':[RULE,dict(RULE,id='bill',description='Aluguel',kind='expense',category='Moradia',amount_cents=200000,commitment_type='bill'),dict(RULE,id='sub',description='Streaming',kind='expense',channel='card',category='Assinaturas',amount_cents=4000,card_id='card1',commitment_type='subscription')], 'monthly_plans':[{'id':'plan','month':'2026-11','opening_cents':100000,'savings_target_cents':100000,'saved_cents':0}]}
    fixtures.update(extra or {})
    def get(path,token):return fixtures.get(path.split('/')[3].split('?')[0],[])
    with patch('app.snapshot.supabase.all_rows',side_effect=get):return snapshot('fixture','2026-11')

PROFILE=dict(goal='emergency',risk='conservative',horizon_months=12,needs_liquidity=True,essential_costs_cents=300000,emergency_balance_cents=0,reserve_months=6,savings_rate=10,expensive_debt='no')

class FinanceTests(unittest.TestCase):
    def test_recurring_base_reserve_and_spending(self):
        data=state_for({'cash_items':[{'id':'market','description':'Mercado','kind':'expense','category':'Mercado','amount_cents':50000,'due_date':'2026-11-15','settled':True}]})
        f=data['finance']
        self.assertEqual(f['recurring_income_cents'],800000)
        self.assertEqual(f['recurring_costs_cents'],204000)
        self.assertEqual(f['base_residual_cents'],596000)
        self.assertEqual(f['variable_costs_cents'],50000)
        self.assertEqual(f['remaining_cents'],446000)
        self.assertEqual(data['horizon'][0]['free_to_use_cents'],446000)
        self.assertEqual(sum(r['amount_cents'] for r in f['expense_ranking']),data['planning']['costs_cents'])
    def test_opening_balance_does_not_expand_consumption_budget(self):
        data=state_for();self.assertEqual(data['finance']['remaining_cents'],496000)
        self.assertEqual(data['planning']['free_to_use_cents'],596000)
    def test_imported_subscription_replaces_forecast_and_keeps_type(self):
        data=state_for({'imports':[{'id':'batch','card_id':'card1','month':'2026-11','expected':4100}], 'entries':[{'id':'entry1','import_id':'batch','payload':{'date':'2026-11-10','description':'STREAMING FICTICIO','amount':4100,'category':'Assinaturas','current':1,'total':1,'kind':'compra'}}], 'entry_matches':[{'id':'link','entry_id':'entry1','rule_id':'sub','event_id':None,'month':'2026-11'}]})
        self.assertEqual(data['finance']['recurring_costs_cents'],204100)
        self.assertEqual(len([r for r in data['finance']['expense_ranking'] if r['type']=='subscription']),1)
    def test_negative_credit_does_not_create_fake_income(self):
        data=state_for({'recurring_rules':[RULE], 'imports':[{'id':'batch','card_id':'card1','month':'2026-11','expected':-5000}], 'entries':[{'id':'credit','import_id':'batch','payload':{'date':'2026-11-10','description':'Crédito fictício','amount':-5000,'category':'Compras','current':1,'total':1,'kind':'credito'}}]})
        self.assertEqual(data['finance']['costs_cents'],0)
        self.assertEqual(data['finance']['income_cents'],800000)
        self.assertEqual(data['finance']['remaining_cents'],700000)
    def test_extra_income_is_separate_from_recurring_base(self):
        data=state_for({'cash_items':[{'id':'extra','description':'Freelance','kind':'income','category':'Outras receitas','amount_cents':200000,'due_date':'2026-11-15','settled':False}]})
        self.assertEqual(data['finance']['extra_income_cents'],200000)
        self.assertEqual(data['finance']['base_residual_cents'],596000)
        self.assertEqual(data['finance']['remaining_cents'],696000)
    def test_reserved_money_not_subtracted_twice(self):
        data=state_for({'monthly_plans':[{'id':'plan','month':'2026-11','opening_cents':0,'savings_target_cents':100000,'saved_cents':50000}]})
        self.assertEqual(data['finance']['reserved_cents'],100000)
        self.assertEqual(data['finance']['remaining_cents'],496000)
    def test_rankings_and_categories_reconcile(self):
        f=state_for()['finance']
        self.assertEqual(f['expense_ranking'][0]['description'],'Aluguel')
        self.assertEqual(sum(c['amount_cents'] for c in f['categories']),f['costs_cents'])
        self.assertEqual(sum(c['amount_cents'] for c in f['recurrence_groups']),f['costs_cents'])

class InvestmentTests(unittest.TestCase):
    def finance(self):return dict(before_reserve_cents=200000,recurring_income_cents=800000)
    def test_simulation_capped_by_surplus(self):
        result=investment_suggestion(dict(before_reserve_cents=10000,recurring_income_cents=800000),PROFILE)
        self.assertEqual(result['amount_cents'],10000)
    def test_no_product_selection_without_profile(self):
        result=investment_suggestion(self.finance());self.assertEqual(result['phase'],'profile');self.assertEqual(result['options'],[])
    def test_deficit_or_high_cost_debt_does_not_suggest_contribution(self):
        self.assertEqual(investment_suggestion(dict(before_reserve_cents=-100,recurring_income_cents=800000),PROFILE)['amount_cents'],0)
        result=investment_suggestion(self.finance(),dict(PROFILE,expensive_debt='yes'));self.assertEqual(result['amount_cents'],0);self.assertEqual(result['options'],[])
    def test_missing_card_prevents_optimistic_investment_estimate(self):
        self.assertEqual(investment_suggestion(self.finance(),PROFILE,True)['amount_cents'],0)
    def test_emergency_and_liquidity_paths(self):
        result=investment_suggestion(self.finance(),PROFILE)
        self.assertEqual(result['phase'],'emergency');self.assertEqual(result['emergency_target_cents'],1800000)
        self.assertEqual(len(result['options']),2)
        self.assertEqual(investment_suggestion(self.finance(),dict(PROFILE,goal='short',emergency_balance_cents=1800000))['phase'],'liquidity')
    def test_long_term_requires_complete_reserve_and_no_immediate_liquidity(self):
        result=investment_suggestion(self.finance(),dict(PROFILE,goal='long',horizon_months=120,needs_liquidity=False,emergency_balance_cents=1800000))
        self.assertEqual(result['phase'],'goals');self.assertEqual(len(result['sources']),4)
    def test_profile_validation(self):
        data=dict(goal='emergency',risk='conservative',horizon_months='12',needs_liquidity=True,essential_costs='3000,00',emergency_balance='0,00',reserve_months='6',savings_rate='10',expensive_debt='no')
        self.assertEqual(profile_payload(data)['essential_costs_cents'],300000)
        for key,value in [('savings_rate',51),('essential_costs','0'),('risk','unknown'),('needs_liquidity','true')]:
            with self.assertRaises(ValueError):profile_payload(dict(data,**{key:value}))

if __name__=='__main__':unittest.main()
