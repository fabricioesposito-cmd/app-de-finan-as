"""Gera somente uma fatura fictícia para validar a importação PDF."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

root=Path(__file__).resolve().parent.parent
output=root/'examples'/'fatura-ficticia.pdf'
c=canvas.Canvas(str(output),pagesize=(595,842))
c.setFillColor(HexColor('#163d30'));c.rect(0,710,595,132,fill=1,stroke=0)
c.setFillColor(HexColor('#ffffff'));c.setFont('Helvetica-Bold',26);c.drawString(40,786,'clareza | fatura de exemplo')
c.setFont('Helvetica',12);c.drawString(40,756,'DADOS FICTICIOS - Novembro de 2026')
c.setFillColor(HexColor('#243c36'));c.setFont('Helvetica',12)
y=665
for line in ['Data                 Descricao                                            Valor (R$)', '02/11/2026    Supermercado Exemplo                          250,00', '04/11/2026    Restaurante Ficticio                                85,90','05/11/2026    Loja Exemplo 02/05                               120,00','06/11/2026    Uber Exemplo                                          32,40','07/11/2026    Estorno Loja Exemplo                             15,00','Total desta fatura                                                         473,30']:
 c.drawString(40,y,line);y-=32
c.setFont('Helvetica',10);c.drawString(40,100,'Este documento nao pertence a um banco. Use somente para testar o aplicativo.')
c.save()
print(output)
