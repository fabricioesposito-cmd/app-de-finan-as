import unittest
from unittest.mock import patch
from app.snapshot import snapshot

class RegistrationSnapshotTests(unittest.TestCase):
    def test_import_registration_comes_from_row_metadata_not_payload(self):
        fixtures={'cards':[dict(id='card',name='Test',closing=11,due=18)],'imports':[dict(id='batch',card_id='card',month='2026-12',expected=1500,created_at='2026-11-20T14:00:00Z')],'entries':[dict(id='entry',import_id='batch',registered_at='2026-11-20T14:00:00Z',payload=dict(description='Test',category='Mercado',date='2026-11-01',amount=1500,registered_at='2030-01-01T00:00:00Z'))]}
        def get(path,token):return fixtures.get(path.split('/')[3].split('?')[0],[])
        with patch('app.snapshot.supabase.all_rows',side_effect=get):result=snapshot('test-token','2026-12')
        row=next(e for e in result['entries'] if e['id']=='entry')
        self.assertEqual(row['registered_at'],'2026-11-20T14:00:00Z')
        self.assertEqual(row['date'],'2026-11-01')
