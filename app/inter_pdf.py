"""Adaptador das tabelas 'Despesas da fatura' do Inter. Sem dados pessoais em fixtures."""
import re
from datetime import date
from app.domain import cents, normalize, suggest

MONTHS={'jan':1,'fev':2,'mar':3,'abr':4,'mai':5,'jun':6,'jul':7,'ago':8,'set':9,'out':10,'nov':11,'dez':12}
HEADER=re.compile(r'^data\s+movimentacao\s+beneficiario\s+valor$')
LONG_DATE=re.compile(r'^\s*(\d{1,2})\s+de\s+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\.?\s+(?:de\s+)?(\d{4})\s+(.+)$',re.I)
MONEY=re.compile(r'(?P<sign>[+−-])?[ \t]{0,3}R\$\s*(?P<amount>\d+(?:\.\d{3})*,\d{2})\s*$')


def supports(pages):
    text='\n'.join(normalize(text) for _,text,_ in pages)
    return 'despesas da fatura' in text and any(HEADER.match(line.strip()) for line in text.splitlines()) and ('conta inter' in text or 'banco inter' in text)


def parse_inter(pages):
    rows=[];unresolved=[];summaries=[];excluded=[];table_pages=[];ignored_pages=[];card_totals={}
    invoice_total=None;declared_spending=None;declared_credits=None
    for page_number,text,method in pages:
        lines=text.splitlines()
        # Apenas campos nominais do resumo; simulações nunca fornecem o total de conciliação.
        for i,line in enumerate(lines):
            normalized=normalize(line)
            for label,key in [('fatura atual','invoice'),('despesas do mes','spending'),('valor antecipado','credits')]:
                if re.match(r'^'+label+r'\s+r\$',normalized):
                    value=MONEY.search(line)
                    if value:
                        amount=cents(value['amount'])
                        if key=='invoice':invoice_total=amount
                        elif key=='spending':declared_spending=amount
                        else:declared_credits=amount
            if normalized.strip()=='total da sua fatura':
                for candidate in lines[i+1:i+4]:
                    value=MONEY.search(candidate.strip())
                    if value:invoice_total=cents(value['amount']);break
        if 'despesas da fatura' not in normalize(text):
            ignored_pages.append(page_number);continue
        table_pages.append(page_number);active=False;card=None;previous=None
        for line_number,line in enumerate(lines,1):
            original=line.strip();normalized=normalize(original)
            if not original:continue
            card_match=re.match(r'^cartao\s+\d+\*+(\d{4})\s*$',normalized)
            if card_match:
                card=card_match[1];active=False;previous=None;continue
            if HEADER.match(normalized):
                active=True;continue
            if normalized.startswith('total cartao '):
                value=MONEY.search(original)
                if value and card:card_totals[card]=cents(value['amount'])
                summaries.append(dict(page=page_number,text=original));active=False;previous=None;continue
            if not active:continue
            match=LONG_DATE.match(original)
            if not match:
                if normalized.startswith('principal ('):
                    # O principal e os juros compõem a parcela acima; não são novos lançamentos.
                    if previous:previous.setdefault('source_details',[]).append(original)
                    continue
                if re.match(r'^\d{1,2}\s',normalized) or MONEY.search(original):
                    unresolved.append(dict(page=page_number,line=line_number,text=original,reason='Linha da tabela não reconhecida; confira no documento.'))
                continue
            day,month,year,rest=match.groups()
            value_match=MONEY.search(rest)
            if not value_match:
                unresolved.append(dict(page=page_number,line=line_number,text=original,reason='Valor ausente ou quebrado na tabela.'));previous=None;continue
            try:purchase_date=date(int(year),MONTHS[month.lower()],int(day)).isoformat()
            except ValueError:
                unresolved.append(dict(page=page_number,line=line_number,text=original,reason='Data inválida na tabela.'));previous=None;continue
            columns=re.split(r'\s{2,}',rest[:value_match.start()].strip())
            description=columns[0].strip()
            beneficiary=' '.join(c.strip() for c in columns[1:] if c.strip()!='-') or None
            if normalize(description).startswith(('pagamento','pgto')):
                excluded.append(dict(page=page_number,text=original,reason='Pagamento de fatura; não é consumo deste mês.'));previous=None;continue
            if not description:
                unresolved.append(dict(page=page_number,line=line_number,text=original,reason='Descrição ausente.'));previous=None;continue
            amount=cents(value_match['amount'])
            credit=value_match['sign']=='+'
            amount=-amount if credit else amount
            desc=normalize(description)
            kind='estorno' if credit and any(word in desc for word in ['estorno','devolucao']) else 'credito' if credit else 'juros' if 'juros' in desc else 'tarifa' if any(word in desc for word in ['iof','tarifa','anuidade']) else 'compra'
            current=total=1;warnings=[]
            installment=re.search(r'\bparcela\s+(\d{1,3})\s+de\s+(\d{1,3})\b',desc)
            if installment:
                current,total=map(int,installment.groups())
                if not 1<=current<=total<=120:
                    unresolved.append(dict(page=page_number,line=line_number,text=original,reason='Parcelamento inválido.'));previous=None;continue
            if method=='ocr':warnings.append('Reconhecido por OCR; confira data, sinal e valor.')
            previous=dict(date=purchase_date,description=description,original_description=description,original_text=original,beneficiary=beneficiary,amount=amount,kind=kind,current=current,total=total,category='Juros e tarifas' if kind in ['juros','tarifa'] else suggest(description),source_page=page_number,source_line=line_number,source_card_last4=card,extraction_method=method,warnings=warnings,needs_review=True)
            rows.append(previous)
    gross=sum(r['amount'] for r in rows if r['amount']>0)
    credits=-sum(r['amount'] for r in rows if r['amount']<0)
    net=gross-credits
    checks=[]
    for label,expected,actual in [('Despesas do mês',declared_spending,gross),('Valor antecipado / créditos',declared_credits,credits),('Fatura atual',invoice_total,net)]:
        if expected is not None:checks.append(dict(label=label,expected_cents=expected,actual_cents=actual,difference_cents=actual-expected))
    for card,expected in card_totals.items():
        actual=sum(r['amount'] for r in rows if r['source_card_last4']==card and r['amount']>0)
        checks.append(dict(label='Despesas do cartão final '+card,expected_cents=expected,actual_cents=actual,difference_cents=actual-expected))
    warnings=['Layout Inter identificado. Somente as tabelas de despesas da fatura atual foram lidas. Confira os lançamentos antes de confirmar.']
    if any(c['difference_cents'] for c in checks):warnings.append('Há divergência entre os lançamentos e os totais declarados no PDF. Revise antes de confirmar.')
    if not checks:warnings.append('Totais do resumo não identificados; informe e confira o total manualmente.')
    return dict(rows=rows,unresolved=unresolved,summaries=summaries,excluded=excluded,warnings=warnings,page_count=len(pages),adapter='inter',transaction_pages=table_pages,ignored_pages=ignored_pages,invoice_total_cents=invoice_total,spending_cents=gross,credits_cents=credits,net_cents=net,reconciliation_checks=checks)
