"""Importa o planejamento mensal da aba Custos; usa valores salvos, não executa fórmulas."""
import io
import zipfile
from datetime import date,datetime
from decimal import Decimal,ROUND_HALF_UP
from hashlib import sha256
from app.domain import normalize,suggest
from app.recurrence import month_distance


def parse_workbook(data,mappings=None):
    from openpyxl import load_workbook
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist())>2000 or sum(i.file_size for i in archive.infolist())>30_000_000:
                raise ValueError('Planilha excede o limite de leitura.')
        book=load_workbook(io.BytesIO(data),data_only=True,read_only=True,keep_links=False)
        formulas=load_workbook(io.BytesIO(data),data_only=False,read_only=True,keep_links=False)
    except ValueError:raise
    except Exception:raise ValueError('Não foi possível abrir o Excel. Envie um arquivo .xlsx válido.')
    try:
        if 'Custos' not in book.sheetnames:raise ValueError('Esta versão lê o modelo com a aba Custos.')
        sheet=book['Custos'];original=formulas['Custos']
        if sheet.max_row>1000 or sheet.max_column>150:raise ValueError('Planilha fora dos limites do modelo.')
        grid=list(sheet.iter_rows());raw=list(original.iter_rows())
        header=next((idx for idx,row in enumerate(grid) if len(row)>1 and normalize(str(row[1].value or ''))=='mes'),None)
        if header is None:raise ValueError('Cabeçalho Mês não encontrado.')
        months=[(idx,cell.value.strftime('%Y-%m')) for idx,cell in enumerate(grid[header]) if isinstance(cell.value,(date,datetime))]
        if not months or len({m for _,m in months})!=len(months):raise ValueError('Meses ausentes ou repetidos no cabeçalho.')
        if any(month_distance(months[i-1][1],months[i][1])!=1 for i in range(1,len(months))):raise ValueError('Os meses precisam estar em sequência.')
        status_row=next((row for row in grid if len(row)>1 and normalize(str(row[1].value or '')).startswith(('satus pgto','status pgto','status pgto'))),None)
        statuses={month:str(status_row[idx].value or '') if status_row else '' for idx,month in months}
        group='income';rows=[];plans=[];warnings=[]
        mappings=mappings or {}
        def amount(rowidx,colidx):
            cell=grid[rowidx][colidx];value=cell.value
            if cell.data_type=='e':raise ValueError('Erro na célula '+cell.coordinate)
            if value is None:
                if raw[rowidx][colidx].data_type=='f':raise ValueError('Fórmula sem resultado salvo em '+cell.coordinate+'. Abra e salve a planilha no Excel antes de importar.')
                return None
            if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError('Valor não numérico em '+cell.coordinate)
            result=int((Decimal(str(value))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            if result<0:raise ValueError('Valor negativo em '+cell.coordinate+'; revise como crédito ou receita antes de importar.')
            return result
        for index,row in enumerate(grid[header+1:],header+1):
            label=str(row[1].value or '').strip() if len(row)>1 else ''
            if not label:continue
            key=normalize(label)
            if key.startswith('custos (pagar'):group='cash';continue
            if key.startswith('custos fixos cartao'):group='card';continue
            if key in ['total','mes'] or key.startswith('data pgto'):continue
            if key.startswith(('limite do cartao','satus pgto','status pgto')):group=None;continue
            if group is None:continue
            if key=='guardar':
                plans=[{'month':month,'savings_target_cents':amount(index,col) or 0} for col,month in months];continue
            values={month:amount(index,col) for col,month in months}
            if not any(value for value in values.values()):continue
            mapping=mappings.get(key,{})
            kind='income' if group=='income' else 'expense'
            channel=mapping.get('channel') or ('card' if group=='card' else 'cash')
            rows.append(dict(id=str(index+1),description=label,kind=kind,channel=channel,category='Salário' if kind=='income' and key=='salario' else 'Outras receitas' if kind=='income' else suggest(label),match_pattern=mapping.get('match_pattern',label),values=values,source_group=group,mapping_confirmed=bool(mapping)))
        if not rows:raise ValueError('Nenhuma receita ou despesa encontrada no modelo.')
        warnings.append('Os resultados salvos de fórmulas foram lidos; a planilha não é recalculada pelo app.')
        warnings.append('A linha Guardar será importada como meta de reserva, sem virar despesa.')
        return dict(digest=sha256(data).hexdigest(),months=[m for _,m in months],rows=rows,plans=plans,statuses=statuses,warnings=warnings)
    finally:book.close();formulas.close()


def build_rules(preview,choices,card_id,account_id,start_month,honor_status=False):
    choice_map={str(c['id']):c for c in choices}
    rules=[]
    for row in preview['rows']:
        choice=choice_map.get(row['id'],{})
        if choice.get('skip'):continue
        channel=choice.get('channel',row['channel']);pattern=str(choice.get('match_pattern',row['match_pattern']))[:150]
        if channel not in ['cash','card'] or (row['kind']=='income' and channel!='cash'):raise ValueError('Receitas devem entrar em uma conta.')
        selected_card=choice.get('card_id') or card_id
        selected_account=choice.get('account_id') or account_id
        if channel=='card' and not selected_card:raise ValueError('Escolha um cartão para os custos do cartão.')
        segments=[];current=None
        for month in preview['months']:
            if month<start_month:continue
            amount=row['values'].get(month)
            if not amount:current=None;continue
            if current and current['amount_cents']==amount and month_distance(current['end_month'],month)==1:current['end_month']=month
            else:
                current=dict(description=row['description'],kind=row['kind'],channel=channel,category=row['category'],amount_cents=amount,start_month=month,end_month=month,due_day=15,match_pattern=pattern,card_id=selected_card if channel=='card' else None,account_id=selected_account if channel=='cash' else None,settled_months=[]);segments.append(current)
            if honor_status and channel=='cash' and normalize(preview['statuses'].get(month,''))=='pago':current['settled_months'].append(month)
        rules.extend(segments)
    return rules,[p for p in preview['plans'] if p['month']>=start_month]
