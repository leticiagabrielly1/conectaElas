# Etapa 6 — Perfil e desempenho

Dashboard por usuária autenticada: cursos iniciados e concluídos, atividades semanais e mensais, progresso por curso, acertos e erros em questionários e desafios, XP e níveis, conquistas, sequência de dias, metas semanais editáveis e certificados emitidos. Dados obtidos das tabelas SQLite existentes; a meta é salva em `weekly_goals`. XP considera aulas e quizzes, sem atribuir pontos aos resultados de execução de código enviados pelo navegador. O indicador por linguagem utiliza a identificação dos cursos, sem inferir domínio real da linguagem. Atividade considera aulas, quizzes e tentativas de desafios, não tempo efetivo de estudo.

Executar `pip install -r requirements.txt` e `python app.py`; acessar `/perfil` com login. Testar os fluxos completos em navegador antes de publicar.
