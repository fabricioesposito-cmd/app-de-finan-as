# Publicação do Clareza no Render

## Configuração

- Repositório: `fabricioesposito-cmd/app-de-finan-as`, branch `main`.
- Serviço web Docker, plano `free`, região `virginia`.
- Dockerfile na raiz. O comando padrão inicia `gunicorn --config gunicorn.conf.py app.wsgi:application`.
- `/healthz` responde sem depender de autenticação ou chamadas ao banco.
- `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY`: usar a configuração pública do projeto existente. Nunca usar `service_role`.
- `SECURE_COOKIES=1`: cookies de sessão apenas em HTTPS.
- O esquema necessário já foi aplicado ao Supabase conectado. Os SQLs em docs documentam as mudanças; não os execute novamente sem verificar o histórico.

## Sessões e limites

Uma única instância/processo Gunicorn, com quatro threads. Sessões e prévias de importação ficam na memória do processo; os registros financeiros ficam no Supabase. Não aumente workers ou instâncias sem mover as sessões e prévias para um armazenamento compartilhado.

O token Supabase é renovado no servidor dentro da sessão de até sete dias. Reiniciar ou suspender o serviço remove as sessões e prévias e exige novo login; não remove os lançamentos. O plano gratuito pode suspender o serviço por inatividade. Por isso, a primeira abertura pode demorar e pedir login novamente.

Sem gravar os PDFs no repositório. O OCR usa arquivos temporários removidos após a operação. A imagem Docker inclui Poppler e Tesseract português/inglês. OCR de documentos extensos pode ultrapassar o tempo da requisição; prefira PDFs com texto quando disponíveis.

## Verificação após publicação

1. `/healthz`, página de login, manifesto e ícones respondem via HTTPS.
2. Sem sessão, `/api/state` não retorna dados financeiros.
3. O login grava cookie HttpOnly/SameSite/Secure e usa RLS para acessar o próprio usuário.
4. Conferir receitas, despesas, metas recorrentes, edição, mês da fatura e importações usando uma conta de teste. Não duplicar importações reais para testar.
5. No iPhone, adicionar o endereço publicado à tela inicial. O ícone anterior do IP local continua apontando para o computador; substituí-lo pelo endereço definitivo.

Referências: https://render.com/docs/docker e https://render.com/docs/free
