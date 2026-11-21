# Avaliação do CORTEX RAG

Este diretório contém um corpus inteiramente sintético, 20 perguntas com evidência-ouro e um avaliador de recuperação vetorial.

## Artefatos

- `fixtures/manual_operacional_sintetico.txt`: documento fictício que deve ser ingerido na API.
- `questions.json`: 20 consultas e trechos-ouro esperados.
- `run_eval.py`: calcula `evidence_hit_rate_at_k` sobre os trechos retornados pelo pgvector.

## Procedimento

1. Inicie o PostgreSQL e a API conforme o README do módulo.
2. Faça upload do documento sintético pelo endpoint `POST /documents`.
3. Execute `python -m evaluation.run_eval --k 5` na pasta `cortex-rag`.
4. Analise `evaluation/results/latest.json` e investigue cada miss.

## Definição da métrica

Para cada consulta, o caso é considerado hit quando o texto de evidência-ouro aparece integralmente em pelo menos um dos K chunks recuperados. A métrica é:

`evidence_hit_rate_at_k = hits / total_de_casos`

A métrica é deliberadamente restrita: mede recuperação do trecho de referência. Não mede correção factual da resposta, groundedness, relevância percebida, robustez a paráfrases, latência ou custo. Esses aspectos exigem rubrica adicional e avaliação humana ou protocolo de judge validado.

Os valores em `expected_facts` são apoio à revisão qualitativa e não são usados para declarar uma nota automática de qualidade da resposta.


## Métricas de ordenação

O avaliador também reporta três métricas com relevância binária derivada da correspondência literal do trecho-ouro:

- `Recall@K`: proporção de consultas em que ao menos um chunk relevante aparece no top-K.
- `MRR@K`: média do inverso da posição do primeiro chunk relevante. Valor maior indica que a evidência tende a aparecer mais cedo.
- `NDCG@K`: ganho cumulativo descontado e normalizado, considerando a posição de todos os chunks relevantes recuperados.

O relatório JSON preserva `score` como alias de `Recall@K` para compatibilidade com consumidores anteriores e adiciona `metrics.recall_at_k`, `metrics.mrr_at_k` e `metrics.ndcg_at_k`. Cada caso inclui as posições dos chunks relevantes em `relevant_ranks`.

### Limitação metodológica

A relevância atual é binária: um chunk é relevante quando contém literalmente a evidência-ouro. Isso é reproduzível, mas não reconhece paráfrases, evidências semanticamente equivalentes ou múltiplos trechos complementares. As métricas avaliam recuperação e ordenação, não factualidade ou groundedness da resposta. A evolução do conjunto-ouro exige revisão humana e critérios explícitos.
