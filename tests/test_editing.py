import unittest
from unittest.mock import patch
from app.editing import update_purchase
from app.snapshot import snapshot

ID='00000000-0000-4000-8000-000000000001'
DATA=dict(id=ID,source='import',description='Mercado corrigido',category='Mercado',amount='55,42',date='2026-11-12')

class EditingTests(unittest.TestCase):
    def test_import_preserves_source_parcels_and_credit_sign(self):
        row={'payload':{'amount':-6000,'current':2,'total':6,'source_page':3}}
        calls=[]
        def request(path,method='GET',data=None,token=None):
            calls.append((path,method,data,token))
            if method=='PATCH':row.update(data)
            return [row]
        with patch('app.editing.supabase.request',side_effect=request):update_purchase(DATA,'owner-token')
        p=row['payload'];self.assertEqual(p['amount'],-5542);self.assertEqual(p['original_amount'],-6000)
        self.assertEqual((p['current'],p['total'],p['source_page']),(2,6,3))
        self.assertTrue(all(c[3]=='owner-token' for c in calls))
        with patch('app.editing.supabase.request',side_effect=request):update_purchase(dict(DATA,amount='50'),'owner-token')
        self.assertEqual(row['payload']['original_amount'],-6000)

    def test_cannot_edit_missing_or_foreign_entry(self):
        with patch('app.editing.supabase.request',return_value=[]):
            with self.assertRaises(ValueError):update_purchase(DATA,'owner-token')

    def test_rejects_linked_event_and_invalid_value(self):
        with patch('app.editing.supabase.request',return_value=[{'id':ID}]):
            with self.assertRaises(ValueError):update_purchase(dict(DATA,source='event',month='2026-12',card_id=ID),'owner-token')
            with self.assertRaises(ValueError):update_purchase(dict(DATA,amount='-10'),'owner-token')

    def test_snapshot_edited_amount_recalculates_available_once(self):
        card=dict(id=ID,name='Inter',closing=11,due=18)
        fixtures={'cards':[card],'imports':[dict(id='batch',month='2026-11',card_id=ID,expected=6000)],'entries':[dict(id='entry',import_id='batch',payload=dict(amount=5542,original_amount=6000,date='2026-11-12',description='Mercado',category='Mercado'))],'cash_items':[dict(id='income',kind='income',description='Receita',category='Outras receitas',amount_cents=100000,due_date='2026-11-01',settled=True)]}
        def get(path,token):return fixtures.get(path.split('/')[3].split('?')[0],[])
        with patch('app.snapshot.supabase.all_rows',side_effect=get):result=snapshot('owner-token','2026-11')
        self.assertEqual(result['finance']['costs_cents'],5542)
        self.assertEqual(result['finance']['remaining_cents'],94458)
        self.assertEqual(result['imports'][0]['original_expected'],6000)
        self.assertTrue(any('editados' in w for w in result['finance']['warnings']))
