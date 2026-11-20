<div align="center">

<img src="assets/nrtech-mark.svg" alt="NR TECH / NRTechLab" width="520">

# CORTEX RAG
### Retrieval-Augmented Generation para conhecimento documental

<img src="assets/cortex-rag-architecture.svg" alt="Arquitetura do CORTEX RAG" width="100%">

**FastAPI · PostgreSQL · pgvector · OpenAI · Python**

[Visão geral](../README.md) · [Arquitetura](assets/cortex-rag-architecture.svg) · [Avaliação](evaluation/README.md)

</div>

---

## Visão executiva

O CORTEX RAG é um MVP de busca semântica e geração de respostas fundamentadas em documentos. O fluxo recebe arquivos PDF/TXT, extrai o conteúdo, segmenta o texto em chunks com sobreposição, gera embeddings, persiste vetores no PostgreSQL/pgvector e recupera evidências para compor o contexto enviado ao modelo de linguagem.

<details>
<summary><strong>Escopo implementado nesta branch</strong></summary>

- API FastAPI com health check, ingestão documental e endpoint de perguntas.
- Extração de texto de PDF digital e TXT UTF-8.
- Chunking parametrizável e testável isoladamente.
- Embeddings persistidos no pgvector.
- Busca por distância de cosseno com índice HNSW.
- Resposta com indicação dos arquivos recuperados e abstenção heurística quando a similaridade é baixa.
- Dataset sintético com 20 perguntas e script de avaliação de recuperação.

</details>

## Identidade e stack

| Camada | Tecnologia |
|---|---|
| API | FastAPI + Pydantic |
| Linguagem | Python |
| Persistência | PostgreSQL 16 |
| Busca vetorial | pgvector + HNSW |
| Embeddings | OpenAI `text-embedding-3-small` |
| Geração | OpenAI `gpt-4o-mini` |
| Extração PDF | pypdf |
| Ambiente local | Docker Compose |
| Testes | pytest |

## Fluxo de avaliação

<img src="assets/evaluation-loop.svg" alt="Ciclo de avaliação do CORTEX RAG" width="100%">

A métrica atualmente implementada é `evidence_hit_rate_at_k`: proporção de perguntas em que a evidência-ouro foi encontrada entre os primeiros K trechos recuperados. Ela avalia recuperação, não correção factual da resposta gerada. Groundedness, factualidade, latência e custo permanecem dimensões de avaliação futura/manual.

## Execução local

### 1. Preparar ambiente

Na pasta `cortex-rag`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` e informe a chave da API OpenAI. Não versionar esse arquivo.

### 2. Subir o PostgreSQL

```powershell
docker compose up -d
```

### 3. Iniciar a API

```powershell
uvicorn app.main:app --reload
```

Documentação interativa: http://127.0.0.1:8000/docs

### 4. Executar testes unitários

```powershell
python -m pytest tests -q
```

Os testes de chunking e integridade do dataset não exigem conexão com banco ou chamadas à OpenAI.

### 5. Ingerir o documento sintético de avaliação

Com a API ativa, envie o arquivo `evaluation/fixtures/manual_operacional_sintetico.txt` pelo endpoint `POST /documents` (Swagger em `/docs`). O documento é fictício e foi criado exclusivamente para os testes.

### 6. Executar avaliação de recuperação

```powershell
python -m evaluation.run_eval --k 5
```

O relatório JSON será salvo em `evaluation/results/latest.json`. A execução exige banco ativo, documento previamente ingerido e chave OpenAI configurada.

## Endpoints

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/health` | Verificação básica do serviço |
| POST | `/documents` | Upload de PDF ou TXT |
| POST | `/ask` | Pergunta sobre o acervo indexado |

Exemplo de payload para `POST /ask`:

```json
{
  "question": "Qual é o prazo-alvo de primeira resposta para P1?"
}
```

## Estrutura

```text
cortex-rag/
├── app/
│   ├── chunking.py
│   ├── config.py
│   ├── db.py
│   ├── main.py
│   └── rag.py
├── assets/
│   ├── nrtech-mark.svg
│   ├── cortex-rag-architecture.svg
│   └── evaluation-loop.svg
├── evaluation/
│   ├── fixtures/
│   ├── questions.json
│   └── run_eval.py
├── tests/
│   └── test_chunking.py
├── .env.example
├── docker-compose.yml
└── requirements.txt
```

## Limitações e segurança

- PDFs escaneados exigem OCR, ainda não incluído.
- Não há autenticação, autorização ou isolamento multi-tenant.
- O limite de upload é de 15 MB.
- A estratégia de chunking usa janelas de caracteres; não é segmentação semântica.
- O limiar de similaridade de 0,25 é heurístico e ainda precisa de calibração.
- A avaliação atual não comprova factualidade, ausência de alucinação ou qualidade global das respostas.
- Não utilizar documentos pessoais, confidenciais ou dados de produção neste MVP.
- Segredos devem permanecer em variáveis de ambiente e fora do Git.

## Roadmap técnico

- [x] Pipeline inicial de ingestão e recuperação vetorial.
- [x] Chunking isolado e testes unitários.
- [x] Conjunto sintético de 20 perguntas.
- [x] Métrica inicial de recuperação top-K.
- [ ] Executar avaliação com banco e registrar baseline real.
- [ ] Adicionar avaliação de groundedness/factualidade com revisão humana.
- [ ] Adicionar logs estruturados, autenticação e controles de acesso.
- [ ] Avaliar OCR e chunking semântico.

---

<div align="center">

**NR TECH / NRTechLab**  
*Researching. Building. Automating. Evolving.*

<sub>Projeto experimental • branch feat/cortex-rag-mvp • versão 0.1.0</sub>

</div>
