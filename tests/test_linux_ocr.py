import io
import shutil
import unittest
from app.pdf_import import linux_ocr_page

@unittest.skipUnless(shutil.which('pdftoppm') and shutil.which('tesseract'),'Requires Poppler and Tesseract Portuguese/English')
class LinuxOCRTests(unittest.TestCase):
    def test_scanned_fixture_is_read_without_external_service(self):
        from PIL import Image,ImageDraw,ImageFont
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        image=Image.new('RGB',(1800,800),'white');draw=ImageDraw.Draw(image)
        try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',48)
        except OSError:font=ImageFont.load_default(size=48)
        draw.text((90,150),'11/11 MERCADO TESTE 15,00',fill='black',font=font)
        pdf=io.BytesIO();c=canvas.Canvas(pdf,pagesize=(900,400));c.drawImage(ImageReader(image),0,0,width=900,height=400);c.save()
        text=linux_ocr_page(pdf.getvalue(),1)
        self.assertIn('MERCADO',text.upper());self.assertIn('15,00',text)
