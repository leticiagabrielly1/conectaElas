# Etapa 12 — integração e validação

## Fonte e preservação
Base: ZIP da Etapa 11. Código do CodeStart já integrado por `codestart_engine.py` e `curriculo.json`. Dados dos cursos: JSON versionado; progresso, usuários, avaliações, favoritos e certificados: SQLite. **Não houve migração dos cursos do JSON para tabelas SQL**, pois isso exigiria uma migração de dados mais extensa e testes adicionais.

## Alterações desta etapa
- Recuperação de senha com token aleatório de uso único, hash SHA-256 e expiração de 30 minutos. E-mail enviado por SMTP configurável; sem SMTP, o fluxo responde de forma genérica e não expõe tokens.
- Tela de recuperação e redefinição de senha no login.
- Configuração opcional de cookie Secure para HTTPS (`COOKIE_SECURE=1`).
- Testes adicionais para permissões administrativas, recuperação, certificados e catálogo.

## Configuração de produção
Configure `SECRET_KEY` com segredo longo e aleatório, `COOKIE_SECURE=1` com HTTPS, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` e `PUBLIC_BASE_URL`. Sem SMTP a recuperação de senha não envia e-mail. Não publique segredos no Git. Configure `OPENAI_API_KEY` apenas no servidor para tutora externa.

## Testes automatizados
Instale as dependências: `python -m pip install -r requirements.txt`. Rode: `python -m unittest discover -s tests -v`.

## Roteiro manual obrigatório
1. Cadastre uma aluna e entre; saia e entre novamente, verificando a persistência.
2. Solicite recuperação, abra o link recebido e redefina a senha; confirme que o token não pode ser reutilizado.
3. Faça uma aula, verifique progresso e gráficos; saia e entre novamente.
4. Conclua um módulo e confirme desbloqueio; tente abrir módulo bloqueado.
5. Teste tutora sem chave, com chave válida e com conexão indisponível.
6. Tente certificado antes da aprovação, depois emita, abra PDF, imprima e verifique o código.
7. Teste acesso administrativo anônimo, como aluna e como admin autorizado.
8. Confira comunidade, denúncias, oportunidades, editor, mobile e acessibilidade.

## Limitações e pendências
Não foi possível executar os testes Flask neste ambiente por falta das dependências e indisponibilidade de acesso à rede para instalá-las. As verificações de sintaxe são distintas de testes funcionais. A execução de código do laboratório e a revisão de segurança de produção exigem auditoria dedicada. O projeto não deve ser considerado validado para produção apenas com estas verificações.
