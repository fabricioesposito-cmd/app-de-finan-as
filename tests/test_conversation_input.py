import unittest
from app.conversation import parse_message

CARD={'id':'00000000-0000-4000-8000-000000000001','name':'Inter','closing':11,'due':18}

class NaturalExpenseTests(unittest.TestCase):
    def parse(self,message):
        return parse_message(message,[CARD],[],'2026-11-18')

    def test_amount_before_merchant_and_short_date(self):
        d=self.parse('gastei 10,00 no mercado no dia 11/11')
        self.assertEqual((d['amount_cents'],d['date'],d['description'],d['category']),
                         (1000,'2026-11-11','mercado','Mercado'))
        self.assertEqual(d['month'],'2026-11')

    def test_screenshot_market_full_date(self):
        d=self.parse('comprei 55,42 no cartão inter no dia 12/11/2026 mercado')
        self.assertEqual((d['amount_cents'],d['date'],d['description'],d['category'],d['month']),
                         (5542,'2026-11-12','mercado','Mercado','2026-12'))

    def test_screenshot_uber_short_date(self):
        d=self.parse('comprei 17,34 no cartão inter no dia 16/11 uber')
        self.assertEqual((d['amount_cents'],d['date'],d['description'],d['category'],d['month']),
                         (1734,'2026-11-16','uber','Transporte','2026-12'))

    def test_single_digit_date_and_two_digit_year(self):
        self.assertEqual(self.parse('gastei 10 no mercado dia 1/2/26')['date'],'2026-02-01')

    def test_date_is_never_money(self):
        self.assertIsNone(self.parse('gastei no mercado dia 11/11')['amount_cents'])

    def test_invalid_date_and_ambiguous_money(self):
        for text in ['gastei 10 no mercado dia 31/11','gastei 10,00 no mercado e 20,00 no uber']:
            with self.assertRaises(ValueError):self.parse(text)

    def test_installment_count_is_not_money(self):
        d=self.parse('comprei geladeira por 1200 em 6x no cartão inter dia 12/11')
        self.assertEqual((d['amount_cents'],d['installments'],d['description']),(120000,6,'geladeira'))
