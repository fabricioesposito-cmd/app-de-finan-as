# Resumo diário do Clareza

No iPhone (iOS 16.4 ou superior), abra o Clareza instalado na tela inicial e toque em **Notificações → Ativar neste aparelho → Permitir**. O padrão é **09:00, horário de Brasília**. A mesma tela permite mudar a hora, enviar um teste e desativar somente aquele aparelho. Não há cobrança por mensagem Web Push. A infraestrutura continua sujeita aos limites dos planos gratuitos existentes.

O resumo usa o mês atual de Brasília e o mesmo cálculo `prepare_snapshot`/`financial_view` do painel: receitas, compromissos, gastos variáveis e reserva. Não é saldo bancário em tempo real. Valores aparecem na notificação e podem ser exibidos na tela bloqueada, conforme os ajustes do iPhone.

## Operação

- Preferências por usuário/aparelho em `push_subscriptions`, com RLS por proprietário.
- `pg_cron` chama `private.dispatch_daily_push()` a cada cinco minutos. À hora escolhida, `pg_net` envia ao servidor apenas os dados do proprietário daquela inscrição. Não precisa de sessão ativa, Mac ligado ou aplicativo aberto.
- O servidor reutiliza o cálculo financeiro canônico e criptografa o Web Push com VAPID. Nenhuma chave de serviço Supabase é necessária no Render.
- Chaves `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `PUSH_JOB_SECRET` no ambiente Render. O mesmo segredo HMAC fica no Vault Supabase sob `clareza_push_job_secret`; nunca no GitHub. `VAPID_SUBJECT` opcional usa por padrão a URL pública do app.
- HMAC SHA-256 cobre o corpo exato, com validade de cinco minutos. O endpoint diário não aceita sessões/CSRF como substitutos da assinatura. Só os provedores conhecidos Apple, Google, Mozilla e Microsoft são aceitos como destinos, sempre HTTPS.
- Confirmação de entrega ao provedor via resposta HTTP; não comprova leitura/exibição no aparelho. Respostas 404/410 desativam inscrições expiradas; falhas transitórias permitem até três tentativas separadas por dez minutos, dentro de duas horas do horário escolhido. A tag diária substitui uma eventual repetição no aparelho.
- O servidor gratuito pode demorar para iniciar; horário de entrega é aproximado. Há timeout de dois minutos no agendador. Conexão, Foco e permissões do iPhone também podem atrasar a exibição.
- Recibos internos conservados sete dias; histórico de execuções deste cron conservado três dias. Não há cache offline de APIs, valores, sessões ou telas financeiras no service worker.

## Implantação e verificação

Aplicar `docs/push-notifications.sql`, configurar os segredos em ambos os provedores, publicar o servidor, então ativar:

```sql
select cron.schedule('clareza-daily-push','*/5 * * * *','select private.dispatch_daily_push();');
```

Executar os testes Python, `tests/push_database_checks.sql` e `tests/push_scheduler_checks.sql`. Os testes SQL são transações revertidas: não deixam contas fictícias e não enviam HTTP. O teste do agendador confirma também que o HMAC coincide com os bytes que `pg_net` transmitiria. Conferir o botão de teste em um aparelho real após a concessão de permissão; não é possível autorizar o iPhone a partir do servidor.
