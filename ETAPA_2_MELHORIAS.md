# ETAPA 2 — Trilha funcional

- Preservado o design da Etapa 1 e o currículo existente.
- Trilha personalizada por objetivo, nível e horas semanais; plano persistido em SQLite.
- Mapa de módulos e aulas, com bloqueios validados também no servidor.
- Conclusão automática de aulas após resposta correta, persistida em SQLite.
- Avaliação final por módulo: utiliza a questão da última aula do módulo como avaliação de revisão, sem criar perguntas inéditas.
- Aprovação da avaliação libera o módulo seguinte; resultados persistidos na tabela `module_assessments`.
- Retomada da primeira aula pendente e apresentação de avaliação pendente.
- Certificado condicionado à conclusão das aulas e aprovação das avaliações de todos os módulos.

## Limitações e observações

- A porcentagem da trilha é baseada nas aulas concluídas, não inclui peso extra para avaliações.
- Níveis de cursos e módulos seguem os dados já presentes no currículo; não foi reclassificado o material.
- Avaliações finais reutilizam uma questão existente, sendo recomendável criar bancos de questões independentes futuramente.
- Verificações estáticas de sintaxe passaram; testes de integração não puderam executar neste ambiente porque o Flask não está instalado.
