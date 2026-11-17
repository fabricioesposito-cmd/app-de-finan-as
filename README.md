# Clareza — Finanças pessoais

Primeira etapa do app pessoal focado em importar faturas, ler PDFs, conferir lançamentos, categorizar gastos e acompanhar o orçamento mensal.

## Executar

Requer Python 3.9 ou superior e conexão com a internet para acessar o Supabase. A leitura de PDF usa pypdf; o OCR opcional usa Vision/PDFKit do macOS.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# macOS: habilita OCR local para PDFs digitalizados (requer Swift/Command Line Tools)
sh scripts/setup_ocr.sh
.venv/bin/python -m app.server
```

Abra http://127.0.0.1:8765. Crie sua conta pelo formulário; se solicitado, confirme o e-mail antes de entrar. A sessão dura até o vencimento do token do Supabase; reiniciar o servidor exige novo login.

O servidor escuta exclusivamente no computador local. Esta versão não está preparada para exposição direta à internet: hospedagem requer HTTPS, cookies Secure, sessões persistentes com renovação, proteção contra abuso, recuperação de senha e validação adicional de segurança.

## Custos, salário e reserva

A tela inicial **Custos e planejamento** reúne receitas, contas fora dos cartões e faturas. Cadastre o salário, informe o saldo no início do mês, registre pagamentos/recebimentos e defina quanto quer guardar. O painel calcula quanto sobra e quanto fica livre após a reserva; sinaliza falta de dinheiro e faturas ausentes. Você pode editar contas e informar o total a pagar e o pagamento parcial de uma fatura sem duplicar gastos.

O saldo é calculado a partir dos seus registros; não é consulta ao banco. Sem recorrência ou transporte automático de saldos entre meses. Regras e fórmulas em [docs/CUSTOS.md](docs/CUSTOS.md).

## Primeiro uso

1. Cadastre seu cartão em **Cartões e faturas**.
2. Abra **Importar fatura**, selecione cartão e mês e informe o total líquido dos lançamentos.
3. Escolha o PDF da fatura (até 5 MB e 40 páginas), informe a senha se necessário, confira as páginas e ajuste categorias, datas, parcelas, tipos, descrições e valores. Linhas ambíguas ficam pendentes; adicione manualmente as compras não reconhecidas.
4. Marque **Lembrar** para salvar associações de estabelecimento e categoria.
5. Marque a conferência do PDF. Confirme quando a diferença for zero e consulte o painel e o orçamento. O mês selecionado pode ser usado para inferir anos ausentes, sempre com aviso.

O arquivo `examples/fatura-ficticia.pdf`, também disponível para download no app, é totalmente fictício e serve como exemplo de importação PDF. Também é possível importar CSV: `examples/fatura.csv` é totalmente fictício. Seu total líquido é **R$ 473,30**. As colunas obrigatórias são `data`, `descricao` e `valor`; `parcela` e `tipo` são opcionais. Datas aceitas: AAAA-MM-DD ou DD/MM/AAAA. Separadores: ponto e vírgula ou vírgula; valores decimais com vírgula devem estar entre aspas quando o separador também for vírgula. Tipos: compra, estorno, credito, juros, tarifa. Parcelas: 2/5, com valor de uma única parcela.

Pagamentos de fatura, saldo anterior e subtotais não são transações de consumo. CSVs de emissores com outros formatos precisam de adaptação. Não há compatibilidade universal com bancos.

## Implementado

- Cadastro/login pelo Supabase Auth; sessão HttpOnly no servidor local.
- Cartões e importações vinculados ao usuário, com RLS e chaves estrangeiras compostas para impedir vínculos entre usuários.
- Leitura real de PDF textual e CSV no servidor, PDFs com senha e revisão antes de gravar.
- OCR local de páginas sem texto no macOS, com avisos de revisão.
- Preservação de página, linha, descrição extraída e texto original do PDF; edição de parcelas/tipos e inclusão manual.
- Resumos e pagamentos separados das compras; linhas ambíguas expostas para conferência.
- Sugestões de categoria por palavras-chave e regras pessoais, sem IA nesta etapa.
- Confirmação atômica via função SECURITY INVOKER, reconciliação e bloqueio conservador de sobreposição.
- Histórico com exclusão de uma importação e seus lançamentos.
- Gastos por categoria, maiores compras, créditos, juros e tarifas, filtros de cartão/mês e pesquisa por descrição.
- Orçamento por categoria/mês consolidando todos os cartões, exportação CSV e paginação das leituras.

Compras idênticas dentro do mesmo arquivo são preservadas. Uma nova importação com linhas coincidentes com outra do mesmo cartão/mês é bloqueada para revisão; o usuário pode desfazer e substituir a anterior. Não há mesclagem automática de faturas parciais. As regras salvas de categoria sobrevivem ao desfazer.

## Próximas etapas

Classificação com IA, edição em lote, categorias personalizadas, comparação mensal, assinaturas, projeções de parcelas com substituição pelos dados importados, contas bancárias sincronizadas, transferências e recorrências ainda não estão implementados. Registro manual de pagamentos de fatura, contas e receitas já está disponível na área de custos. Não há dados simulados apresentados como reais. O app não está hospedado publicamente.

## Segurança e configuração

`config.json` contém somente URL e chave **publicável** do projeto, nunca chave secreta ou service_role. Autorização ocorre por JWT individual e RLS. Não há logs de faturas ou senhas. O arquivo importado fica apenas em memória durante a leitura, sem retenção do original; persistem as linhas confirmadas. Não envie faturas para o GitHub.

O repositório GitHub foi criado pelo usuário como público. Versione apenas código e exemplos fictícios. `.gitignore` exclui ambientes, arquivos temporários e a pasta `faturas/`, mas não substitui a revisão dos arquivos enviados.

## Validação

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
```

33 testes cobrem planejamento mensal, pagamentos de fatura, metas de reserva, receitas pendentes e também PDF textual, senha, endpoint de prévia, datas inferidas, meses em português, OCR simulado, ambiguidades e domínio financeiro. Os testes de domínio cobrem centavos exatos, valores inválidos, estornos, parcelas, reconciliação, contagem de compras repetidas e rejeição de pagamentos. `tests/database_checks.sql` foi executado no Supabase em transação com rollback: gravação, sobreposição, total divergente, isolamento entre dois usuários e exclusão em cascata. Não executa movimentações bancárias.

A tela de acesso foi conferida no navegador. O fluxo autenticado completo pela interface ainda precisa ser validado com a conta do usuário. Nenhuma fatura real foi utilizada. OCR nativo também foi validado com um PDF fictício rasterizado: cinco lançamentos, total líquido R$ 473,30.

## Limitações da leitura PDF

A leitura agora inclui um adaptador para o layout Inter com tabelas “Despesas da fatura”. Ele lê somente a fatura atual, reconhece datas como “23 de set. 2026”, separa beneficiário, parcelas, créditos e pagamento de fatura anterior, preserva o cartão de origem e confere os subtotais. Resumos, ofertas, próximas parcelas e taxas informativas ficam fora dos lançamentos. O total identificado pode preencher a revisão automaticamente.

Para outros layouts, a extração continua genérica e não garante todos os formatos bancários. Linhas quebradas, múltiplas colunas e moedas podem exigir inclusão manual ou adaptador específico do emissor. A igualdade de totais não prova completude. Revise todas as páginas. PDFs com texto parcial sobre imagens ainda podem exigir OCR externo ou ajuste do adaptador. Sem o helper nativo ou fora do macOS, páginas sem texto geram erro explícito; nunca são ignoradas silenciosamente. A senha é usada em memória para abrir o arquivo e não é armazenada.

Para gerar novamente o exemplo fictício: `.venv/bin/python scripts/create_example.py`.

Arquitetura e plano: [docs/PROJETO.md](docs/PROJETO.md). Estrutura aplicada: [docs/schema.sql](docs/schema.sql).
