# ETAPA 11 — Acessibilidade

- Botões A+ e A− agora partem de 16px, ajustam de 12 a 24px e persistem preferência local.
- Alto contraste reforçado em cards, formulários, botões e links.
- Link "Pular para o conteúdo", regiões semânticas e navegação por teclado no menu móvel (Tab, Shift+Tab, Escape).
- Estado de tema, contraste e animações anunciado por ARIA; controles com rótulos.
- Botão para reduzir animações com preferência persistida; respeita `prefers-reduced-motion`.
- Melhorias em foco visível, legibilidade, tamanho dos alvos e descrição dos elementos estáticos.
- Mantidas as dez etapas anteriores, rotas e estrutura SQL.

## Limitações e testes pendentes
Não há certificação WCAG 2.2 nem auditoria completa de todas as telas dinâmicas. É necessário testar com NVDA/VoiceOver, navegação por teclado, zoom de 200%/400%, contraste com ferramenta automatizada, formulários, mensagens e fluxos autenticados. Alguns componentes dinâmicos ainda podem precisar de rótulos e mensagens de erro mais específicas.
