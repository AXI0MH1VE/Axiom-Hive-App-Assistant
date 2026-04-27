# Verity Assistant

A constrained AI assistant providing factual, attributable answers with zero tolerance for misappropriation.

## Overview

Verity Assistant is a ChatGPT-like application centered on **factual integrity**:

- **Factual Grounding**: Every claim traceable to curated knowledge sources
- **No Misappropriation**: Copyright detection and strict attribution
- **Transparency**: Confidence scores, inline citations, and gap identification
- **Auditability**: Tamper-evident logs for every query and response
- **Hermetic Scope**: Operates only within approved knowledge bases

Built with a RAG pipeline, NLI fact-checking, and multi-layer validation guardrails.

---

## Quick Start (5 minutes)

### Prerequisites
- Docker & Docker Compose
- 8GB+ RAM (16GB recommended for local LLM option)
- 10GB disk space

### Start the application

```bash
cd verity-assistant
docker-compose up --build -d
```

Access the UI at: **http://localhost**

API documentation: **http://localhost:8000/docs**

### First query

Ask a factual question like "What is photosynthesis?" to see sourced, confidence-labeled answers.

---

## Architecture

### Backend (FastAPI, Python 3.11)

```
src/backend/
├── main.py                  # FastAPI app & REST endpoints
├── core/
│   ├── assistant.py         # Orchestration pipeline
│   ├── intent_classifier.py # Query routing
│   ├── fact_checker.py      # NLI entailment validation
│   ├── contradiction.py     # Source conflict detection
│   └── auditor.py           # Tamper-evident audit logging
├── retrieval/
│   ├── vector_store.py      # FAISS wrapper
│   ├── searcher.py          # Hybrid vector + BM25
│   ├── document_loader.py   # PDF/DOCX/HTML ingestion
│   └── ingest_service.py    # Batch ingestion
├── models/
│   ├── wrapper.py           # LLM provider abstraction
│   ├── constrained_gen.py   # Guardrails & prompts
│   └── verifier_model.py    # NLI model singleton
├── utils/
│   ├── formatter.py         # Structured output schema
│   ├── citation.py          # Bibliography generation
│   ├── similarity.py        # BLEU + embedding similarity
│   └── sanitizer.py         # PII redaction (Presidio)
└── services/
    ├── knowledge_service.py # High-level API
    ├── auth_service.py      # API key & rate limiting
    ├── feedback_service.py  # User flagging & review
    └── update_service.py    # Corpus versioning
```

### Frontend (React + TypeScript + Vite)

```
src/frontend/
├── src/
│   ├── App.tsx              # Router & layout
│   ├── pages/
│   │   ├── Chat.tsx         # Main chat interface
│   │   ├── History.tsx      # Conversation history
│   │   └── Admin.tsx        # Dashboard (audit, stats)
│   ├── components/
│   │   ├── MessageBubble.tsx
│   │   ├── SourceCard.tsx   # Expandable citation
│   │   ├── ConfidenceBadge.tsx
│   │   └── SettingsPanel.tsx
│   └── store/               # Zustand global state
├── index.html
└── Dockerfile               # Nginx static build
```

### Knowledge Pipeline

1. **Document Ingestion** → PDF/DOCX/HTML → chunked text with provenance metadata
2. **Embedding** → `all-MiniLM-L6-v2` sentence-transformers → FAISS Flat index
3. **Hybrid Retrieval** → vector similarity + BM25 keyword ranking
4. **Constraint Injection** → prompt with source excerpts, logit bias
5. **Output Validation** → NLI fact-check, copyright similarity, PII scan
6. **Structured Formatting** → answer + confidence + sources + gaps

---

## Configuration

All runtime behavior controlled by JSON/YAML files in `config/`.

| File | Purpose |
|------|---------|
| `rules.json` | Token risk patterns, fact rules, copyright thresholds |
| `boundaries.json` | Allowed domains, restricted claim types, source authority |
| `thresholds.json` | Retrieval k, similarity cutoffs, validation NLI threshold, audit retention |
| `sources.yaml` | Corpus manifest, LLM provider configuration, API enable flags |
| `llm_config.json` | OpenAI/Anthropic/Local provider settings, retry policies |

Environment variables (see `.env.example`):
- `OPENAI_API_KEY` – required for cloud LLM
- `AUDIT_HMAC_KEY` – rotate every 30 days
- `REDIS_ENABLED` – optional caching layer

---

## API Reference

Full OpenAPI spec available at: `http://localhost:8000/docs`

### Chat

**POST** `/api/v1/chat`

```json
{
  "query": "What is the capital of France?",
  "strict": false,
  "top_k": 5,
  "stream": false
}
```

Response:

```json
{
  "id": "uuid",
  "answer": "The capital of France is Paris [1].",
  "confidence": "High",
  "sources": [
    {
      "id": 1,
      "title": "France - Wikipedia",
      "author": "Wikipedia contributors",
      "date": "2024-06-10",
      "url": "https://en.wikipedia.org/wiki/France",
      "license": "CC-BY-SA-4.0"
    }
  ],
  "gaps": [],
  "model_version": "gpt-4-turbo",
  "timestamp": "2025-08-26T20:00:00Z",
  "processing_time_ms": 1250,
  "query_hash": "sha256:..."
}
```

### Search-only

**GET** `/api/v1/search?q=question&top_k=5` – retrieve excerpts without LLM generation.

### Administration

- `GET /api/v1/admin/audit` – query audit log
- `GET /api/v1/admin/stats` – system health metrics
- `POST /api/v1/feedback` – report inaccurate response
- `POST /api/v1/ingest` – add document to knowledge base

---

## Knowledge Corpus

### Initial Corpus

The default setup expects a curated Wikipedia subset in `knowledge/embeddings/`.

To download and index sample data:

```bash
python scripts/download_sample_corpus.py  # 100 articles
python scripts/build_index.py            # creates FAISS index
```

### Adding Documents

API: `POST /api/v1/ingest` with JSON body: `{ "file_path": "/abs/path/doc.pdf" }`

Supported formats: PDF, DOCX, HTML, TXT, Markdown.

Documents are chunked (1,000 characters with 200 overlap), embedded, and added to the vector store. Provenance hash stored for deduplication.

### Corpus Updates

Delta packs apply incremental updates without downtime. Configure `sources.yaml` `update_endpoint` to point to signed update manifest.

Freshness policy: If corpus >90 days old, system refuses new queries (configurable).

---

## Governance & Transparency

### Audit Logging

Every interaction recorded in `data/audit/audit.db` (SQLite) with:
- Query hash, timestamp, user context
- Retrieval metadata (sources, latency)
- Generation parameters (model, tokens)
- Validation results (fact-check, copyright, plagiarism)
- HMAC-SHA256 signature for tamper detection

Export compliance reports:
```bash
python scripts/export_audit.py --format pdf --start 2025-01-01
```

### Feedback Loop

Users flag responses as inaccurate, missing citation, or poor attribution. Admin review queue at `/api/v1/admin/feedback`. Flags trigger root-cause analysis and knowledge base corrections.

### Operational Disclosure

First-use message displayed in UI:

> I am an in-application AI assistant. My knowledge comes from a curated set of sources approved by the application owner. I do not access real-time public internet data unless explicitly configured. I never speculate; if evidence is insufficient, I will say so. Every answer includes citations and confidence indicator. I am designed to prevent misappropriation.

---

## Security & Privacy

- **No PII collection** by default; Presidio redacts if detected
- **Rate limiting**: 100 req/min per IP, 1000 req/min per API key
- **Input sanitization**: Blocks prompt injection patterns
- **Audit integrity**: HMAC signatures detect log tampering
- **Optional encryption**: AES-256 for audit DB (enable in thresholds.json)

---

## Development

### Local setup (no Docker)

```bash
# Python
pip install -r requirements.txt

# Frontend
cd src/frontend && npm install && cd ../..

# Download sample corpus
python scripts/download_sample_corpus.py

# Build vector index
python scripts/build_index.py

# Run backend
uvicorn src.backend.main:app --reload --port 8000

# Run frontend (separate terminal)
cd src/frontend && npm run dev
```

### Testing

```bash
# Unit tests
pytest tests/unit/

# Integration (end-to-end)
pytest tests/integration/

# E2E UI tests (requires browser)
npx playwright test

# Load test
locust -f tests/load/locustfile.py
```

### Code quality

```bash
black src/
ruff check src/
mypy src/
pre-commit install
```

---

## Deployment

### Docker Compose (single command)

```bash
docker-compose up -d
```

Environment variables: copy `.env.example` → `.env` and fill secrets.

### Production checklist

- [ ] Set `API_KEY_REQUIRED=true` and issue API keys
- [ ] Enable Redis caching (`REDIS_ENABLED=true`)
- [ ] Configure TLS (reverse proxy: nginx, Traefik)
- [ ] Set `AUDIT_LOG_ENCRYPTION=true` and provide `AUDIT_HMAC_KEY`
- [ ] Mount `knowledge/` to persistent volume
- [ ] Backup `data/audit/` regularly
- [ ] Enable Prometheus metrics (`ENABLE_PROMETHEUS=true`)
- [ ] Configure log aggregation (ELK/Graylog)

---

## Troubleshooting

### Backend fails to start
- Verify `.env` file present; at minimum set `OPENAI_API_KEY`
- Ensure `knowledge/embeddings/corpus.faiss` exists (run `build_index.py` if empty)
- Check port 8000 not in use

### Slow responses (>3s)
- Enable Redis caching
- Reduce `top_k` (default 5) or switch to local LLM fallback
- Ensure sufficient RAM (≥16GB for embeddings)

### "No verified information" for all queries
- Vector store empty: run `python scripts/ingest_corpus.py --data-dir knowledge/raw`
- Check logs for retrieval errors
- Verify `config/sources.yaml` has `enabled: true` for your corpus

---

## Contributing

This repository follows the governance model defined in `GOVERNANCE.md`. All changes require:

1. Unit test coverage ≥80%
2. Factual validation on benchmark
3. Peer review of audit-log impact
4. Documentation updates

---

## License

MIT. See `LICENSE` file.

---

## Support

Report issues: GitHub Issues (private repo)
Security: `SECURITY.md`
