<div align="center">

<a href="https://www.nrtechlab.dev/"><img src="https://www.nrtechlab.dev/__l5e/assets-v1/02f952d5-a3b8-492b-8494-d58ea08ddfda/nrtech-logo.jpeg" alt="NR TECH Research Laboratory" width="150"></a>

# CORTEX RAG
### Retrieval-Augmented Generation for Document Intelligence

**Technical implementation note · NR TECH Research Laboratory · 2026**

[Research site](https://www.nrtechlab.dev/) · [Framework overview](../README.md) · [Evaluation protocol](evaluation/README.md)

</div>

---

<p align="center">
<img src="https://img.shields.io/badge/MODULE-RAG-0B75C9?style=flat-square">
<img src="https://img.shields.io/badge/API-FastAPI-123B5D?style=flat-square">
<img src="https://img.shields.io/badge/DATABASE-PostgreSQL%2016-336791?style=flat-square">
<img src="https://img.shields.io/badge/VECTOR-pgvector-168AAD?style=flat-square">
<img src="https://img.shields.io/badge/STATUS-Experimental-8A6D3B?style=flat-square">
</p>

## 00 / Abstract

Este módulo implementa um pipeline experimental de Retrieval-Augmented Generation (RAG) para consulta a documentos. O objetivo é investigar a recuperação de evidências documentais e sua utilização como contexto de respostas geradas por um modelo de linguagem.

O escopo atual contempla arquivos PDF digitais e TXT, segmentação textual, embeddings, armazenamento vetorial e recuperação por distância de cosseno. A implementação é um MVP de engenharia; ainda não constitui uma solução validada para produção.

## 01 / System architecture

<img src="assets/cortex-rag-architecture.svg" alt="CORTEX RAG system architecture" width="100%">

| Stage | Operação | Componente |
|---|---|---|
| 01 | Document acquisition | FastAPI upload |
| 02 | Text extraction | pypdf / UTF-8 |
| 03 | Chunk segmentation | Python |
| 04 | Vectorization | OpenAI embeddings |
| 05 | Vector persistence and retrieval | PostgreSQL / pgvector |
| 06 | Contextual generation | OpenAI chat completion |

## 02 / Technology profile

| Layer | Technology |
|---|---|
| Language | Python |
| API | FastAPI |
| Database | PostgreSQL 16 |
| Vector extension | pgvector |
| Similarity | Cosine distance |
| ANN index | HNSW |
| Embedding model | text-embedding-3-small |
| Generation model | gpt-4o-mini |
| PDF parser | pypdf |
| Tests | pytest |
| Local environment | Docker Compose |

## 03 / Evaluation protocol

<img src="assets/evaluation-loop.svg" alt="Retrieval evaluation protocol" width="100%">

O diretório evaluation contém um documento sintético e 20 perguntas com evidência-ouro. A métrica evidence_hit_rate_at_k calcula a proporção de perguntas em que o trecho de referência foi recuperado entre os primeiros K resultados.

~~~text
evidence_hit_rate_at_k = evidence_hits / total_questions
~~~

A métrica não deve ser interpretada como acurácia da resposta, factualidade, groundedness ou ausência de alucinação. Essas dimensões exigem protocolo próprio e revisão qualitativa.

Consulte [evaluation/README.md](evaluation/README.md) para os detalhes e critérios de execução.

## 04 / Local execution

### Requirements

- Python 3.11+
- Docker Desktop
- Chave de API OpenAI

### Environment setup — Windows PowerShell

~~~powershell
cd cortex-rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
~~~

Configure as variáveis em .env. Não versione chaves ou segredos.

### Database

~~~powershell
docker compose up -d
~~~

### API

~~~powershell
uvicorn app.main:app --reload
~~~

Swagger UI: http://127.0.0.1:8000/docs

### Unit tests

~~~powershell
python -m pytest tests -q
~~~

Os testes unitários de chunking, integridade do dataset e métricas de observabilidade não exigem conexão com banco ou chamadas à API OpenAI.

### Retrieval evaluation

1. Faça upload de evaluation/fixtures/manual_operacional_sintetico.txt via POST /documents.
2. Execute:

~~~powershell
python -m evaluation.run_eval --k 5
~~~

3. Analise o relatório em evaluation/results/latest.json.

A execução de avaliação requer PostgreSQL ativo, documento previamente ingerido e credenciais válidas.

## 05 / API surface

| Method | Endpoint | Description |
|---|---|---|
| GET | /health | Liveness check |
| GET | /ready | PostgreSQL readiness check |
| GET | /metrics | Process-local request and latency metrics (JSON) |
| POST | /documents | PDF/TXT ingestion |
| POST | /ask | Contextual question answering |

As respostas HTTP incluem `X-Request-ID` e `X-Process-Time-Ms`. Os logs de requisição são emitidos em JSON. O cliente OpenAI utiliza timeout e número máximo de retries configuráveis; conexões PostgreSQL possuem timeout explícito.

### Observability and reliability baseline

`GET /metrics` apresenta contagem de requisições, erros HTTP 5xx e percentis p50/p95/p99 calculados sobre uma janela em memória de até 10.000 observações. Esses dados são locais ao processo, reiniciam com a aplicação e não devem ser tratados como telemetria distribuída ou SLO de produção. O endpoint ainda não possui autenticação.

Variáveis adicionais:

~~~env
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=2
DATABASE_CONNECT_TIMEOUT_SECONDS=5
~~~

`/health` verifica liveness da API; `/ready` consulta o PostgreSQL. A prontidão não verifica a disponibilidade da OpenAI.

Exemplo de requisição:

~~~json
{
  "question": "Qual é o prazo-alvo de primeira resposta para P1?"
}
~~~

## 06 / Repository map

~~~text
cortex-rag/
├── app/
│   ├── chunking.py
│   ├── config.py
│   ├── db.py
│   ├── main.py
│   ├── observability.py
│   └── rag.py
├── assets/
│   ├── cortex-rag-architecture.svg
│   └── evaluation-loop.svg
├── evaluation/
│   ├── fixtures/
│   ├── questions.json
│   ├── run_eval.py
│   └── README.md
├── tests/
│   ├── test_chunking.py
│   ├── test_evaluation_dataset.py
│   └── test_observability.py
├── .env.example
├── docker-compose.yml
└── requirements.txt
~~~

## 07 / Limitations and controls

- PDFs escaneados não são processados; OCR não está incluído.
- Não há autenticação, autorização ou isolamento entre usuários.
- O limite de upload é de 15 MB.
- Chunking utiliza janelas de caracteres, não segmentação semântica.
- O limiar de similaridade é heurístico e requer calibração.
- A avaliação atual não mede factualidade nem qualidade global das respostas.
- O corpus de teste é sintético; não utilizar documentos pessoais ou confidenciais.
- Segredos devem permanecer em variáveis de ambiente e nunca ser versionados.

## 08 / Engineering roadmap

- [x] Ingestão PDF/TXT e persistência vetorial inicial.
- [x] Chunking isolado e testes unitários.
- [x] Dataset sintético de 20 perguntas.
- [x] Avaliador inicial de recuperação top-K.
- [ ] Baseline integrado reproduzível.
- [ ] Testes de integração para concorrência e idempotência.
- [ ] Avaliação de groundedness e factualidade.
- [x] Instrumentação inicial de requisições, latência e logs JSON.
- [ ] Métricas Prometheus, tracing distribuído e controle de acesso.
- [ ] OCR e avaliação multimodal.

---

<div align="center">

<a href="https://www.nrtechlab.dev/"><img src="https://www.nrtechlab.dev/__l5e/assets-v1/02f952d5-a3b8-492b-8494-d58ea08ddfda/nrtech-logo.jpeg" alt="NR TECH Research Laboratory" width="92"></a>

**NR TECH Research Laboratory** · CORTEX Framework

<sub>Experimental implementation · engineering foundation in progress</sub>

</div>
