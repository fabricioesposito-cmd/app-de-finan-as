"""Fixtures inteiramente fictícias. Nenhum conteúdo da fatura do usuário é versionado."""
import io
import unittest
from reportlab.pdfgen import canvas
from app.inter_pdf import supports,parse_inter
from app.pdf_import import parse_pdf,parse_pages

HEADER='Data    Movimentação    Beneficiário    Valor'
TABLE='''Despesas da fatura
CARTÃO 0000****1111
{header}
23 de set. 2026    LOJA FICTICIA (Parcela 02 de 06)              -             R$ 100,00
 Principal (R$ 90,00) + Juros (R$ 10,00)
15 de out. 2026    JUROS PIX CREDITO                           -             R$ 5,00
15 de out. 2026    IOF                                         -             R$ 1,00
15 de out. 2026    PAGAMENTO ON LINE                           -           + R$ 50,00
Total CARTÃO 0000****1111                                                   R$ 106,00
CARTÃO 0000****2222
{header}
15 de out. 2026    PIX CRED A VISTA                 BENEFICIARIO FICTICIO    R$ 34,00
29 de out. 2026    LOJA DEVOLUCAO                              -           + R$ 10,00
Total CARTÃO 0000****2222                                                    R$ 34,00
'''.format(header=HEADER)
PAGES=[(1,'Conta Inter\nResumo da fatura\nEncargos rotativos 16,60% Valor financiado R$ 999,00','text'),
       (2,'Opções de parcelamento\n1 + 2 de R$ 333,00\nDespesas do mês R$ 140,00\nValor antecipado R$ 10,00\nFatura atual R$ 130,00','text'),
       (3,TABLE,'text'),
       (4,'Próxima fatura\n23 de nov. 2026 LOJA FICTICIA (Parcela 03 de 06) R$ 100,00','text')]

class InterPDFTests(unittest.TestCase):
    def test_only_current_statement_tables_are_transactions(self):
        self.assertTrue(supports(PAGES))
        result=parse_inter(PAGES)
        self.assertEqual(len(result['rows']),5)
        self.assertEqual(result['transaction_pages'],[3])
        self.assertEqual(result['ignored_pages'],[1,2,4])
        self.assertEqual(result['unresolved'],[])
        self.assertEqual(len(result['excluded']),1)
        self.assertEqual(result['invoice_total_cents'],13000)
        self.assertTrue(all(c['difference_cents']==0 for c in result['reconciliation_checks']))

    def test_signs_installments_interest_and_beneficiary(self):
        result=parse_inter(PAGES)
        first=result['rows'][0]
        self.assertEqual((first['date'],first['current'],first['total']),('2026-09-23',2,6))
        self.assertEqual(first['source_card_last4'],'1111')
        self.assertEqual(len(first['source_details']),1)
        self.assertEqual(result['rows'][1]['kind'],'juros')
        self.assertEqual(result['rows'][1]['amount'],500)
        self.assertEqual(result['rows'][2]['kind'],'tarifa')
        self.assertEqual(result['rows'][3]['beneficiary'],'BENEFICIARIO FICTICIO')
        self.assertEqual(result['rows'][4]['amount'],-1000)
        self.assertEqual(result['net_cents'],13000)

    def test_table_continues_on_next_page_and_repeated_purchases_are_preserved(self):
        text='Despesas da fatura\nCARTÃO 0000****1111\n'+HEADER+'\n15 de out. 2026    LOJA FICTICIA        -        R$ 10,00\n'
        result=parse_inter([(1,'Conta Inter\n'+text,'text'),(2,text,'text')])
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(result['rows'][1]['source_page'],2)

    def test_bad_transaction_stays_pending_but_adverts_do_not(self):
        text=TABLE.replace('R$ 34,00\n29 de','SEM VALOR\n29 de')
        result=parse_inter([(1,'Conta Inter\n'+text,'text')])
        self.assertEqual(len(result['unresolved']),1)
        self.assertEqual(result['unresolved'][0]['page'],1)
        self.assertTrue(any(c['difference_cents']!=0 for c in result['reconciliation_checks']))

    def test_ocr_rows_keep_review_flag(self):
        result=parse_inter([(1,'Conta Inter\n'+TABLE,'ocr')])
        self.assertTrue(all(r['needs_review'] and r['warnings'] for r in result['rows']))

    def test_adapter_is_selected_for_real_generated_pdf(self):
        data=io.BytesIO();c=canvas.Canvas(data,pagesize=(1200,842));c.setFont('Helvetica',10)
        for _,text,_ in PAGES:
            c.setFont('Helvetica',10);y=800
            for line in text.splitlines():c.drawString(30,y,line);y-=20
            c.showPage()
        c.save()
        result=parse_pdf(data.getvalue(),'2026-11')
        self.assertEqual(result['adapter'],'inter')
        self.assertEqual(result['invoice_total_cents'],13000)
        self.assertEqual(result['net_cents'],13000)

    def test_generic_interest_credit_word_is_not_a_refund(self):
        result=parse_pages([(1,'15/10/2026 JUROS PIX CREDITO 5,00','text')],'2026-11')
        self.assertEqual(result['rows'][0]['amount'],500)
        self.assertEqual(result['rows'][0]['kind'],'juros')

if __name__=='__main__':unittest.main()
