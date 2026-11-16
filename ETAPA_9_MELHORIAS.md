# ETAPA 9 — Comunidade

- Publicações categorizadas por linguagem, projetos e conquistas.
- Comentários, curtidas e denúncias autenticadas, persistidos em SQLite.
- Moderação administrativa com fila de denúncias, ocultação e descarte.
- Por segurança, nenhum usuário é administrador automaticamente. Para conceder permissão, um operador autorizado do banco deve inserir o ID na tabela `community_moderators`.
- O feed exibe apenas nome público, conteúdo e data; não exibe e-mail ou telefone.
- Regras de convivência visíveis na página.
- Moderação é reativa e exige revisão humana; não há filtro automático de dados pessoais ou abuso.
- Antes de publicar para menores, configurar HTTPS, chave secreta de produção, CSRF, rate limiting, política de retenção e ferramentas de bloqueio.
