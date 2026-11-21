# CORTEX RAG — Load testing

Este procedimento mede o comportamento HTTP do endpoint RAG sob concorrência controlada. O executor usa apenas a biblioteca padrão do Python; não adiciona dependências ao runtime da API.

## Pré-requisitos

- API CORTEX RAG iniciada e acessível.
- PostgreSQL/pgvector inicializado e documento de teste ingerido.
- Credenciais OpenAI válidas configuradas na API.
- Use apenas documentos sintéticos ou autorizados.

## Execução reproduzível

Na pasta `cortex-rag`, execute uma carga inicial moderada:

```powershell
python -m evaluation.load_test --url http://127.0.0.1:8000/ask --requests 30 --concurrency 2 --warmup 3 --payload '{"question":"Qual é o procedimento documentado?"}'
```

Depois aumente progressivamente a concorrência, mantendo a mesma pergunta e o mesmo corpus:

```powershell
python -m evaluation.load_test --url http://127.0.0.1:8000/ask --requests 100 --concurrency 5 --warmup 5 --payload '{"question":"Qual é o procedimento documentado?"}' --fail-on-error
python -m evaluation.load_test --url http://127.0.0.1:8000/ask --requests 200 --concurrency 10 --warmup 5 --payload '{"question":"Qual é o procedimento documentado?"}' --fail-on-error
python -m evaluation.load_test --url http://127.0.0.1:8000/ask --requests 300 --concurrency 20 --warmup 5 --payload '{"question":"Qual é o procedimento documentado?"}' --fail-on-error
```

Cada execução imprime um relatório JSON com quantidade de requisições, sucessos, falhas, taxa de erro, throughput, distribuição de status HTTP e latência mínima/média/p50/p95/p99/máxima.

## Interpretação

- Compare p50/p95/p99 entre níveis de concorrência; p95/p99 revelam degradação de cauda.
- Correlacione HTTP 503 com `GET /metrics`, especialmente `upstream_bulkheads` e `upstream_circuit_breaker`.
- Correlacione latência e erros com `upstream_retries`.
- Throughput é requisições concluídas por segundo durante a janela medida; não equivale a capacidade sustentável.
- O cliente de carga e a API podem compartilhar a mesma máquina. Registre esse contexto e evite comparar execuções em ambientes diferentes.

## Limites e segurança operacional

O teste `/ask` consome embeddings e, quando há evidência, chamadas de geração. Custos e limites do provedor aplicam-se. Comece com carga baixa, monitore quotas e interrompa se houver saturação ou custo inesperado. Não execute contra produção sem autorização e janela de teste.

Este harness não define SLOs nem afirma capacidade de produção. Os resultados são um baseline experimental; repita em ambiente controlado antes de estabelecer metas. O relatório não inclui conteúdo de respostas nem credenciais.
