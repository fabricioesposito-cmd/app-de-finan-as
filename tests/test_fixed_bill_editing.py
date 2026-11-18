import unittest
from unittest.mock import patch
from app.editing import update_fixed_bill
from app.recurrence import occurrences

ID='00000000-0000-4000-8000-000000000001'
RULE=dict(id=ID,description='Conta teste',kind='expense',channel='cash',category='Outras receitas',amount_cents=17300,due_day=16,start_month='2026-11',end_month=None,schedule_type='monthly',commitment_type='bill',account_id=None)
DATA=dict(id=ID,description='Conta atualizada',category='Outros',amount='200,00',due_day='20')

class FixedBillEditingTests(unittest.TestCase):
    def test_edit_existing_rule_and_preserve_month_overrides(self):
        row=dict(RULE);writes=[]
        def request(path,method='GET',data=None,token=None):
            self.assertIn(ID,path);self.assertEqual(token,'owner-token')
            if method=='PATCH':writes.append(data);row.update(data)
            return [row]
        with patch('app.editing.supabase.request',side_effect=request):saved=update_fixed_bill(DATA,'owner-token')
        self.assertEqual(saved['category'],'Outros');self.assertEqual(saved['amount_cents'],20000)
        self.assertEqual(set(writes[0]),{'description','category','amount_cents','due_day'})
        projected=occurrences([row],[dict(rule_id=ID,month='2026-12',amount_override_cents=15000,status='realized')],'2026-12')[0]
        self.assertEqual((projected['amount_cents'],projected['category'],projected['due_date']),(15000,'Outros','2026-12-20'))
        self.assertTrue(projected['settled'])

    def test_missing_or_wrong_rule_type_is_rejected(self):
        for result in [[],[dict(RULE,kind='income')],[dict(RULE,schedule_type='installment')]]:
            with patch('app.editing.supabase.request',return_value=result):
                with self.assertRaises(ValueError):update_fixed_bill(DATA,'owner-token')

    def test_invalid_fields_and_unpersisted_updates_fail(self):
        for data in [dict(DATA,amount='-10'),dict(DATA,due_day='32'),dict(DATA,category='')]:
            with patch('app.editing.supabase.request',return_value=[dict(RULE)]) as request:
                with self.assertRaises(ValueError):update_fixed_bill(data,'owner-token')
                self.assertEqual(request.call_count,1)
        with patch('app.editing.supabase.request',return_value=[dict(RULE)]):
            with self.assertRaises(ValueError):update_fixed_bill(DATA,'owner-token')
