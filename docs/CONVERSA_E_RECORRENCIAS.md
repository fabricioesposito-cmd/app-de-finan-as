# Conversa, recorrências e carga inicial

## Registrar por conversa

A entrada atual é por texto, com interpretação local por regras, sem modelo de IA externo. Exemplos suportados:

- Comprei no supermercado por R$ 120 no cartão principal.
- Comprei uma geladeira por R$ 1.200,00 em 6x no cartão principal.
- Assinei streaming por R$ 39,90 no cartão principal.
- Recebi meu salário de R$ 5.000 na conta principal.
- Quanto posso gastar neste mês?

O app prepara um formulário editável. Nenhum lançamento é gravado antes da confirmação. Cartão ambíguo, valor ausente e descrição incompleta exigem preenchimento. Com múltiplos cartões, a expressão principal só é resolvida automaticamente se coincidir com o nome de um cartão; com apenas um cartão, ele é sugerido. Não existe integração automática com bancos, microfone ou interpretação irrestrita de linguagem.

A data sugerida é a data local de São Paulo; ontem/amanhã e DD/MM/AAAA são reconhecidos. No cartão, o mês é sugerido pelos dias de fechamento e vencimento e pode ser corrigido. Se já fechou, a compra pode comprometer a fatura do mês seguinte. Contas e plataformas são identificadores de origem/destino; o saldo inicial segue consolidado e manual.

O valor de uma compra parcelada é o total. As parcelas são divididas em centavos inteiros; eventuais centavos restantes entram nas primeiras parcelas. A série termina no número informado. Assinaturas e receitas mensais se repetem até o mês de encerramento ou até o usuário encerrá-las. As projeções são calculadas, não gravadas novamente em cada acesso.

Quando existe receita/conta recorrente correspondente, a confirmação permite marcar a previsão como realizada e ajustar seu valor naquele mês, sem criar outra receita/despesa. Uma chave de solicitação impede gravação duplicada por repetição da mesma confirmação.

## Fatura e conciliação

Compras informadas e previsões de cartão comprometem o planejamento imediatamente no mês da fatura. Na revisão da importação, o campo de vínculo permite associá-las a um lançamento real. Sugestões automáticas exigem nome compatível, valor coincidente e data compatível para compras avulsas; ambiguidades ficam para escolha. O mesmo registro não é sugerido automaticamente para duas linhas.

A associação é gravada na mesma transação da importação. O registro real substitui a previsão/compra informada no planejamento e nos relatórios. Também é possível vincular/desvincular uma fatura já importada em Recorrências e contas. Desfazer uma importação remove seus vínculos e volta a exibir previsões e compras informadas.

Parcelas restantes reconhecidas no PDF podem criar previsões futuras a partir do mês seguinte, mantendo a numeração original. Uma assinatura pode ser marcada como mensal na revisão. Se a linha já foi vinculada a uma recorrência, não cria outra série. Projeções criadas pela importação são removidas se ela for desfeita. Pagamento de fatura continua sendo saída de caixa sem gerar uma segunda despesa.

Um total de fatura informado manualmente ajusta a parte importada. Compras e previsões não vinculadas são acrescentadas. Vincule as ocorrências incluídas na fatura ou pule uma previsão para não duplicá-la em um total agregado informado sem detalhamento.

## Importar planilha

A versão atual lê o modelo Custos com meses na linha Mês, receitas, Custos (pagar com Pix), Custos Fixos Cartão e Guardar. Usa valores e resultados de fórmulas já salvos no arquivo. Fórmula sem resultado salvo bloqueia a importação; o app não recalcula o Excel.

A prévia permite escolher o primeiro mês, canal, cartão/conta específicos por item, texto de identificação na fatura e itens ignorados. Alterações mensais de valor e datas de término são preservadas em segmentos recorrentes finitos. Guardar é uma meta, nunca outra despesa. O usuário decide se o status mensal Pago implica receitas recebidas/contas pagas e se substitui metas existentes; saldo inicial e valor já guardado são preservados.

A carga é atômica, bloqueia reimportação do mesmo arquivo e rejeita planejamento/lançamentos manuais sobrepostos com o mesmo nome e período. Para importar uma versão atualizada, selecione meses futuros sem sobreposição ou encerre/revise as previsões anteriores. Sem importação genérica de qualquer planilha, acompanhamento específico de dívida do carro ou transferência automática de saldos.

A planilha anexada neste chat pode ser lida pelo botão correspondente neste computador, mediante configuração local em work. Caminhos, mapeamentos pessoais e arquivos originais não são versionados. O vínculo confirmado pelo usuário entre uma conta da planilha e uma compra do cartão é apresentado na revisão da carga; os dados só entram no Supabase após confirmação no app.

## Validação

54 testes Python cobrem cálculos, PDF, planilha, linguagem suportada, parcelas, término de séries, recebimento, previsão versus lançamento real e não duplicação. Testes SQL com rollback validaram gravação idempotente, RPCs, conciliação atômica, geração de parcelas futuras, desfazer, carga inicial e isolamento de usuários. Dados de teste foram revertidos.

No Chrome temporário, nove áreas foram abertas e foram testadas a confirmação da planilha e a preparação/confirmação de uma compra com atualização do disponível. Esses testes de interface usaram respostas fictícias interceptadas, sem gravar na conta do usuário; a validação com dados reais e login do usuário permanece necessária. Layout conferido em desktop e celular.

Foi corrigida a tela vazia causada por arquivo de interface não servido pelo processo anterior e por campo ausente na resposta de estado. A área de acesso fica visível em falhas iniciais; o painel é mostrado antes da renderização dos módulos e os campos de coleção têm valores padrão.

## Segurança

Novas tabelas usam RLS por usuário e chaves estrangeiras compostas para contas, cartões e vínculos. Funções são SECURITY INVOKER e não usam service_role. Conteúdo de mensagens não é enviado a provedores de IA. Persiste somente o lançamento confirmado, com seus campos financeiros.

Permanece o aviso preexistente do Supabase de [proteção contra senhas vazadas desativada](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection). Não houve alerta de RLS nas novas tabelas. Hospedagem pública ainda exige as melhorias de sessão, HTTPS e proteção contra abuso descritas no README.
