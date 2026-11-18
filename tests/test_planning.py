import io
import json
import unittest
from unittest.mock import patch
from app.planning import monthly_summary, item_payload

CARD={'id':'card1','name':'Cartão exemplo','due':31}
def item(kind,amount,settled=False,month='2026-11'):
    return dict(id='test',kind=kind,amount_cents=amount,settled=settled,due_date=month+'-05')
def bill(amount,month='2026-11'):
    return dict(card_id='card1',month=month,expected=amount)
def payment(amount,total=None):
    return dict(card_id='card1',month='2026-11',paid_cents=amount,bill_total_cents=total)

class PlanningTests(unittest.TestCase):
    def summary(self,items=None,imports=None,payments=None,plan=None):
        return monthly_summary('2026-11',items or [],imports or [],[CARD],payments or [],plan)

    def test_salary_costs_and_savings(self):
        s=self.summary([item('income',800000),item('expense',250000)],[bill(150000)],plan={'opening_cents':100000,'savings_target_cents':200000})
        self.assertEqual(s['costs_cents'],400000)
        self.assertEqual(s['forecast_cents'],500000)
        self.assertEqual(s['free_to_use_cents'],300000)
        self.assertEqual(s['payable_cents'],400000)
        self.assertEqual(s['current_cash_cents'],100000)

    def test_card_payment_is_not_another_expense(self):
        s=self.summary([item('income',800000,True),item('expense',250000,True)],[bill(150000)],[payment(150000)])
        self.assertEqual(s['costs_cents'],400000)
        self.assertEqual(s['forecast_cents'],400000)
        self.assertEqual(s['current_cash_cents'],400000)
        self.assertEqual(s['payable_cents'],0)

    def test_pending_income_not_in_current_cash(self):
        s=self.summary([item('income',500000),item('expense',100000,True)])
        self.assertEqual(s['current_cash_cents'],-100000)
        self.assertEqual(s['forecast_cents'],400000)
        self.assertEqual(s['receivable_cents'],500000)

    def test_deficit_and_unaffordable_target(self):
        s=self.summary([item('income',100000),item('expense',150000)],plan={'savings_target_cents':20000})
        self.assertEqual(s['shortfall_cents'],50000)
        self.assertEqual(s['free_to_use_cents'],0)
        self.assertEqual(s['can_save_cents'],0)
        s=self.summary([item('income',100000)],plan={'savings_target_cents':150000})
        self.assertEqual(s['savings_gap_cents'],50000)
        self.assertEqual(s['free_to_use_cents'],0)

    def test_saved_money_reserved_only_once(self):
        s=self.summary([item('income',500000,True)],plan={'savings_target_cents':200000,'saved_cents':100000})
        self.assertEqual(s['free_to_use_cents'],300000)
        self.assertEqual(s['current_cash_cents'],400000)

    def test_credit_does_not_create_cash_and_month_isolation(self):
        s=self.summary([item('income',900000,True,'2026-10')],[bill(-5000),bill(100000,'2026-10')])
        self.assertEqual(s['card_cents'],0)
        self.assertEqual(s['income_cents'],0)
        self.assertEqual(s['forecast_cents'],0)
        self.assertEqual(s['bills'][0]['due_date'],'2026-11-30')

    def test_partial_payment_and_invoice_total_override(self):
        s=self.summary([item('income',500000)],[bill(100000),bill(50000)],[payment(80000,200000)])
        self.assertEqual(s['card_cents'],200000)
        self.assertEqual(s['payable_cents'],120000)
        self.assertEqual(s['costs_cents'],200000)
        self.assertEqual(s['forecast_cents'],300000)

    def test_undo_import_does_not_erase_real_payment(self):
        s=self.summary(payments=[payment(10000)])
        self.assertEqual(s['current_cash_cents'],-10000)
        self.assertEqual(s['costs_cents'],10000)
        self.assertEqual(s['payable_cents'],0)

    def test_missing_cards_are_explicit(self):
        self.assertEqual(self.summary()['missing_cards'],['Cartão exemplo'])
        self.assertEqual(self.summary()['missing_card_ids'],['card1'])

    def test_item_validation(self):
        data=dict(description='Salário',kind='income',category='Salário',amount='8.000,00',due_date='2026-11-05',settled=False)
        self.assertEqual(item_payload(data)['amount_cents'],800000)
        for field,value in [('amount','-10'),('due_date','2026-02-31'),('settled','false'),('kind','transfer')]:
            with self.assertRaises(ValueError):item_payload(dict(data,**{field:value}))

    def test_save_route_does_not_convert_pending_string_to_true(self):
        from app.server import Handler,TOKEN
        handler=object.__new__(Handler)
        body=json.dumps(dict(description='Salário',kind='income',category='Salário',amount='100,00',due_date='2026-11-05',settled=False)).encode()
        handler.path='/api/cash-item';handler.headers={'X-App-Token':TOKEN,'Content-Length':str(len(body))};handler.rfile=io.BytesIO(body);handler.session=lambda:{'token':'fixture'}
        sent=[];handler.send=lambda value,*args:sent.append(value)
        with patch('app.server.supabase.request') as request:
            handler.do_POST()
            self.assertFalse(request.call_args.args[2]['settled'])
        self.assertTrue(sent[0]['ok'])

    def test_state_route_returns_month_summary(self):
        from app.server import Handler
        handler=object.__new__(Handler);handler.path='/api/state?month=2026-11';handler.session=lambda:{'token':'fixture','email':'fixture@example.invalid'}
        fixtures={'cards':[CARD],'imports':[dict(bill(150000),id='batch1')],'cash_items':[dict(item('income',800000),description='Salário',category='Salário'),dict(item('expense',250000),description='Conta',category='Outros')],'monthly_plans':[{'month':'2026-11','opening_cents':100000,'savings_target_cents':200000}]}
        sent=[];handler.send=lambda value,*args:sent.append(value)
        def get(path,token):return fixtures.get(path.split('/')[3].split('?')[0],[])
        with patch('app.server.supabase.all_rows',side_effect=get):handler.do_GET()
        self.assertEqual(sent[0]['planning']['free_to_use_cents'],300000)
        self.assertEqual(sent[0]['planning']['month'],'2026-11')

if __name__=='__main__':unittest.main()
