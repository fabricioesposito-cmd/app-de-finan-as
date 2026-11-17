# Projeto inicial

## Produto e MVP

App web pessoal em português e reais. O problema central é transformar faturas em uma leitura confiável dos gastos: cartão → arquivo → extração → revisão → categorias → confirmação → painel → orçamento.

O MVP completo incluirá CSV e PDF, análise por cartão/período, compromissos de parcelas futuras e orçamento. A versão atual importa PDF e CSV com persistência Supabase. PDF textual, senha e OCR local no macOS estão implementados; ainda não equivale ao MVP inteiro.

## Premissas e pendências

Uso individual, com isolamento por usuário desde a base. Sem integração bancária, investimentos ou movimentação de dinheiro. O mês da fatura determina o orçamento; a data da compra é preservada separadamente. Sem transferência automática de sobras entre meses.

Ainda precisamos de amostras reais dos emissores para definir adaptadores PDF e CSV. Não é bloqueador para a fatia inicial. Recuperação de senha, publicação, retenção de originais e provedor de IA devem ser definidos antes da etapa correspondente.

## Arquitetura e stack

- Interface HTML/CSS/JavaScript responsiva, sem ferramenta de build nesta etapa.
- Servidor Python com pypdf para PDF, parser CSV, centavos inteiros e cliente REST Supabase; OCR opcional via Vision/PDFKit no macOS.
- Supabase PostgreSQL, Auth e RLS; nenhuma chave privilegiada no app.
- GitHub para versionamento e verificações automatizadas.

A escolha separa domínio, interface e persistência e usa uma dependência principal para leitura PDF. Antes de hospedar, substituir ou endurecer o servidor HTTP de desenvolvimento e implementar gestão de sessões adequada. Um framework pode entrar quando a complexidade justificar.

## Modelo de dados aplicado

| Entidade | Responsabilidade |
|---|---|
| auth.users | Identidade administrada pelo Supabase |
| cards | Dono, emissor, nome, limite em centavos e dias de fechamento/vencimento |
| imports | Dono, cartão, mês da fatura, hash, total informado e criação |
| entries | Dono, importação e payload dos lançamentos revisados |
| category_rules | Associação confirmada de descrição exata e categoria por usuário |
| budgets | Limite em centavos por usuário, mês e categoria |

O payload inclui data da compra, descrição original ou revisada, valor em centavos, tipo, parcela atual/total, categoria e linha do CSV. PDF agora preserva original_description, original_text, source_page, source_line, extraction_method e avisos separadamente dos campos revisados. Evolução: normalizar lançamentos/categorias e acrescentar auditoria.

Futuro: statements para separar fatura de importação; installment_series e parcelas calculadas/importadas; accounts, movements e settlements para receitas, transferências e pagamentos. Pagamento da fatura reduz saldo bancário sem criar consumo novamente. Nenhum desses módulos futuros está ativo.

## Importação e categorização

CSV até 5 MB, UTF-8 ou Windows-1252. Falhas de leitura interrompem a prévia e identificam a linha. Nenhuma gravação ocorre antes da confirmação. Crédito/estorno tem sinal negativo. Pagamentos/subtotais declarados como tipo são rejeitados.

Regras pessoais prevalecem sobre palavras-chave. Sem regra conhecida, usa-se sugestão simples ou Outros. Categorias só entram nos relatórios depois da confirmação. Não existe chamada a IA.

O banco valida acesso, mês, parcelas, valores, tipos e categorias; reconcilia a soma e grava tudo na mesma transação, serializando confirmações da mesma fatura. Bloqueia sobreposição com importações anteriores. Limitação: não oferece aprovação manual de coincidências legítimas entre arquivos diferentes.

PDF implementado: leitura textual por página e OCR para páginas sem texto via helper local do macOS. Até 40 páginas/5 MB, senha opcional, linhas incertas em lista de pendências, resumos separados e reconhecimento de datas numéricas ou meses abreviados em português. Ano ausente é inferido e sinalizado. A confirmação exige aceite de conferência. Adaptadores específicos por emissor e OCR de layouts híbridos continuam pendentes. IA deverá receber o mínimo de dados e tratar o conteúdo do documento como dados sem autoridade para executar instruções.

## Telas e jornadas

- Acesso: criar conta, confirmar e-mail conforme configuração e entrar.
- Cartões: cadastrar e consultar limite/dias; acessar histórico e desfazer importação.
- Importação: cartão, mês, total líquido, upload e tabela revisável; diferença zero habilita confirmação.
- Visão geral: total líquido, créditos, juros/tarifas, categorias e maiores gastos.
- Lançamentos: filtro por cartão/mês, busca e exportação completa.
- Orçamento: limite por mês/categoria e comparação com consumo confirmado de todos os cartões.

## Etapas e aceite

1. **Fatia PDF/CSV — entregue em código:** confirmar arquivo de exemplo por R$ 473,30; impedir divergência e reimportação; manter dados por usuário; desfazer apenas uma importação. Domínio e banco testados; jornada autenticada de interface pendente.
2. **Importação dos emissores reais:** extrair corretamente amostras anonimizadas; reconhecer totais/componentes, registrar texto original e revisões separadamente; testar PDFs textuais e digitalizados. Aceite: todos os lançamentos conferíveis e nenhuma incerteza silenciosa.
3. **Categorias e análise:** regras editáveis, categorias personalizadas, ações em lote, comparação entre meses e IA opcional. Aceite: correções reutilizadas sem tratar sugestões como confirmação.
4. **Parcelas e previsões:** séries, meses futuros e substituição de projeções pela fatura real. Aceite: nenhuma dupla contagem em importações sucessivas; previsões rotuladas como calculadas.
5. **Contas e fluxo de caixa:** saldos, receitas, despesas, transferências, recorrências e pagamentos. Aceite: transferir não cria resultado e pagar fatura não duplica despesas.
6. **Publicação:** HTTPS, cookies Secure, recuperação/renovação de sessão, limitação de tentativas e uploads, backup e validação da jornada em dispositivos. Aceite: autenticação e importação ponta a ponta, RLS testada e revisão de segurança concluída.

## Resultado da validação inicial

Quatorze testes de domínio/PDF passaram. O OCR nativo reconheceu cinco lançamentos de uma fatura fictícia digitalizada, somando R$ 473,30. Transação de teste PostgreSQL completou gravação, duplicidade, divergência de total, isolamento entre usuários e exclusão em cascata, com rollback. Verificação de segurança do Supabase sem alertas na estrutura inicial. Tela de acesso conferida visualmente. PDF validado com exemplos fictícios, incluindo senha e OCR. Sem validação de IA, contas bancárias ou importação de fatura real.
