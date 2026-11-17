import unittest
from collections import Counter
from app.domain import cents, parse_csv, reconcile, fingerprint, future_commitment

class FinancialTests(unittest.TestCase):
    def test_money_is_exact(self):
        self.assertEqual(cents('1.234,56'),123456)
        self.assertEqual(cents('0,10')+cents('0,20'),30)
        for value in ['NaN','1,001','Infinity']:
            with self.assertRaises(ValueError): cents(value)

    def test_import_refund_and_installment(self):
        rows=parse_csv(b'data;descricao;valor;parcela;tipo\n2026-11-01;Loja;120,00;2/5;compra\n2026-11-02;Loja;15,00;;estorno\n')
        self.assertEqual(reconcile(rows,10500),0)
        self.assertEqual(reconcile(rows,10000),500)
        self.assertEqual(future_commitment(rows),36000)

    def test_duplicate_counts_preserve_legitimate_repeated_purchases(self):
        rows=parse_csv(b'data,descricao,valor\n2026-11-01,Loja,10.00\n2026-11-01,Loja,10.00\n')
        self.assertEqual(Counter(map(fingerprint,rows))[fingerprint(rows[0])],2)

    def test_rejects_payment_and_bad_installment(self):
        for data in [b'data;descricao;valor;tipo\n2026-11-01;Pagamento;100;pagamento', b'data;descricao;valor;parcela\n2026-11-01;Loja;10;5/2']:
            with self.assertRaises(ValueError): parse_csv(data)

    def test_bad_headers_and_empty_file(self):
        for data in [b'data,valor\n2026-01-01,10',b'data,descricao,valor\n']:
            with self.assertRaises(ValueError): parse_csv(data)

if __name__=='__main__': unittest.main()
