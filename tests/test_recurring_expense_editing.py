import unittest
from unittest.mock import patch
from app.editing import update_recurring_expense
from app.recurrence import occurrences

ID='00000000-0000-4000-8000-000000000001'
BASE=dict(id=ID,description='Compra de teste',category='Compras',kind='expense',channel='card',amount_cents=3333,total_amount_cents=10000,start_month='2026-11',end_month=None,due_day=18,schedule_type='installment',commitment_type='installment',occurrence_count=3,first_installment=2,total_installments=4)
DATA=dict(id=ID,description='Cadastro corrigido',category='Outros',amount='33,33',due_day='20')

class RecurringExpenseEditingTests(unittest.TestCase):
    def edit(self,rule,data=DATA):
        row=dict(rule)
        def request(path,method='GET',data=None,token=None):
            self.assertEqual(token,'owner-token')
            if method=='PATCH':row.update(data)
            return [row]
        with patch('app.editing.supabase.request',side_effect=request):return update_recurring_expense(data,'owner-token')

    def test_metadata_edit_preserves_uneven_installment_cents_and_numbering(self):
        saved=self.edit(BASE)
        self.assertEqual(saved['total_amount_cents'],10000)
        rows=[occurrences([saved],[],m)[0] for m in ['2026-11','2026-12','2027-01']]
        self.assertEqual([r['amount_cents'] for r in rows],[3334,3333,3333])
        self.assertEqual([r['current'] for r in rows],[2,3,4])
        self.assertEqual(sum(r['amount_cents'] for r in rows),10000)
        self.assertFalse(occurrences([saved],[],'2027-02'))

    def test_new_installment_amount_preserves_count_and_month_exception(self):
        saved=self.edit(BASE,dict(DATA,amount='40,00'))
        self.assertEqual(saved['total_amount_cents'],12000)
        self.assertEqual(saved['occurrence_count'],3)
        row=occurrences([saved],[dict(rule_id=ID,month='2026-12',amount_override_cents=3500,status='realized')],'2026-12')[0]
        self.assertEqual(row['amount_cents'],3500)
        self.assertTrue(row['settled'])

    def test_subscription_stays_subscription_when_category_changes(self):
        rule=dict(BASE,schedule_type='monthly',commitment_type=None,category='Assinaturas',total_amount_cents=None,occurrence_count=None)
        saved=self.edit(rule)
        self.assertEqual(saved['commitment_type'],'subscription')
        self.assertEqual(saved['category'],'Outros')

    def test_excessive_installment_total_is_rejected(self):
        with self.assertRaises(ValueError):self.edit(dict(BASE,occurrence_count=600),dict(DATA,amount='90.000.000.000,00'))
