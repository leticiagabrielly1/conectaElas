# Conectas Elas — Plataforma integrada

Projeto de aprendizagem para alunas do Ensino Médio. Interface multipáginas com tema claro/escuro, contraste, fontes ajustáveis, Flask, SQLite e currículo ampliado a partir do CodeStart.

## Como iniciar no VS Code (Windows)

1. Extraia o ZIP e abra a pasta `ConectasElas_Completo` no VS Code.
2. No terminal execute `python -m pip install -r requirements.txt` (ou `py -m pip install -r requirements.txt`).
3. Execute `python app.py` (ou `py app.py`).
4. Abra `http://127.0.0.1:5000`.

O banco SQLite `conectas.db` é criado automaticamente. Não abra o HTML com duplo clique: o backend é necessário.

## Páginas

`/dashboard`, `/cursos`, `/curso/<id>`, `/desafios`, `/trilha-personalizada`, `/laboratorio`, `/tutora`, `/projetos`, `/oportunidades`, `/comunidade`, `/certificados`, `/perfil`, `/entrar`.

## Funcionalidades

- Cadastro, login, logout, edição de perfil; senhas com hash.
- 15 cursos, 663 aulas, teoria, objetivos, prática e questões por aula.
- Progresso individual, XP, tentativas, percentual de acertos e gráficos por curso e dia, persistidos no SQLite.
- Certificado digital em PDF imprimível, liberado apenas após 100% das aulas e avaliações corretas; código de autenticidade e verificação pública.
- Tutora com respostas locais e suporte opcional à API OpenAI via `OPENAI_API_KEY`.
- Laboratório com verificação estática de Python, Java e JSON e consultas SQL de demonstração, sem execução de código Python/Java.
- Trilhas personalizadas e projetos do currículo CodeStart.
- Vagas fictícias com favoritos e mural de comunidade (protótipo educacional).

## Testes

Execute `python -m unittest discover -s tests -v`.

## Segurança e publicação

Este é um protótipo para testes locais. Antes de usar com alunas reais, configurar `SECRET_KEY` segura e HTTPS, CSRF, limitação de requisições, recuperação de senha, política de privacidade, moderação de publicações e avaliação de acessibilidade. Não publique dados pessoais. O certificado é **da plataforma educacional** e não representa certificado oficial do SENAC, reconhecimento pelo MEC ou validação profissional. Vagas e organizações são fictícias.

A tutora de IA externa só funciona se a API estiver configurada e houver conectividade e saldo; sem isso o CodeStart usa resposta local. A chave nunca deve ficar no frontend.


## Trilha personalizada funcional (nova versão)

Acesse `/trilha-personalizada`, faça login, escolha objetivo, nível e horas por semana e clique em **Gerar minha trilha**. O plano fica salvo em `study_plans` no SQLite. O sistema organiza os cursos na sequência do currículo CodeStart, apresenta um cronograma semanal com aulas reais, indica a próxima aula pendente e acompanha o progresso automaticamente quando uma avaliação é respondida corretamente. Você pode sair, entrar novamente e retomar sua trilha; excluir o plano não apaga aulas concluídas.

Para testar: `python -m unittest discover -s tests -v`. O projeto exige instalar as dependências de `requirements.txt`.
