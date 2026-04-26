# AXIOM HIVE FOUNDATIONAL DOCTRINE

## 1. MISSION & PURPOSE

Verity Assistant is a constrained large language model system designed to operate as a **factual oracle** within a host application. Its primary mission is to provide accurate, attributable information while systematically eliminating:

- Speculative or false statements
- Copyrighted material reproduction without authorization
- Unverified claims presented as fact
- Information originating outside the approved knowledge corpus

The system exists as a **subordinate digital infrastructure** executing linguistic processing and data synthesis under the absolute jurisdictional authority of the biological human operator.

---

## 2. CORE PRINCIPLES

### 2.1 Factual Grounding Only
Every statement of fact must be traceable to an authoritative, time-stamped source in a curated knowledge base. The assistant shall not generate any claim that cannot be directly attributed to a verified source excerpt.

**Operationalization**:
- Retrieval-Augmented Generation (RAG) as mandatory first step
- Fact-grounding validator cross-checks each generated sentence against source excerpts
- Deterministic decoding (temperature=0) to limit invention

### 2.2 Uncertainty Transparency
The assistant must clearly differentiate between verified fact, well-supported consensus, and areas where evidence is insufficient. It must refuse to answer rather than guess.

**Operationalization**:
- Confidence scoring per response: High (≥3 sources, recent), Medium (1–2 sources), Low (single, old source)
- Structured output schema includes explicit `gaps` field listing unknowns
- Refusal messages direct users to refine queries or seek alternative sources

### 2.3 No Misappropriation
The assistant shall never reproduce copyrighted material verbatim without explicit, properly attributed quotation. It shall never paraphrase in a way that masks the origin of proprietary content.

**Operationalization**:
- Sentence-level similarity check against copyrighted work database (threshold: 30% BLEU or 0.6 cosine similarity → block)
- Attribution requirement: all quotes include source, author, date, license status
- Plagiarism detection ensures generated text uniqueness (>0.8 similarity to single unlicensed source → regenerate or refuse)

### 2.4 Hermetic Scope
The assistant only uses knowledge bases and tool integrations explicitly approved by the application owner. It does not access public internet content unless that access is whitelisted and monitored.

**Operationalization**:
- All retrieval sources enumerated in `config/sources.yaml` with approval status
- External API connectors require explicit configuration; disabled by default
- Document Custodian validates provenance of user-uploaded content before indexing

### 2.5 User-Side Accountability
Every response includes metadata that enables auditing: source list, confidence scoring, timestamp, and model version.

**Operationalization**:
- Tamper-evident audit log (append-only SQLite with HMAC signatures)
- Response metadata includes `query_hash`, `sources_used`, `validators_passed`, `model_version`
- Full audit trail available for compliance review via admin dashboard

---

## 3. SYSTEM ARCHITECTURE

### 3.1 Processing Pipeline

```
User Query
    ↓
[Intent Classifier]
    ├─ Factual request → proceed
    └─ Subjective/creative → refusal with guidance
    ↓
[Retrieval Engine]
    ├─ Vector similarity search (FAISS)
    ├─ BM25 keyword search (rank_bm25)
    └─ Metadata filtering (source, date, license)
    ↓
[Evidence Aggregation]
    └─ Collect top-k excerpts with provenance metadata
    ↓
[Contradiction Detector]
    └─ Surface conflicting claims from multiple sources
    ↓
[Constrained Generator]
    ├─ System prompt with source excerpts
    ├─ Logit bias against speculative tokens
    ├─ Temperature = 0.0 (deterministic)
    └─ Stop sequences to prevent trailing speculation
    ↓
[Output Validator Pipeline]
    ├─ Fact-grounding check (NLI entailment)
    ├─ Copyright similarity check (embedding + BLEU)
    ├─ PII detection and redaction
    └─ Format compiler (citations, confidence badge)
    ↓
Final Response (Answer + Confidence + Sources + Gaps + Metadata)
    ↓
[Audit Logger] (append-only, signed)
```

### 3.2 Guardrails

Guardrails operate at three levels:

**Pre-generation**:
- Intent classification blocks non-factual queries
- Retrieval confidence threshold: if <1 high-quality source → early refusal
- Input sanitization prevents prompt injection

**Generation-time**:
- System prompt strictly limits output to provided sources
- Logit bias suppresses tokens associated with speculation ("maybe", "perhaps", "I think")
- Constrained decoding: maximum 1024 tokens, stop at EOS or "Sources:"

**Post-generation**:
- Sentence-wise NLI validation: each claim must be entailed by at least one source
- Copyright similarity: regenerate if exceeding threshold (max 2 retries)
- Plagiarism check: uniqueness threshold enforced
- Final formatter ensures citation formatting and uncertainty markers

### 3.3 Knowledge Corpus

The knowledge base consists of:

1. **Primary Corpus**: Curated, human-vetted sources
   - Wikipedia EN dump (filtered to ` articles_with_citations` subset)
   - Scientific databases (PubMed Central open access, arXiv)
   - Government publications (data.gov, census.gov, etc.)
   - Technical manuals (Apache, Kubernetes, Python docs — permissive licenses)

2. **Secondary Corpus** (optional, user-provided):
   - Private company documents (with provenance hash)
   - Custom knowledge base uploads (PDF, DOCX, HTML)
   - Must pass integrity verification before indexing

3. **Live Sources** (configurable, disabled by default):
   - Approved APIs: PubMed, IEEE Xplore, .gov endpoints
   - Accessed only when explicitly enabled in `sources.yaml`
   - Results timestamped and cached for 24h

All corpus content is versioned with SHA-256 hashes stored in `knowledge/manifest.json`. Delta updates delivered as signed packs; full re-index required only for major version changes.

---

## 4. CONFIGURATION PROTOCOL

All system behavior is controlled by JSON/YAML configuration files placed in `config/`. Changes take effect after service restart.

### 4.1 config/rules.json

```json
{
  "version": "1.0.0",
  "description": "Token and claim evaluation rules",
  "token_rules": [
    {"pattern": "\\b(definitely|certainly|undeniably)\\b", "risk": 0.8, "action": "suppress"},
    {"pattern": "\\b(probably|might|maybe|perhaps)\\b", "risk": 0.3, "action": "flag"},
    {"pattern": "\\b(I think|in my opinion|personally)\\b", "risk": 0.1, "action": "allow"}
  ],
  "fact_rules": [
    {"type": "unsourced_claim", "condition": "no_citation_in_text", "action": "require_citation"},
    {"type": "unverified_statistic", "condition": "contains_number_percentage", "action": "cross_check"},
    {"type": "temporal_claim", "condition": "contains_date_time", "action": "verify_recency"}
  ],
  "copyright_rules": [
    {"type": "long_quote", "threshold_chars": 50, "action": "summarize_or_attribute"},
    {"type": "high_similarity", "threshold_bleu": 0.3, "threshold_cosine": 0.6, "action": "block"},
    {"type": "plagiarism_risk", "threshold_uniqueness": 0.2, "action": "regenerate"}
  ],
  "pii_rules": [
    {"entity_type": "PERSON", "action": "redact"},
    {"entity_type": "EMAIL_ADDRESS", "action": "redact"},
    {"entity_type": "PHONE_NUMBER", "action": "redact"}
  ]
}
```

### 4.2 config/boundaries.json

```json
{
  "allowed_domains": [
    "science", "technology", "history", "geography", "mathematics",
    "physics", "chemistry", "biology", "medicine", "law", "economics"
  ],
  "restricted_claim_types": [
    "medical_advice", "legal_advice", "financial_investment",
    "personal_opinion", "predictive_projection", "creative_writing"
  ],
  "verification_sources": [
    "wikipedia", "pubmed", "arxiv", "gov_data", "ieee"
  ],
  "min_source_confidence": 0.7,
  "max_age_days": 365
}
```

### 4.3 config/thresholds.json

```json
{
  "retrieval": {
    "top_k": 5,
    "similarity_threshold": 0.65,
    "min_results_high_confidence": 3
  },
  "generation": {
    "max_tokens": 1024,
    "temperature": 0.0,
    "top_p": 1.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0
  },
  "validation": {
    "nli_threshold": 0.8,
    "copyright_bleu_threshold": 0.3,
    "copyright_cosine_threshold": 0.6,
    "plagiarism_threshold": 0.2,
    "max_regeneration_attempts": 2
  },
  "audit": {
    "retention_days": 365,
    "hmac_key_rotation_days": 30,
    "encryption_enabled": false
  },
  "performance": {
    "timeout_retrieval_ms": 500,
    "timeout_generation_ms": 3000,
    "cache_ttl_seconds": 3600
  }
}
```

### 4.4 config/sources.yaml

```yaml
corpus_sources:
  - id: "wikipedia_202406"
    type: "vector_store"
    path: "knowledge/embeddings/wikipedia_202406.faiss"
    metadata: "knowledge/processed/wikipedia_202406_meta.jsonl"
    license: "CC-BY-SA-4.0"
    enabled: true
    freshness_days: 90

  - id: "pubmed_open"
    type: "api"
    endpoint: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    db: "pmc"
    enabled: false  # opt-in only

  - id: "user_documents"
    type: "local"
    path: "knowledge/raw/user_uploads/"
    requires_signature: true
    enabled: true

llm:
  primary:
    provider: "openai"
    model: "gpt-4-turbo-preview"
    api_key_env: "OPENAI_API_KEY"
    timeout: 30

  fallback:
    provider: "local"
    model: "llama3:8b-instruct-q4_K_M"
    endpoint: "http://localhost:11434/api/generate"
    enabled: true
```

### 4.5 config/llm_config.json

```json
{
  "providers": {
    "openai": {
      "api_base": "https://api.openai.com/v1",
      "models": ["gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
      "rate_limit_rpm": 500
    },
    "anthropic": {
      "api_base": "https://api.anthropic.com/v1",
      "models": ["claude-3-opus-20240229", "claude-3-sonnet-20240229"],
      "rate_limit_rpm": 200
    },
    "local": {
      "providers": ["ollama", "llama_cpp"],
      "ollama_url": "http://localhost:11434",
      "default_model": "llama3:8b-instruct-q4_K_M"
    }
  },
  "default_provider": "openai",
  "fallback_enabled": true,
  "max_retries": 3,
  "retry_delay_seconds": 1
}
```

---

## 5. MODULE RESPONSIBILITIES

### 5.1 Core Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| `assistant.py` | `src/backend/core/assistant.py` | Orchestrate full pipeline: retrieval → generation → validation → formatting |
| `validators.py` | `src/backend/core/validators.py` | Multi-layer validation: risk scoring, factual boundary check, copyright, PII |
| `fact_checker.py` | `src/backend/core/fact_checker.py` | Cross-source verification using NLI model (DeBERTa-v3) |
| `contradiction.py` | `src/backend/core/contradiction.py` | Detect and surface conflicting claims across sources |
| `intent_classifier.py` | `src/backend/core/intent_classifier.py` | Route queries: factual vs non-factual, domain detection |
| `auditor.py` | `src/backend/core/auditor.py` | Append-only audit logger with HMAC signing, export to compliance reports |

### 5.2 Retrieval Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| `vector_store.py` | `src/backend/retrieval/vector_store.py` | FAISS index wrapper: add, search, persist, load |
| `searcher.py` | `src/backend/retrieval/searcher.py` | Hybrid search combining vector + BM25 with metadata filters |
| `document_loader.py` | `src/backend/retrieval/document_loader.py` | Ingest PDF/DOCX/HTML → extracted text + metadata JSONL |
| `ingest_service.py` | `src/backend/retrieval/ingest_service.py` | Batch/streaming corpus ingestion with deduplication |

### 5.3 Model Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| `wrapper.py` | `src/backend/models/wrapper.py` | LLM provider abstraction (OpenAI, Anthropic, local) |
| `constrained_gen.py` | `src/backend/models/constrained_gen.py` | Guardrails: prompt engineering, logit bias, token suppression |
| `verifier_model.py` | `src/backend/models/verifier_model.py` | NLI model for entailment checking (offline, cached) |
| `prompt_templates.py` | `src/backend/models/prompt_templates.py` | System prompts per domain and confidence level |

### 5.4 Utility Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| `formatter.py` | `src/backend/utils/formatter.py` | Output renderer producing structured Response JSON |
| `citation.py` | `src/backend/utils/citation.py` | Generate inline citations [1], [2] + bibliography |
| `similarity.py` | `src/backend/utils/similarity.py` | BLEU and embedding cosine similarity for plagiarism detection |
| `sanitizer.py` | `src/backend/utils/sanitizer.py` | PII detection and redaction using Presidio |
| `cache.py` | `src/backend/utils/cache.py` | Redis wrapper for embedding cache and query result cache |
| `crypto.py` | `src/backend/utils/crypto.py` | HMAC-SHA256 signing for audit logs, optional AES-256 encryption |

### 5.5 Service Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| `knowledge_service.py` | `src/backend/services/knowledge_service.py` | High-level orchestration: retrieval → synthesis → validation |
| `auth_service.py` | `src/backend/services/auth_service.py` | API key validation and rate limiting (optional) |
| `feedback_service.py` | `src/backend/services/feedback_service.py` | Capture user flags, queue for admin review |
| `update_service.py` | `src/backend/services/update_service.py` | Corpus delta pack application, freshness checks, version management |

---

## 6. DATA SCHEMAS

### 6.1 Response Schema (output to user)

```json
{
  "id": "uuid-v4",
  "answer": "Photosynthesis is the process by which plants convert sunlight into chemical energy...",
  "confidence": "High",  // enum: High, Medium, Low
  "sources": [
    {
      "id": 1,
      "title": "Photosynthesis - Wikipedia",
      "author": "Wikipedia contributors",
      "organization": "Wikimedia Foundation",
      "date": "2024-06-15",
      "url": "https://en.wikipedia.org/wiki/Photosynthesis",
      "license": "CC-BY-SA-4.0",
      "excerpt": "Photosynthesis is a system of biological processes..."
    }
  ],
  "gaps": [
    "Detailed molecular mechanism of photosystem II remains under investigation"
  ],
  "warnings": [],
  "model_version": "gpt-4-turbo-2024-04-09",
  "timestamp": "2025-08-26T16:22:06Z",
  "processing_time_ms": 1250,
  "query_hash": "sha256:abc123..."
}
```

### 6.2 Audit Log Entry Schema

```json
{
  "log_id": "uuid-v4",
  "timestamp": "2025-08-26T16:22:06Z",
  "query_hash": "sha256:abc123...",
  "user_id": null,  // or session_id
  "query_text": "What is photosynthesis?",
  "intent": "factual",
  "retrieval": {
    "sources_queried": ["wikipedia_202406"],
    "excerpts_retrieved": 3,
    "retrieval_time_ms": 142
  },
  "generation": {
    "model": "gpt-4-turbo-preview",
    "provider": "openai",
    "prompt_tokens": 512,
    "completion_tokens": 156,
    "total_tokens": 668,
    "generation_time_ms": 980
  },
  "validation": {
    "fact_check_passed": true,
    "fact_check_score": 0.92,
    "copyright_check_passed": true,
    "copyright_bleu_score": 0.08,
    "plagiarism_check_passed": true,
    "pii_redactions": 0,
    "contradictions_detected": 0
  },
  "response_id": "uuid-v4",
  "signature": "hmac-sha256:def456..."
}
```

### 6.3 Knowledge Manifest Schema

```json
{
  "corpus_version": "2024.06.1",
  "generated_at": "2024-06-30T00:00:00Z",
  "sources": [
    {
      "source_id": "wikipedia_202406",
      "source_type": "vector_store",
      "file_path": "knowledge/embeddings/wikipedia_202406.faiss",
      "metadata_path": "knowledge/processed/wikipedia_202406_meta.jsonl",
      "sha256": "abc123def456...",
      "document_count": 6234500,
      "license": "CC-BY-SA-4.0",
      "freshness_days": 90
    }
  ],
  "total_documents": 6234500,
  "total_embeddings": 6234500,
  "embedding_model": "all-MiniLM-L6-v2",
  "index_type": "Flat"
}
```

---

## 7. SECURITY PROTOCOLS

### 7.1 Input Sanitization
- Maximum query length: 4,096 characters
- Maximum history depth: 20 turns
- Strip control characters, normalize Unicode (NFC)
- Reject requests with suspicious patterns: `ignore previous`, `role: system`, `<think>` tags

### 7.2 Rate Limiting
- Per-IP token bucket: 100 requests / minute (burst 10)
- Per-API-key: 1,000 requests / minute (configurable)
- Backoff: exponential with jitter, max 60s wait

### 7.3 Audit Integrity
- Each audit log entry includes HMAC-SHA256 signature
- Key rotated every 30 days (configurable)
- Optional AES-256 encryption of entire `audit.db` at rest
- Immutable append-only design: no UPDATE or DELETE operations

### 7.4 Data Privacy
- No personal data collected by default
- If user history enabled: AES-256 encryption per-session
- PII automatically redacted before storage in logs
- GDPR compliance: right to delete via `/api/history/delete_all`

---

## 8. PERFORMANCE REQUIREMENTS

| Metric | Target | Measurement |
|--------|--------|-------------|
| Retrieval latency (p50) | <200ms | Embedded FAISS on SSD |
| Retrieval latency (p95) | <500ms | 95th percentile |
| End-to-end response time (p95) | <3s | Network + LLM + validation |
| Embedding generation (per doc) | <50ms | CPU-optimized |
| Index rebuild (1M docs) | <2h | Single-core, RAM ≥16GB |
| Concurrent users | 50 | Per docker-compose instance |
| Cache hit rate | ≥40% | Redis query/embedding cache |

---

## 9. ERROR HANDLING PHILOSOPHY

**Principle**: Fail loudly, fail safely, never speculate.

- Retrieval returns 0 results → immediate refusal: "No verified information found."
- LLM API timeout → retry 3× with backoff → fallback to local model if available → else refusal
- Validation failure after 2 regeneration attempts → refusal with detailed violation report
- Unexpected exception → log to audit, return 500 with generic error, no stack trace to user
- Corrupted audit log entry → flag integrity violation, halt startup if HMAC mismatch

---

## 10. DEVELOPMENT STANDARDS

### 10.1 Code Quality
- Python: type hints everywhere, mypy strict mode
- JavaScript/TypeScript: ESLint + Prettier
- Pre-commit hooks: black, ruff, mypy, eslint
- Docstrings: Google style

### 10.2 Testing
- Unit coverage: ≥80% on core modules
- Integration: 100-question benchmark (NaturalQuestions subset)
- E2E: Playwright tests covering all user journeys
- Load: Locust 50 concurrent users, 10-minute sustained

### 10.3 Documentation
- README: quick start (5 min Docker), features, architecture
- API docs: auto-generated from FastAPI OpenAPI
- Developer guide: module architecture, extension points
- User guide: "How Verity Works" transparency page in UI
- Governance doc: knowledge corpus curation, update schedule, audit policy

---

## 11. DEPLOYMENT MODEL

### 11.1 Local Development

```bash
# Clone repository
git clone <repo_url>
cd verity-assistant

# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies
cd src/frontend && npm install && cd ../..

# Download sample Wikipedia corpus (100 articles)
python scripts/download_sample_corpus.py

# Build vector index
python scripts/build_index.py --input knowledge/raw --output knowledge/embeddings

# Start backend
uvicorn src.backend.main:app --reload --port 8000

# Start frontend (separate terminal)
cd src/frontend && npm run dev
```

Access UI: http://localhost:5173

### 11.2 Production (Docker Compose)

```bash
docker-compose up --build -d
```

Services:
- `verity-backend` (FastAPI, port 8000)
- `verity-frontend` (nginx, port 80)
- `redis` (cache & rate-limiting)
- `vector-store` (FAISS files mounted as volume)

### 11.3 Cloud Deployment

Terraform scripts provided for AWS ECS, GCP Cloud Run, Azure Container Apps. Environment variables for secrets (API keys, HMAC key). Managed PostgreSQL (RDS) for multi-user history, S3/GCS for knowledge storage.

---

## 12. MAINTENANCE & GOVERNANCE

### 12.1 Knowledge Corpus Updates

- Automated check: daily at 03:00 UTC
- Delta pack downloaded from trusted update server (signed with GPG)
- Signature verified before application
- Index incrementally updated; zero downtime
- Minimum freshness enforced: if corpus >90 days old, refuse new queries (configurable)

### 12.2 Model Updates

- Model version tracked in every response
- New model releases staged: shadow mode (10% traffic) → canary → full rollout
- A/B testing framework for guardrail effectiveness
- Rollback procedure: `scripts/rollback_model.py`

### 12.3 Audit Retention

- Raw audit logs: 365 days retention default
- After 90 days: aggregated statistics kept, raw entries archived to S3/GCS
- GDPR deletion: `services/feedback_service.delete_user_data(user_id)`
- Export: `/admin/audit/export?format=pdf` for compliance officers

### 12.4 Feedback Loop

User-flagged responses enter review queue:
1. Admin inspects flagged response + sources + audit log
2. Determine root cause: retrieval miss, LLM hallucination, citation error
3. Remediation: re-index document, update rules, retrain verifier model, or acknowledge error
4. Update knowledge base if factual gap identified
5. Close flag with resolution notes

Monthly review: top 10 flagged topics → prioritize knowledge gaps

---

## 13. ETHICAL BOUNDARIES

The assistant shall not:

1. Generate content for: military weapons, illegal activities, hate speech, non-consensual intimate imagery
2. Provide instructions for breaching computer security or violating laws
3. impersonate individuals or entities
4. Offer medical diagnosis, legal advice, or financial investment guidance (explicitly refused)
5. Store or infer user preferences for profiling without explicit consent

These boundaries are encoded in `intent_classifier.py` and `validators.py` with zero-tolerance blocking.

---

## 14. TRANSPARENCY DISCLOSURE

Every new user session displays:

> **Verity Assistant — Operational Disclosure**
>
> I am an in-application AI assistant. My knowledge comes from a curated set of sources approved by the application owner. I do not access real-time public internet data unless explicitly configured to do so. I never speculate; if evidence is insufficient, I will say so. Every answer includes citations and a confidence indicator. I am designed to prevent misappropriation of copyrighted material. My responses are logged for quality assurance and compliance.

This message is accessible at any time via the "About Verity" link in the UI.

---

## 15. VERSIONING & COMPATIBILITY

- **API versioning**: `/api/v1/` endpoints; backward-compatible for 2 years
- **Knowledge schema versioning**: manifest includes `schema_version` field; migrations automated
- **Model versioning**: Each response records exact model ID; old responses remain viewable
- **Breaking changes**: Major version bump with 6-month deprecation period

---

## APPENDIX A: GLOSSARY

| Term | Definition |
|------|------------|
| Hermetic Scope | Limited to approved knowledge sources; no unmonitored external access |
| Factual Grounding | Every claim directly attributable to a source excerpt |
| Misappropriation | Reproduction of copyrighted material without attribution/permission |
| Deterministic Decoding | Temperature=0 generates same output given identical input |
| Delta Pack | Incremental knowledge corpus update (diff from previous version) |
| NLI (Natural Language Inference) | Textual entailment model determining if premise supports hypothesis |
| Guardrails | Mechanisms preventing generation of disallowed content |
| Tamper-Evident Log | Immutable log with cryptographic signatures detecting modifications |

---

**Document Version**: 1.0  
**Effective Date**: 2025-08-26  
**Authority**: Biological Human Leader (supreme jurisdictional authority)  
**Compliance**: All system components must adhere to this doctrine; deviations require written authorization.
