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

## 00 / Overview

CORTEX (Cognitive Optical Reasoning Engine) is an applied research initiative in document intelligence, data engineering, and enterprise workflow automation.

The research investigates how heterogeneous documents can be converted into structured, verifiable, and traceable records while preserving evidence provenance and the criteria supporting each decision.

The conceptual framework explores three complementary domains:

| Conceptual module | Research responsibility |
|---|---|
| **OPTIC** | Document perception, multimodal reading, and structured extraction |
| **NEXUS** | Evidence arbitration, cross-source consistency, and provenance |
| **AEGIS** | Symbolic constraints, operational validation, and explainability |

> **Implementation note:** OPTIC, NEXUS, and AEGIS are part of the research architecture described on the website. They must not be interpreted as autonomous agents already implemented in this repository. The software module available on this branch is a separate document RAG MVP.

## 01 / Research problem

Enterprise document workflows combine heterogeneous formats, incomplete data, discrepancies between sources, manual validation, and audit requirements. The challenge is not merely extracting text: it is preserving the relationship between data, evidence, applied rules, and outcomes.

- **Document heterogeneity** — variation in layout, format, quality, and structure.
- **Evidence consistency** — discrepancies between documents and external sources.
- **Operational validation** — business rules and constraints before decisions are issued.
- **Traceability** — provenance and reconstruction of the decision path.
- **Resilience** — handling partial failures, ambiguity, and low confidence.

## 02 / Reference architecture

The research vision organizes document processing into decoupled components with explicit contracts and independent evaluation. Each capability must be identified as implemented, experimental, or planned.

| Layer | Scope |
|---|---|
| Acquisition | Document intake and normalization |
| Perception | Text, layout, and entity extraction |
| Evidence | Association of fields with their respective sources |
| Arbitration | Conflict and inconsistency handling |
| Guardrails | Rules, constraints, and validation |
| Orchestration | Workflow coordination and observability |

## 03 / Available implementation — CORTEX RAG

<div align="center">

### Retrieval-Augmented Generation · MVP

<img src="cortex-rag/assets/cortex-rag-architecture.svg" alt="CORTEX RAG MVP workflow" width="100%">

</div>

The cortex-rag subproject contains the initial implementation of a RAG pipeline: PDF/TXT ingestion, text extraction, chunking, embedding generation, vector persistence in PostgreSQL/pgvector, and context retrieval for LLM-generated answers.

**MVP stack**

| Component | Technology |
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

- [CORTEX RAG technical documentation](cortex-rag/README.md)
- [Evaluation protocol](cortex-rag/evaluation/README.md)
- [Code and artifacts](cortex-rag/)
- [Development branch](https://github.com/nrdataanalysis-1908/CORTEX-Framework/tree/feat/cortex-rag-mvp)

## 04 / Evaluation methodology

The evaluation separates retrieval quality, generation quality, and operational behavior. The initial dataset contains 20 synthetic questions linked to known evidence passages.

<img src="cortex-rag/assets/evaluation-loop.svg" alt="Evaluation protocol" width="100%">

| Dimension | Approach |
|---|---|
| Retrieval | Gold evidence retrieved within top-K |
| Groundedness | Answer supported by retrieved context |
| Factuality | Facts checked against the source document |
| Abstention | Refusal when sufficient evidence is unavailable |
| Performance | Latency, token consumption, and cost |

The current automated metric, evidence_hit_rate_at_k, measures only retrieval of the gold passage. It does not represent overall accuracy, factuality, or production performance. Quantitative results will be published only after reproducible execution.

## 05 / Engineering principles

1. **Evidence before assertion** — every claim must have identifiable support.
2. **Validation as a first-class stage** — validation is part of the workflow, not a later patch.
3. **Separation of concerns** — perception, rules, persistence, and presentation have clear boundaries.
4. **Reproducibility** — inputs, parameters, versions, and results must be traceable.
5. **Failure transparency** — missing evidence and failures must be made explicit.
6. **Security by design** — data minimization, protected secrets, and controlled access.

## 06 / Research and engineering roadmap

| Horizon | Direction |
|---|---|
| Current | RAG MVP, vector retrieval, and initial evaluation protocol |
| Next | Groundedness, factuality, observability, and integration tests |
| Planned | Multimodal OCR, field-level evidence, and cross-validation |
| Research | Agent negotiation, symbolic constraints, and causal replay |

## 07 / Status and reproducibility

This repository is evolving. Code on the development branch must be treated as experimental until integration tests, evaluation, and execution documentation are complete.

This README does not claim benchmark results, production metrics, or features that have not yet been verified.

---

<div align="center">

<a href="https://www.nrtechlab.dev/"><img src="https://www.nrtechlab.dev/__l5e/assets-v1/02f952d5-a3b8-492b-8494-d58ea08ddfda/nrtech-logo.jpeg" alt="NR TECH Research Laboratory" width="112"></a>

**NR TECH Research Laboratory**

*Researching intelligent document processing, data engineering and enterprise workflow automation.*

[Website](https://www.nrtechlab.dev/) · [GitHub](https://github.com/nrdataanalysis-1908)

<sub>© 2026 NR TECH Research · CORTEX Framework</sub>

</div>
