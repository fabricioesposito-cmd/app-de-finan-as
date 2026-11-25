# Clareza · interface

O painel prioriza o valor disponível e sua composição. Verde escuro representa o resumo principal; superfícies claras separam consulta, cadastros e ações. Valores usam alinhamento e espaçamento consistentes, com texto secundário de contraste legível.

- `static/design.css` organiza o tema visual e suas adaptações por largura, sobre os estilos funcionais existentes de tabelas e formulários.
- `static/experience.js` aplica ícones SVG locais, navegação móvel, atalhos, ajustes recolhíveis e melhorias de teclado. Não realiza chamadas financeiras nem altera cálculos.
- No celular (até 800 px), navegação inferior fixa mantém acesso às cinco áreas. Cabeçalho oferece notificações, instalação e contas/importações. Tabelas preservam os rótulos em cartões por registro.
- Registrar mantém conversa e histórico juntos, com atalhos e filtros combináveis de busca, tipo e mês. O filtro de mês é o mês do orçamento; a data de compra continua visível. Ordem por data de registro preservada.
- O orçamento mantém a reserva recorrente em destaque. Exceções do mês e edição de perfil usam detalhes expansíveis.
- Rotas por fragmento permitem voltar e avançar entre áreas, conservando o mês selecionado. Atalhos de teclado, identificação dos diálogos, foco visível, redução de movimento e acesso direto ao conteúdo integram a interface.

Validação: cinco áreas em 320, 375, 390, 430, 768, 800, 1024 e 1440 px, filtros combinados, estados vazios, navegação de retorno, edição, formulários, tabelas móveis/importações, notificações, tooltips e entrada monetária. Dados fictícios; testes de domínio e CI preservam o cálculo financeiro.
