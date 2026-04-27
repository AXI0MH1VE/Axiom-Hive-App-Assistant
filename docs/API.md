# Verity Assistant API Reference

Base URL (development): `http://localhost:8000/api/v1`

Full auto-generated OpenAPI schema: `/docs` (Swagger UI), `/redoc` (ReDoc).

---

## Chat

### POST /chat

Submit a factual question.

**Request**

```json
{
  "query": "What is the speed of light?",
  "strict": false,
  "top_k": 5,
  "stream": false
}
```

**Response 200**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "The speed of light in a vacuum is 299,792,458 meters per second [1].",
  "confidence": "High",
  "sources": [
    {
      "id": 1,
      "title": "Speed of light - Wikipedia",
      "author": "Wikipedia contributors",
      "date": "2024-06-12",
      "url": "https://en.wikipedia.org/wiki/Speed_of_light",
      "license": "CC-BY-SA-4.0",
      "excerpt": "The speed of light in vacuum, commonly denoted c, is a universal physical constant..."
    }
  ],
  "gaps": [],
  "warnings": [],
  "model_version": "gpt-4-turbo-preview",
  "timestamp": "2025-08-26T21:00:00Z",
  "processing_time_ms": 1420,
  "query_hash": "sha256:abc123...",
  "metadata": {
    "intent": "factual",
    "strict_mode": false,
    "num_retrieved_sources": 5,
    "num_cited_sources": 1,
    "fact_check_passed": true
  }
}
```

### POST /chat/stream

Stream response tokens (Server-Sent Events). Not yet implemented; returns assembled response.

---

## Search

### GET /search

Retrieve source excerpts without LLM generation.

**Query Parameters**
- `q` (required): query string
- `top_k` (optional, default=5): max results

**Response 200**

```json
{
  "query": "photosynthesis",
  "results": [
    {
      "id": 1,
      "score": 0.89,
      "title": "Photosynthesis - Wikipedia",
      "excerpt": "Photosynthesis is a system of biological processes..."
    }
  ],
  "count": 1
}
```

---

## Knowledge Management

### POST /ingest

Add a new document to knowledge base.

**Request**

```json
{
  "file_path": "/app/knowledge/raw/mydoc.pdf",
  "metadata_override": {
    "author": "Dr. Jane Smith",
    "license": "CC-BY-4.0"
  }
}
```

**Response 200**

```json
{
  "success": true,
  "document_ids": [1001, 1002, 1003],
  "message": "Ingested 3 chunks"
}
```

---

## Feedback

### POST /feedback

Submit user feedback about a response.

**Request**

```json
{
  "response_id": "resp-uuid",
  "flag_type": "inaccurate",
  "description": "The answer about capital is wrong; should be Paris not Lyon."
}
```

**Response 200**

```json
{
  "feedback_id": "fb-uuid",
  "status": "submitted"
}
```

---

## Admin

### GET /admin/audit

Query audit log entries (admin auth required in production).

**Query Parameters**
- `event_type` (optional): filter by event type
- `user_id` (optional)
- `start_date`, `end_date` (optional): ISO timestamps
- `limit` (default=100)

### GET /admin/audit/export

Export audit log as JSONL or CSV.

`/admin/audit/export?format=csv&start_date=2025-01-01`

### GET /admin/stats

System health dashboard: vector_store size, cache hit rate, audit log counts, feedback stats.

### POST /admin/feedback/{id}/review

Update feedback status (admin only).

```json
{
  "status": "resolved",
  "resolution": "Fact-check confirmed error; article updated.",
  "reviewed_by": "admin"
}
```

---

## Health & Metrics

- `GET /health` – liveness probe (returns 200 if API running)
- `GET /ready` – readiness probe (checks vector store accessibility)
- `GET /metrics` – Prometheus-style metrics endpoint

---

## Error Handling

Standard HTTP status codes:
- 200 – success
- 400 – bad request (validation error)
- 401 – unauthorized (API key missing/invalid)
- 429 – rate limit exceeded
- 500 – internal error

Error response format:

```json
{
  "detail": "Human-readable error message"
}
```

---

## Rate Limits

Default: 100 requests per minute per IP (burst 10).

Configure in `config/thresholds.json` → `performance.rate_limit_*`.

API key holders can request higher limits.

---

## Versioning

API versioned via URL: `/api/v1/...`

Backward-compatible for at least 2 years. Breaking changes require major version bump and 6-month deprecation notice.
