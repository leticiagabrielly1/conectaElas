# Etapa 4 — Tutora IA

- Chat responsivo, modos de explicação, depuração, linha a linha e dicas.
- Integração com OpenAI Responses API por OPENAI_API_KEY no backend. Sem chave, conteúdo local explicitamente identificado.
- Contexto da próxima aula da trilha, quando disponível e desbloqueada.
- Histórico no SQLite separado por usuário autenticado, com limite de 100 mensagens por conta e botão de exclusão.
- A chave de API nunca é enviada ao navegador. `store=False` na chamada externa.
- Para produção: configurar SECRET_KEY forte, HTTPS, política de retenção e controles de custo/limite por usuário.
