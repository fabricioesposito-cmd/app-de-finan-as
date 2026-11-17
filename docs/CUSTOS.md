# Custos e planejamento mensal

Área inicial do app para acompanhar salário, outras receitas, contas fora dos cartões, faturas e meta de reserva. Dados por usuário no Supabase, com RLS.

## Uso

1. Escolha o mês de referência.
2. Informe saldo disponível no início do mês, excluindo reserva de meses anteriores e antes dos recebimentos/pagamentos do mês.
3. Cadastre salário e outras receitas com data e situação de recebimento.
4. Cadastre contas pagas por Pix, boleto, débito ou dinheiro. Não repita compras já incluídas nas faturas.
5. Importe faturas. Se o valor a pagar incluir saldo anterior/ajustes não importados, preencha o total a pagar na lista de contas. Também é possível informar uma fatura manualmente, antes da importação.
6. Registre quanto já pagou de cada fatura. É apenas controle: o app não movimenta dinheiro.
7. Defina quanto deseja guardar e informe quanto já separou neste mês.

Contas/receitas podem ser editadas, excluídas e marcadas como pagas/recebidas ou pendentes. Não há recorrência automática: cada lançamento pertence à data informada. O saldo inicial não é transportado automaticamente entre meses.

## Cálculos

- Receitas previstas: salário e outras receitas do mês, recebidas ou pendentes.
- Compromissos: contas fora dos cartões + uma fatura por cartão/mês.
- Fatura: total a pagar informado; quando vazio, soma líquida das importações daquele cartão/mês. Pagamento já declarado é preservado como valor mínimo do compromisso mesmo se a importação for desfeita.
- Saldo previsto antes de guardar: saldo inicial + receitas previstas − compromissos.
- Caixa calculado até agora: saldo inicial + recebido − contas pagas − pagamentos de cartões − já guardado.
- Disponível para usar: máximo entre zero e saldo previsto menos o maior entre meta de reserva e valor já guardado. A reserva não é descontada duas vezes.
- Sobra antes de guardar: máximo entre zero e saldo previsto. Não significa recomendação de guardar esse valor, nem reserva efetivamente realizada.
- Déficit e meta sem cobertura aparecem em avisos; o painel não apresenta valor negativo como dinheiro disponível.

Pagamento da fatura não cria uma segunda despesa. Crédito líquido de cartão não vira receita em dinheiro. Vencimentos usam o dia cadastrado no mês de referência, limitado ao último dia do mês. Uma fatura manual continua sendo a fonte do valor a pagar até o usuário limpar esse campo, mesmo após novas importações.

O painel consolida todos os cartões e ignora o filtro específico de cartão. A área de orçamento por categoria continua dedicada aos gastos importados dos cartões. Valores são declarados, sem integração bancária. Faturas/contas faltantes deixam a previsão incompleta; cartão sem fatura/valor informado é sinalizado.

## Estrutura e validação

`cash_items`: receitas/contas com vencimento e situação. `monthly_plans`: saldo inicial, meta e valor já guardado por mês. `card_settlements`: total a pagar opcional e pagamento acumulado por cartão/mês. Índices por usuário, unicidade mensal e chave estrangeira composta impedem vínculo com cartão de outro usuário. Políticas USING/WITH CHECK impedem reassociação de dono.

26 testes de domínio, PDF, API e planejamento passaram, incluindo duplicação de pagamento de fatura, déficit, meta inviável, valores guardados e separação de meses. Teste SQL separado verifica gravação e isolamento com transação/rollback. A validação de interface autenticada com dados reais continua pendente.

O advisor do Supabase identificou aviso de proteção contra senhas vazadas desabilitada na configuração Auth; não é um alerta das tabelas desta entrega. Referência: https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection
