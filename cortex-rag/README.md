# CORTEX RAG — MVP

Módulo experimental de Retrieval-Augmented Generation integrado ao CORTEX Framework. O sistema ingere arquivos PDF/TXT, divide o conteúdo em chunks, gera embeddings, persiste vetores no PostgreSQL com pgvector e responde perguntas com recuperação semântica e referências aos documentos.

> Estado: implementação inicial em desenvolvimento. Ainda requer execução local, testes automatizados e validação de qualidade antes de ser considerada uma entrega concluída.

## Arquitetura

```text
PDF/TXT -> extração -> chunking -> embeddings
                                  |
                                  v
                           PostgreSQL + pgvector
                                  |
Pergunta -> embedding -> busca vetorial -> contexto -> LLM -> resposta + fontes
```

## Stack

- Python, FastAPI e Pydantic
- PostgreSQL 16 + pgvector
- OpenAI Embeddings e Chat Completions
- Docker Compose

A busca utiliza distância de cosseno (`<=>`) e índice HNSW. O pgvector permite busca exata ou aproximada; o índice aproximado deve ser avaliado contra recall e latência no conjunto de teste. Referência: https://github.com/pgvector/pgvector.

## Executar localmente

1. Entre na pasta `cortex-rag`.
2. Crie o ambiente e instale dependências:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Inicie o PostgreSQL:

```bash
docker compose up -d
```

4. Copie `.env.example` para `.env` e configure `OPENAI_API_KEY`.
5. Inicie a API:

```bash
uvicorn app.main:app --reload
```

Documentação interativa: http://127.0.0.1:8000/docs

## Endpoints

- `GET /health`: verificação básica.
- `POST /documents`: upload multipart de PDF ou TXT.
- `POST /ask`: pergunta sobre os documentos indexados.

Exemplo de pergunta:

```json
{"question": "Quais são os principais pontos do documento?"}
```

## Avaliação planejada

O conjunto de avaliação terá pelo menos 20 perguntas com respostas de referência e evidências esperadas. Serão medidos:

- Recall@K da recuperação dos trechos relevantes;
- groundedness/aderência ao contexto;
- correção factual em relação ao gabarito;
- taxa de abstenção correta quando não houver evidência;
- latência por consulta.

Os resultados serão publicados somente após execução reproduzível. Não há métricas de desempenho declaradas nesta etapa.

## Limitações conhecidas do MVP

- PDF digital; OCR para PDFs escaneados ainda não está incluído.
- Sem autenticação/autorização nesta versão.
- Sem isolamento multiusuário/tenant.
- Limite de upload definido em 15 MB.
- A qualidade depende do documento, do modelo de embedding, do chunking e do contexto recuperado.
- O limiar de similaridade é heurístico e precisa ser calibrado com o conjunto de avaliação.
- Não enviar documentos confidenciais ou dados pessoais para a API externa.

## Próximas etapas

1. Testes unitários e integração com banco real.
2. Dataset de avaliação com 20+ casos.
3. Medição de Recall@K, groundedness e latência.
4. Logs estruturados, autenticação e limites operacionais.
5. OCR opcional para documentos digitalizados.
