# Avaliação do CORTEX RAG

Este diretório contém um corpus inteiramente sintético, 20 perguntas com evidência-ouro e avaliadores separados para recuperação e qualidade de respostas.

## Artefatos

- `fixtures/manual_operacional_sintetico.txt`: documento fictício que deve ser ingerido na API.
- `questions.json`: 20 consultas e trechos-ouro esperados.
- `run_eval.py`: avalia a recuperação top-K no pgvector.
- `retrieval_metrics.py`: calcula Recall@K, MRR@K e NDCG@K.
- `answer_quality.py`: agrega rótulos de qualidade atribuídos por revisores humanos.
- `ANSWER_QUALITY.md`: rubrica, formato de anotação e interpretação das métricas.

## Avaliação de recuperação

1. Inicie o PostgreSQL e a API conforme o README do módulo.
2. Faça upload do documento sintético pelo endpoint `POST /documents`.
3. Execute `python -m evaluation.run_eval --k 5` na pasta `cortex-rag`.
4. Analise `evaluation/results/latest.json` e investigue cada miss.

Para cada consulta, o caso é considerado hit quando o texto de evidência-ouro aparece integralmente em pelo menos um dos K chunks recuperados. O relatório apresenta Recall@K, MRR@K e NDCG@K. A relevância é binária e literal: não reconhece paráfrases ou equivalência semântica.

Essas métricas avaliam recuperação e ordenação. Não medem correção factual, groundedness ou qualidade da resposta gerada. O campo legado `score` permanece como alias de Recall@K.

## Avaliação de qualidade da resposta

A qualidade da resposta é avaliada separadamente por anotações humanas. Cada afirmação deve ser rotulada como `supported`, `unsupported`, `contradicted` ou `unverifiable`, com evidência ou justificativa registrada. Também se anota se a resposta se absteve e se a abstenção era esperada.

O módulo `evaluation.answer_quality.evaluate_annotations` agrega taxas de suporte, afirmações não sustentadas, contradição e acurácia de abstenção. Ele não classifica texto automaticamente, não chama modelos e não transforma similaridade vetorial em prova factual.

Consulte [ANSWER_QUALITY.md](ANSWER_QUALITY.md) para o formato JSON, critérios de anotação e limites metodológicos.

## Limites metodológicos

- O conjunto atual é sintético; nenhum resultado de benchmark real é incluído.
- A relevância da recuperação depende de correspondência literal com a evidência-ouro.
- A qualidade da resposta depende de revisão humana e consistência da rubrica.
- Afirmações não verificáveis são reportadas separadamente e excluídas do denominador das taxas de afirmações decidíveis.
- As métricas não constituem garantia estatística nem prova universal de factualidade.
