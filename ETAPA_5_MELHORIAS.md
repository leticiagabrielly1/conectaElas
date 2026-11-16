# Etapa 5 — Editor interativo

- Editor com numeração de linhas, seleção de linguagem, atalhos e console.
- JavaScript executado apenas em iframe sandbox sem allow-same-origin, com CSP restritiva e limite de espera de 2 segundos. O limite de espera não é um limite de CPU: scripts infinitos ainda podem travar a aba. Para produção, usar isolamento em processo/worker dedicado com quotas.
- HTML/CSS em iframe sandbox sem scripts; SQL somente leitura no motor demonstrativo existente.
- Python, Java e JSON: validação estática existente, sem execução remota.
- Projetos persistidos no SQLite por usuária autenticada, com abertura, edição e exclusão.
- Três desafios JavaScript com testes automáticos no navegador. Resultados do cliente não concedem XP nem certificados porque podem ser falsificados.
- Exercício de aula pode ser carregado com /laboratorio?aula=ID; código inicial é heurístico e pode exigir ajuste da linguagem.
- Destaque de sintaxe ainda não está disponível: o editor fornece fonte monoespaçada, numeração e tema escuro, mas não colorização por token.
- Para hospedagem pública: configurar SECRET_KEY e HTTPS; adicionar CSRF e rate limiting antes de produção.
