# Clareza — Finanças pessoais

Primeira etapa do app pessoal focado em importar faturas, conferir lançamentos, categorizar gastos e acompanhar o orçamento mensal.

## Executar

Requer Python 3.9 ou superior, sem dependências externas, e conexão com a internet para acessar o Supabase.

```sh
python3 -m app.server
```

Abra http://127.0.0.1:8765. Crie sua conta pelo formulário; se solicitado, confirme o e-mail antes de entrar. A sessão dura até o vencimento do token do Supabase; reiniciar o servidor exige novo login.

O servidor escuta exclusivamente no computador local. Esta versão não está preparada para exposição direta à internet: hospedagem requer HTTPS, cookies Secure, sessões persistentes com renovação, proteção contra abuso, recuperação de senha e validação adicional de segurança.

## Primeiro uso

1. Cadastre seu cartão em **Cartões e faturas**.
2. Abra **Importar fatura**, selecione cartão e mês e informe o total líquido dos lançamentos.
3. Escolha um CSV, confira as linhas e ajuste categorias, datas, descrições e valores.
4. Marque **Lembrar** para salvar associações de estabelecimento e categoria.
5. Confirme quando a diferença for zero e consulte o painel e o orçamento.

O arquivo `examples/fatura.csv` é totalmente fictício. Seu total líquido é **R$ 473,30**. As colunas obrigatórias são `data`, `descricao` e `valor`; `parcela` e `tipo` são opcionais. Datas aceitas: AAAA-MM-DD ou DD/MM/AAAA. Separadores: ponto e vírgula ou vírgula; valores decimais com vírgula devem estar entre aspas quando o separador também for vírgula. Tipos: compra, estorno, credito, juros, tarifa. Parcelas: 2/5, com valor de uma única parcela.

Pagamentos de fatura, saldo anterior e subtotais não são transações de consumo. CSVs de emissores com outros formatos precisam de adaptação. Não há compatibilidade universal com bancos.

## Implementado

- Cadastro/login pelo Supabase Auth; sessão HttpOnly no servidor local.
- Cartões e importações vinculados ao usuário, com RLS e chaves estrangeiras compostas para impedir vínculos entre usuários.
- Leitura real de CSV no servidor e revisão antes de gravar.
- Sugestões de categoria por palavras-chave e regras pessoais, sem IA nesta etapa.
- Confirmação atômica via função SECURITY INVOKER, reconciliação e bloqueio conservador de sobreposição.
- Histórico com exclusão de uma importação e seus lançamentos.
- Gastos por categoria, maiores compras, créditos, juros e tarifas, filtros de cartão/mês e pesquisa por descrição.
- Orçamento por categoria/mês consolidando todos os cartões, exportação CSV e paginação das leituras.

Compras idênticas dentro do mesmo arquivo são preservadas. Uma nova importação com linhas coincidentes com outra do mesmo cartão/mês é bloqueada para revisão; o usuário pode desfazer e substituir a anterior. Não há mesclagem automática de faturas parciais. As regras salvas de categoria sobrevivem ao desfazer.

## Próximas etapas

PDF/OCR, classificação com IA, edição em lote, categorias personalizadas, comparação mensal, assinaturas, projeções de parcelas com substituição pelos dados importados, contas bancárias, pagamento de fatura, transferências e recorrências ainda não estão implementados. Não há dados simulados apresentados como reais. O app não está hospedado publicamente.

## Segurança e configuração

`config.json` contém somente URL e chave **publicável** do projeto, nunca chave secreta ou service_role. Autorização ocorre por JWT individual e RLS. Não há logs de faturas ou senhas. O arquivo importado fica apenas em memória durante a leitura, sem retenção do original; persistem as linhas confirmadas. Não envie faturas para o GitHub.

O repositório GitHub foi criado pelo usuário como público. Versione apenas código e exemplos fictícios. `.gitignore` exclui ambientes, arquivos temporários e a pasta `faturas/`, mas não substitui a revisão dos arquivos enviados.

## Validação

```sh
python3 -m unittest discover -s tests -v
```

Cinco testes de domínio cobrem centavos exatos, valores inválidos, estornos, parcelas, reconciliação, contagem de compras repetidas e rejeição de pagamentos. `tests/database_checks.sql` foi executado no Supabase em transação com rollback: gravação, sobreposição, total divergente, isolamento entre dois usuários e exclusão em cascata. Não executa movimentações bancárias.

A tela de acesso foi conferida no navegador. O fluxo autenticado completo pela interface ainda precisa ser validado com a conta do usuário. Nenhuma fatura real foi utilizada.

Arquitetura e plano: [docs/PROJETO.md](docs/PROJETO.md). Estrutura aplicada: [docs/schema.sql](docs/schema.sql).
