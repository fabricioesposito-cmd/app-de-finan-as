import io
import unittest
from unittest.mock import patch
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from app.pdf_import import parse_pages, parse_pdf


def make_pdf(lines=None):
    data=io.BytesIO()
    c=canvas.Canvas(data)
    y=790
    for text in lines or ['02/11/2026 Supermercado Exemplo 250,00','04/11/2026 Restaurante Ficticio 85,90','05/11/2026 Loja Exemplo 02/05 120,00','06/11/2026 Uber Exemplo 32,40','07/11/2026 Estorno Loja Exemplo 15,00','Total desta fatura 473,30']:
        c.drawString(40,y,text);y-=24
    c.save();return data.getvalue()


class PDFTests(unittest.TestCase):
    def test_real_pdf_extraction(self):
        result=parse_pdf(make_pdf(),'2026-11')
        self.assertEqual(len(result['rows']),5)
        self.assertEqual(sum(r['amount'] for r in result['rows']),47330)
        parcel=result['rows'][2]
        self.assertEqual((parcel['current'],parcel['total']),(2,5))
        self.assertEqual(parcel['source_page'],1)
        self.assertIn('Loja Exemplo',parcel['original_text'])
        self.assertEqual(len(result['summaries']),1)

    def test_portuguese_month_names(self):
        result=parse_pages([(1,'02 NOV Restaurante Ficticio 85,90','text')],'2026-11')
        self.assertEqual(result['rows'][0]['date'],'2026-11-02')
        self.assertEqual(result['rows'][0]['description'],'Restaurante Ficticio')

    def test_inferred_year_crosses_december(self):
        result=parse_pages([(1,'28/12 Loja Ficticia 10,00','text')],'2027-01')
        self.assertEqual(result['rows'][0]['date'],'2026-12-28')
        self.assertTrue(result['rows'][0]['warnings'])

    def test_summary_payment_and_foreign_currency_not_silently_imported(self):
        result=parse_pages([(1,'01/11 Pagamento recebido 100,00\n02/11 Loja USD 10,00 55,00\nTaxa sem data 5,00\n03/11 Loja sem valor','text')],'2026-11')
        self.assertEqual(result['rows'],[])
        self.assertEqual(len(result['unresolved']),3)
        self.assertEqual(len(result['summaries']),1)

    def test_credit_sign_and_bad_date(self):
        result=parse_pages([(2,'02/11 Loja Ficticia 10,00 CR\n31/02 Loja 12,00','text')],'2026-11')
        self.assertEqual(result['rows'][0]['amount'],-1000)
        self.assertEqual(len(result['unresolved']),1)

    def test_password_protected_pdf(self):
        writer=PdfWriter();writer.append(PdfReader(io.BytesIO(make_pdf())));writer.encrypt('1234')
        out=io.BytesIO();writer.write(out)
        with self.assertRaisesRegex(ValueError,'senha'):parse_pdf(out.getvalue(),'2026-11')
        self.assertEqual(len(parse_pdf(out.getvalue(),'2026-11','1234')['rows']),5)

    def test_scanned_page_uses_ocr_and_flags_result(self):
        data=io.BytesIO();c=canvas.Canvas(data);c.showPage();c.save()
        with patch('app.pdf_import.ocr_page',return_value='02/11 Loja Ficticia 10,00') as ocr:
            result=parse_pdf(data.getvalue(),'2026-11')
            ocr.assert_called_once()
        self.assertEqual(result['rows'][0]['extraction_method'],'ocr')
        self.assertTrue(result['rows'][0]['needs_review'])

    def test_malformed_and_invalid_month(self):
        for data in [b'not a pdf',b'%PDF-1.7\ninvalid']:
            with self.assertRaises(ValueError):parse_pdf(data,'2026-11')
        with self.assertRaises(ValueError):parse_pages([], '2026-99')

    def test_pdf_preview_endpoint_keeps_metadata(self):
        from app.server import Handler, TOKEN
        handler=object.__new__(Handler);body=make_pdf()
        handler.headers={'X-App-Token':TOKEN,'Content-Length':str(len(body)),'X-Invoice-Month':'2026-11'}
        handler.path='/api/preview-pdf';handler.rfile=io.BytesIO(body)
        captured=[]
        handler.send=lambda data,*args,**kwargs:captured.append(data)
        handler.session=lambda:{'token':'test-only'}
        with patch('app.server.supabase.all_rows',return_value=[]):handler.do_POST()
        self.assertEqual(len(captured[0]['rows']),5)
        self.assertEqual(len(captured[0]['digest']),64)
        self.assertEqual(captured[0]['page_count'],1)

if __name__=='__main__':unittest.main()
