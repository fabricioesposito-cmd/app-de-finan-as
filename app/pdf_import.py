"""Extração conservadora: nenhum layout desconhecido é tratado como completo."""
import io
import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from app.domain import cents, normalize, suggest

MAX_PAGES = 40
DATE = re.compile(r'^\s*(\d{2})[/-](\d{2})(?:[/-](\d{4}|\d{2}))?\s+(.+)$')
AMOUNT = re.compile(r'(?<![\d/])(?:R\$\s*)?[−-]?\s*\d{1,3}(?:\.\d{3})*,\d{2}\s*(?:[-−]|CR|C)?\s*$', re.I)
SUMMARY = re.compile(r'^(?:total\b|subtotal\b|saldo\s+anterior\b|pagamento\b|pagamentos\b|limite\b|valor\s+(?:total|minimo)\b|resumo\b)', re.I)


def parse_pages(pages, month):
    try:
        reference = date.fromisoformat(month + '-01')
    except (ValueError, TypeError):
        raise ValueError('Selecione o mês da fatura antes de ler o PDF.')
    rows, unresolved, summaries = [], [], []
    for page_number, text, method in pages:
        lines = text.splitlines()
        for line_number, original in enumerate(lines, 1):
            original = original.strip()
            if not original:
                continue
            normalized = normalize(original)
            month_names = {'jan':1,'fev':2,'mar':3,'abr':4,'mai':5,'jun':6,'jul':7,'ago':8,'set':9,'out':10,'nov':11,'dez':12}
            named = re.match(r'^(\d{2})\s+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\.?\s+(?:(\d{4})\s+)?(.+)$', normalized)
            parse_line = original
            if named:
                d, m, y, remainder = named.groups()
                # Preserve o texto original; apenas o prefixo de data é normalizado.
                prefix = re.match(r'^\d{2}\s+\w+\.?\s+(?:\d{4}\s+)?', original, re.I)
                parse_line = d + '/' + str(month_names[m]).zfill(2) + ('/' + y if y else '') + ' ' + original[prefix.end():]
            if SUMMARY.match(normalized):
                if AMOUNT.search(original):
                    summaries.append(dict(page=page_number, text=original))
                continue
            match = DATE.match(parse_line)
            if not match:
                if AMOUNT.search(original):
                    unresolved.append(dict(page=page_number, line=line_number, text=original, reason='Valor sem data de compra reconhecida; confira se é lançamento ou resumo.'))
                continue
            day, mon, year, rest = match.groups()
            warnings = []
            if not year:
                inferred = reference.year - (int(mon) > reference.month)
                warnings.append('Ano inferido pelo mês da fatura; confirme a data.')
            else:
                inferred = int(year) + (2000 if len(year) == 2 else 0)
            try:
                purchase_date = date(inferred, int(mon), int(day)).isoformat()
            except ValueError:
                unresolved.append(dict(page=page_number, line=line_number, text=original, reason='Data inválida.')); continue
            value_match = AMOUNT.search(rest)
            if not value_match:
                unresolved.append(dict(page=page_number, line=line_number, text=original, reason='Valor não reconhecido ou linha quebrada; adicione manualmente.')); continue
            description = rest[:value_match.start()].strip()
            # Duas colunas ou mais de uma moeda exigem intervenção, sem escolher um valor às cegas.
            if re.search(r'\d+[,.]\d{2}\b', description):
                unresolved.append(dict(page=page_number, line=line_number, text=original, reason='Mais de uma data ou valor na linha; confira as colunas e adicione manualmente.')); continue
            if SUMMARY.match(normalize(description)):
                summaries.append(dict(page=page_number,text=original)); continue
            raw_value = value_match.group().strip().replace('−','-')
            credit = raw_value.endswith(('-', 'CR', 'cr', 'C', 'c')) or raw_value.lstrip().startswith('-')
            raw_value = re.sub(r'(?:CR|C|-)\s*$', '', raw_value, flags=re.I).strip()
            try:
                value = cents(raw_value)
            except ValueError:
                unresolved.append(dict(page=page_number,line=line_number,text=original,reason='Valor inválido.')); continue
            desc_normalized = normalize(description)
            if any(term in desc_normalized for term in ['estorno','credito','devolucao']):
                credit = True
            kind = 'estorno' if 'estorno' in desc_normalized else 'credito' if credit else 'juros' if 'juros' in desc_normalized else 'tarifa' if any(t in desc_normalized for t in ['tarifa','anuidade']) else 'compra'
            value = -abs(value) if credit else abs(value)
            current, total = 1, 1
            installment = re.search(r'\b(?:parc(?:ela)?\.?\s*)?(\d{1,3})\s*/\s*(\d{1,3})\b', description, re.I)
            if installment:
                current, total = map(int, installment.groups())
                if not 1 <= current <= total <= 120:
                    unresolved.append(dict(page=page_number,line=line_number,text=original,reason='Parcelamento inválido.')); continue
                warnings.append('Parcelamento extraído da descrição; confirme se corresponde à parcela atual.')
            if not description:
                unresolved.append(dict(page=page_number,line=line_number,text=original,reason='Descrição ausente.')); continue
            if method == 'ocr':
                warnings.append('Reconhecido por OCR; confira caracteres, sinal e valor.')
            rows.append(dict(date=purchase_date,description=description,original_description=description,original_text=original,amount=value,kind=kind,current=current,total=total,category='Juros e tarifas' if kind in ['juros','tarifa'] else suggest(description),source_page=page_number,source_line=line_number,extraction_method=method,warnings=warnings,needs_review=True))
    return dict(rows=rows,unresolved=unresolved,summaries=summaries,warnings=['Extração genérica. Confira todas as páginas; a conciliação de totais não garante que todas as compras foram identificadas.'],page_count=len(pages))


def ocr_page(data, page_number, password=''):
    helper = Path(__file__).resolve().parent.parent / 'work' / 'pdf-ocr'
    if sys.platform != 'darwin' or not helper.is_file():
        raise ValueError('Este PDF contém página digitalizada. O OCR local precisa ser instalado: consulte o README.')
    with tempfile.TemporaryDirectory(prefix='clareza-ocr-') as folder:
        source = Path(folder) / 'invoice.pdf'
        source.write_bytes(data)
        try:
            result = subprocess.run([str(helper), str(source), str(page_number)], input=password, text=True, capture_output=True, timeout=60, check=True)
            return json.loads(result.stdout)['text']
        except (subprocess.SubprocessError, ValueError, KeyError):
            raise ValueError('O OCR não conseguiu ler uma página do PDF. Tente uma cópia com melhor resolução.')


def parse_pdf(data, month, password=''):
    if not data.startswith(b'%PDF-'):
        raise ValueError('O arquivo enviado não é um PDF válido.')
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError('Instale as dependências PDF: python -m pip install -r requirements.txt')
    pages = []
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted and not reader.decrypt(password):
            raise ValueError('PDF protegido: informe a senha correta para abrir a fatura.')
        if not 0 < len(reader.pages) <= MAX_PAGES:
            raise ValueError('Importe PDFs com até 40 páginas.')
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text(extraction_mode='layout') or ''
            method = 'text'
            if len(re.sub(r'\s','',text)) < 20:
                text = ocr_page(data, number, password)
                method = 'ocr'
            pages.append((number, text, method))
    except ValueError:
        raise
    except Exception:
        raise ValueError('Não foi possível ler o PDF. Verifique a senha e se o arquivo está íntegro.')
    result = parse_pages(pages, month)
    if not result['rows']:
        result['warnings'].append('Nenhum lançamento identificado automaticamente. Use as linhas pendentes para adicionar compras manualmente ou valide o layout do emissor.')
    return result
