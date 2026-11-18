import unittest
from unittest.mock import patch
from app.planning import item_payload,monthly_summary
from app.editing import update_cash_item

ID='00000000-0000-4000-8000-000000000001'
DRAFT=dict(id=ID,description='Gasto de teste',kind='expense',category='Mercado',amount='15,00',due_date='2026-11-11',month='2026-12',settled=True,account_id=None)

class CashBudgetMonthTests(unittest.TestCase):
    def test_explicit_month_and_legacy_fallback(self):
        item=item_payload(DRAFT)
        self.assertEqual((item['due_date'],item['budget_month']),('2026-11-11','2026-12'))
        self.assertEqual(item_payload({k:v for k,v in DRAFT.items() if k!='month'})['budget_month'],'2026-11')
        with self.assertRaises(ValueError):item_payload(dict(DRAFT,month='2026-13'))

    def test_expense_moves_budget_without_changing_payment_date_or_double_count(self):
        item=dict(item_payload(DRAFT),id=ID)
        november=monthly_summary('2026-11',[item],[],[],[])
        december=monthly_summary('2026-12',[item],[],[],[])
        self.assertEqual(november['costs_cents'],0)
        self.assertEqual(december['costs_cents'],1500)
        self.assertEqual(december['items'][0]['due_date'],'2026-11-11')
        self.assertEqual(november['current_cash_cents'],-1500)
        self.assertEqual(december['current_cash_cents'],0)
        self.assertEqual(november['payable_cents'],0)

    def test_edit_cash_verifies_saved_month_and_preserves_identity(self):
        row=dict(item_payload(DRAFT),id=ID,budget_month='2026-11')
        def request(path,method='GET',data=None,token=None):
            self.assertIn(ID,path);self.assertEqual(token,'owner-token')
            if method=='PATCH':row.update(data)
            return [row]
        with patch('app.editing.supabase.request',side_effect=request):saved=update_cash_item(DRAFT,'owner-token')
        self.assertEqual(saved['budget_month'],'2026-12');self.assertEqual(saved['id'],ID)
        self.assertEqual(saved['amount_cents'],1500)

    def test_missing_or_unpersisted_edit_is_not_reported_as_success(self):
        old=dict(item_payload(DRAFT),budget_month='2026-11')
        for result in [[],[old]]:
            with patch('app.editing.supabase.request',return_value=result):
                with self.assertRaises(ValueError):update_cash_item(DRAFT,'owner-token')

class ManualEntryRouteTests(unittest.TestCase):
    def call_route(self,saved):
        import io,json
        from app.server import Handler,TOKEN
        payload=dict(DRAFT,source='cash',channel='card',kind='expense',amount='15,00',date='2026-11-11',card_id=ID)
        body=json.dumps(payload).encode();handler=object.__new__(Handler)
        handler.path='/api/manual-entry-update';handler.headers={'X-App-Token':TOKEN,'Content-Length':str(len(body))};handler.rfile=io.BytesIO(body);handler.session=lambda:{'token':'owner-token'}
        sent=[];handler.send=lambda value,status=200,*args:sent.append((value,status))
        with patch('app.server.supabase.request',side_effect=[{'id':ID,'channel':'card'},saved]) as request:
            handler.do_POST()
            self.assertEqual(request.call_args_list[0].args[2]['p_data']['month'],'2026-12')
            self.assertEqual(request.call_args_list[0].args[2]['p_id'],ID)
        return sent

    def test_route_confirms_card_and_budget_month(self):
        row=dict(id=ID,description=DRAFT['description'],category='Mercado',amount_cents=1500,month='2026-12',purchase_date='2026-11-11',card_id=ID)
        self.assertTrue(self.call_route([row])[0][0]['ok'])
        row['month']='2026-11'
        result=self.call_route([row])[0]
        self.assertEqual(result[1],400);self.assertIn('error',result[0])
