# ETAPA 10 — Painel administrativo

- Acesse `/administracao`. Somente contas presentes na tabela SQLite `admins` podem usar as rotas `/data/admin/*`.
- Não existe administrador padrão nem senha embutida. Para autorizar uma conta, primeiro cadastre-a normalmente, pare o servidor e execute, na pasta do projeto:

```bash
python -c "import sqlite3; c=sqlite3.connect('conectas.db'); print(c.execute('SELECT id,email FROM users').fetchall()); c.close()"
```

Após identificar o ID da conta que será administradora, substitua `ID_AUTORIZADO` pelo número correspondente:

```bash
python -c "import sqlite3; c=sqlite3.connect('conectas.db'); c.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(ID_AUTORIZADO,)); c.commit(); c.close()"
```

- Indicadores: contas cadastradas, estudantes com aulas concluídas, cursos, certificados, acessos a cursos (contados a partir da atualização), erros em avaliações e denúncias pendentes. Taxa exibida é certificados emitidos / (alunas × cursos), não uma taxa de conclusão por matrícula.
- Cursos: criar e editar metadados, módulos por agrupamento e aulas com questão e alternativas. As alterações são persistidas em `admin_course_data` (SQLite) e recarregadas ao iniciar o aplicativo.
- Oportunidades: cadastrar e editar vagas demonstrativas. O sistema não verifica fontes reais externas.
- Moderação: denúncias pendentes, ocultação e dispensa.
- Certificados: listagem e revogação; revogados não são autenticados nem baixados pelo endpoint público.
- Todas as mutações administrativas são auditadas em `admin_audit`.

## Limitações e testes pendentes

- Ainda não há exclusão de cursos/aulas, ordenação por arrastar, editor visual de módulos, gestão de permissões pela interface ou validação de fontes de vagas reais.
- O formulário de aulas permite editar questões individuais; a avaliação final do módulo continua usando a estrutura preexistente.
- Sem testes de integração completos neste ambiente (dependências Flask/ReportLab ausentes). Foram validadas as sintaxes Python e JavaScript.
- Para produção, configure `SECRET_KEY` forte, HTTPS, CSRF, backups e revisão de permissões.
