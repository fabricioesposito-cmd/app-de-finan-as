# Clareza — Finanças pessoais

Aplicativo pessoal com dashboard, receitas, contas fixas, assinaturas, parcelamentos, cartões, importação de faturas PDF/CSV, planejamento por planilha, orçamento e registro de gastos por conversa em português.

O dashboard calcula receitas menos custos e a maior entre a meta de reserva e o valor já separado. O saldo inicial das contas é acompanhado separadamente. Compras de cartão afetam o mês da fatura; lançamentos em conta também permitem escolher um mês do orçamento diferente da data. A reserva pode ser recorrente. A conversa usa regras locais e exige revisão antes de gravar.

## Executar no computador

Requer Python 3.9+ (produção usa Python 3.12) e conexão ao Supabase.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PORT=8766 .venv/bin/python -m app.server
```

Abra http://127.0.0.1:8766/. O endereço de loopback funciona apenas no próprio computador. Para outro aparelho no mesmo Wi-Fi, inicie com `HOST=IP_LOCAL_DO_COMPUTADOR` e use esse IP no navegador. Em macOS, descubra-o com `ipconfig getifaddr en0`.

## Publicar no Render

Use o Dockerfile e o Blueprint `render.yaml`, com plano gratuito e banco Supabase existente. A aplicação é servida por Gunicorn/WSGI. As instruções e limitações estão em [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md).

`SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` configuram a conexão. São o endereço e a chave publicável, não uma chave de serviço. Toda operação financeira usa o token do usuário e as políticas RLS do Supabase. O arquivo `config.json` contém apenas a configuração pública usada no desenvolvimento.

## PDF e planilhas

- PDF com texto: pypdf, leitura das tabelas e revisão antes da importação. Há adaptador para faturas Inter.
- PDF digitalizado: macOS usa o helper Vision/PDFKit de `scripts/setup_ocr.sh`; a imagem Linux instala Poppler e Tesseract com português. O OCR é processado no servidor, sem serviços externos.
- XLSX: escolha o arquivo no formulário. O atalho para uma planilha do computador é exclusivo do ambiente local e não é incluído na publicação.
- Limite de arquivo: 5 MB; PDF: até 40 páginas. OCR e layouts desconhecidos exigem conferência.
- Importações, compras e recorrências podem ser vinculadas para evitar duplicação.

## Usar no iPhone

Abra o endereço HTTPS publicado no Safari, toque em Compartilhar → Adicionar à Tela de Início e mantenha Abrir como App da Web ativado, se disponível. O app tem manifesto e ícones próprios; há instruções no botão Instalar app. No endereço público funciona com Wi-Fi ou dados móveis, sem depender do computador. Requer conexão para consultar e salvar; não registra operações offline.

## Validação

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Os testes de banco usam transações revertidas e usuários fictícios. Não publique pastas `work/`, `.venv/`, arquivos `.env`, faturas ou planilhas pessoais. O Dockerfile copia apenas código, assets e exemplos fictícios.

As sugestões de investimento são educativas, dependem do perfil e do orçamento, e não executam aplicações. O app não conecta contas bancárias automaticamente.
