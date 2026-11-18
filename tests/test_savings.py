import unittest
from unittest.mock import patch
from app.savings import savings_plan
from app.snapshot import snapshot

class SavingsTests(unittest.TestCase):
    def test_starts_in_selected_month_and_continues_indefinitely(self):
        schedules=[dict(start_month='2026-12',amount_cents=50000)]
        self.assertEqual(savings_plan([],schedules,'2026-11')[0],{})
        for month in ['2026-12','2027-01','2030-01']:
            self.assertEqual(savings_plan([],schedules,month)[0]['savings_target_cents'],50000)

    def test_changes_pause_and_month_exception(self):
        schedules=[dict(start_month='2026-11',amount_cents=50000),dict(start_month='2027-01',amount_cents=80000),dict(start_month='2027-03',amount_cents=0)]
        plans=[dict(month='2027-02',savings_target_cents=10000,saved_cents=20000,opening_cents=15000,savings_override=True)]
        self.assertEqual(savings_plan(plans,schedules,'2026-12')[0]['savings_target_cents'],50000)
        self.assertEqual(savings_plan(plans,schedules,'2027-01')[0]['savings_target_cents'],80000)
        plan,_,override=savings_plan(plans,schedules,'2027-02')
        self.assertEqual(plan['savings_target_cents'],10000);self.assertTrue(override)
        self.assertEqual((plan['saved_cents'],plan['opening_cents']),(20000,15000))
        self.assertEqual(savings_plan(plans,schedules,'2027-03')[0]['savings_target_cents'],0)
        self.assertEqual(plans[0]['savings_target_cents'],10000)

    def test_legacy_target_replaced_but_saved_is_not_repeated(self):
        plans=[dict(month='2026-11',savings_target_cents=20000,saved_cents=60000)]
        schedules=[dict(start_month='2026-11',amount_cents=50000)]
        p,_,_=savings_plan(plans,schedules,'2026-11')
        self.assertEqual((p['savings_target_cents'],p['saved_cents']),(50000,60000))
        self.assertNotIn('saved_cents',savings_plan(plans,schedules,'2026-12')[0])

    def test_snapshot_budget_and_horizon_reserve_once(self):
        fixtures={'savings_schedules':[dict(start_month='2026-11',amount_cents=50000)],'cash_items':[dict(id='income',kind='income',description='Receita',category='Outras receitas',amount_cents=100000,due_date='2026-11-01',settled=True)],'monthly_plans':[dict(month='2026-11',saved_cents=60000)]}
        def get(path,token):return fixtures.get(path.split('/')[3].split('?')[0],[])
        with patch('app.snapshot.supabase.all_rows',side_effect=get):data=snapshot('fixture','2026-11')
        self.assertEqual(data['finance']['reserved_cents'],60000)
        self.assertEqual(data['finance']['remaining_cents'],40000)
        self.assertEqual(data['horizon'][1]['savings_target_cents'],50000)
        self.assertEqual(data['planning']['saved_cents'],60000)
