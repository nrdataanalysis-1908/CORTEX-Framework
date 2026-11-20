<div align="center">

<a href="https://www.nrtechlab.dev/"><img src="https://www.nrtechlab.dev/__l5e/assets-v1/02f952d5-a3b8-492b-8494-d58ea08ddfda/nrtech-logo.jpeg" alt="NR TECH Research Laboratory" width="180"></a>

# CORTEX FRAMEWORK
### Intelligent Document Processing for Enterprise Workflows

**NR TECH Research Laboratory · Research Edition · 2026**

[Website](https://www.nrtechlab.dev/) · [Research](https://www.nrtechlab.dev/#research) · [Architecture](https://www.nrtechlab.dev/#architecture) · [Documentation](cortex-rag/README.md) · [Development branch](https://github.com/nrdataanalysis-1908/CORTEX-Framework/tree/feat/cortex-rag-mvp)

<img src="cortex-rag/assets/cortex-rag-architecture.svg" alt="CORTEX RAG architecture" width="100%">

</div>

---

<p align="center">
<img src="https://img.shields.io/badge/RESEARCH-2026-0B75C9?style=flat-square">
<img src="https://img.shields.io/badge/DOMAIN-Document%20Intelligence-123B5D?style=flat-square">
<img src="https://img.shields.io/badge/STATUS-Active%20Development-168AAD?style=flat-square">
<img src="https://img.shields.io/badge/EDITION-Research-102A43?style=flat-square">
</p>

## 00 / Visão geral

O CORTEX (Cognitive Optical Reasoning Engine) é uma iniciativa de pesquisa aplicada em inteligência documental, engenharia de dados e automação de workflows corporativos.

A pesquisa investiga como documentos heterogêneos podem ser convertidos em registros estruturados, verificáveis e rastreáveis, preservando a proveniência das evidências e os critérios que sustentam cada decisão.

O framework conceitual explora três domínios complementares:

| Módulo conceitual | Responsabilidade de pesquisa |
|---|---|
| **OPTIC** | Percepção documental, leitura multimodal e extração estruturada |
| **NEXUS** | Arbitragem de evidências, consistência entre fontes e proveniência |
| **AEGIS** | Restrições simbólicas, validação operacional e justificabilidade |

> **Nota de implementação:** OPTIC, NEXUS e AEGIS compõem a arquitetura de pesquisa descrita no site. Não devem ser interpretados como agentes autônomos já implementados neste repositório. O módulo de software disponível nesta branch é um MVP separado de RAG documental.

## 01 / Problema de pesquisa

Workflows documentais corporativos combinam formatos heterogêneos, dados incompletos, divergência entre fontes, validação manual e requisitos de auditoria. O desafio não é apenas extrair texto: é preservar a relação entre dado, evidência, regra aplicada e resultado.

- **Document heterogeneity** — variação de layout, formato, qualidade e estrutura.
- **Evidence consistency** — divergências entre documentos e fontes externas.
- **Operational validation** — regras de negócio e restrições antes da emissão de decisões.
- **Traceability** — proveniência e reconstituição do caminho decisório.
- **Resilience** — tratamento de falhas parciais, ambiguidades e baixa confiança.

## 02 / Arquitetura de referência

A visão de pesquisa organiza o processamento documental em componentes desacoplados, com contratos explícitos e avaliação individual. Cada capacidade deve ser identificada como implementada, experimental ou planejada.

| Camada | Escopo |
|---|---|
| Acquisition | Recepção e normalização de documentos |
| Perception | Extração textual, layout e entidades |
| Evidence | Associação de campos às respectivas fontes |
| Arbitration | Tratamento de conflitos e inconsistências |
| Guardrails | Regras, restrições e validação |
| Orchestration | Coordenação do workflow e observabilidade |

## 03 / Implementação disponível — CORTEX RAG

<div align="center">

### Retrieval-Augmented Generation · MVP

<img src="cortex-rag/assets/cortex-rag-architecture.svg" alt="Fluxo do MVP CORTEX RAG" width="100%">

</div>

O subprojeto cortex-rag contém a implementação inicial de um pipeline RAG: ingestão de PDF/TXT, extração de texto, chunking, geração de embeddings, persistência vetorial em PostgreSQL/pgvector e recuperação de contexto para resposta por LLM.

**Stack do MVP**

| Componente | Tecnologia |
|---|---|
| API | FastAPI |
| Runtime | Python |
| Database | PostgreSQL 16 |
| Vector search | pgvector / cosine distance / HNSW |
| Embeddings | OpenAI API |
| Generation | OpenAI API |
| PDF parsing | pypdf |
| Local orchestration | Docker Compose |
| Unit tests | pytest |

- [Documentação técnica do CORTEX RAG](cortex-rag/README.md)
- [Protocolo de avaliação](cortex-rag/evaluation/README.md)
- [Código e artefatos](cortex-rag/)
- [Branch de desenvolvimento](https://github.com/nrdataanalysis-1908/CORTEX-Framework/tree/feat/cortex-rag-mvp)

## 04 / Metodologia de avaliação

A avaliação separa qualidade de recuperação, qualidade de geração e comportamento operacional. O primeiro conjunto contém 20 perguntas sintéticas vinculadas a trechos de evidência conhecidos.

<img src="cortex-rag/assets/evaluation-loop.svg" alt="Protocolo de avaliação" width="100%">

| Dimensão | Abordagem |
|---|---|
| Retrieval | Evidência-ouro encontrada no top-K |
| Groundedness | Resposta sustentada pelo contexto recuperado |
| Factuality | Verificação dos fatos contra o documento-fonte |
| Abstention | Recusa quando não há evidência suficiente |
| Performance | Latência, consumo de tokens e custo |

A métrica automatizada atual, evidence_hit_rate_at_k, mede apenas a recuperação do trecho-ouro. Não representa acurácia global, factualidade nem desempenho de produção. Resultados quantitativos só serão publicados após execução reproduzível.

## 05 / Princípios de engenharia

1. **Evidence before assertion** — toda afirmação deve ter suporte identificável.
2. **Validation as a first-class stage** — validação integra o fluxo, não é um remendo posterior.
3. **Separation of concerns** — percepção, regras, persistência e apresentação possuem fronteiras claras.
4. **Reproducibility** — entradas, parâmetros, versões e resultados devem ser rastreáveis.
5. **Failure transparency** — ausência de evidência e falhas devem ser explicitadas.
6. **Security by design** — dados mínimos, segredos protegidos e acesso controlado.

## 06 / Roadmap de pesquisa e engenharia

| Horizonte | Direção |
|---|---|
| Current | MVP RAG, recuperação vetorial e protocolo inicial de avaliação |
| Next | Groundedness, factualidade, observabilidade e testes de integração |
| Planned | OCR multimodal, evidências por campo e validação cruzada |
| Research | Negociação entre agentes, restrições simbólicas e replay causal |

## 07 / Estado e reprodutibilidade

Este repositório está em evolução. O código da branch de desenvolvimento deve ser tratado como experimental até que testes integrados, avaliação e documentação de execução sejam concluídos.

Não são declarados neste README resultados de benchmark, métricas de produção ou funcionalidades ainda não verificadas.

---

<div align="center">

<a href="https://www.nrtechlab.dev/"><img src="https://www.nrtechlab.dev/__l5e/assets-v1/02f952d5-a3b8-492b-8494-d58ea08ddfda/nrtech-logo.jpeg" alt="NR TECH Research Laboratory" width="112"></a>

**NR TECH Research Laboratory**

*Researching intelligent document processing, data engineering and enterprise workflow automation.*

[Website](https://www.nrtechlab.dev/) · [GitHub](https://github.com/nrdataanalysis-1908)

<sub>© 2026 NR TECH Research · CORTEX Framework</sub>

</div>
