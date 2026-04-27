# Governance & Knowledge Curation

This document defines operational policies for the Verity Assistant knowledge base, update process, audit, and continuous improvement.

---

## 1. Knowledge Corpus Curation

### Source Approval Process

All sources for the knowledge corpus must be:

1. **Authoritative** – published by recognized institution (university, government, standards body, peer-reviewed journal)
2. **Verifiable** – public or licensed with clear provenance; no anonymous claims
3. **Timestamped** – include publication/last-update date
4. **License-compatible** – allow redistribution under CC-BY, public domain, or commercial license with attribution

**Approval workflow:**
- Proposal submitted via GitHub issue or admin panel
- Review by at least two domain experts (internal or contracted)
- Decision recorded in `knowledge/manifest.json` with `"approved": true/false`
- Approved sources added to `config/sources.yaml` as `enabled: true`

### Content Standards

- **No primary research** (except from trusted preprint servers like arXiv with clear "preprint" label)
- **No opinion pieces**, editorials, or blog posts unless explicitly labeled and limited to `en: opinion` domain
- **Bias monitoring**: quarterly review of source diversity across geography, gender, institution
- **Recency**: scientific sources preferred ≤5 years old; historical sources can be older but flagged with date

### Update Cadence

- **Critical updates** (false facts, broken links): deploy within 24h
- **Regular updates**: weekly delta pack checks for modified sources
- **Major releases**: quarterly corpus rebuild with new source additions

---

## 2. Audit Policy

### Audit Log Retention

- **Raw logs**: 365 days in `data/audit/audit.db`
- **Aggregated metrics**: retained indefinitely
- **Archived logs**: after 90 days, compressed and moved to S3/GCS with lifecycle expiration (7 years)

### Audit Review Cycle

- **Daily**: automated integrity check (HMAC verification of last 100 entries)
- **Weekly**: admin reviews rate-limit violations and high-frequency error patterns
- **Monthly**: full audit report generated; includes:
  - Top denied queries (refusals)
  - Fact-check failure rate
  - Copyright detection incidents
  - Source citation distribution

### Tamper Detection

Every audit entry includes HMAC-SHA256 signature using rotating 256-bit key.
Key rotation every 30 days; old keys kept offline for 90 days to allow verification of archived logs.

If mismatch detected, system enters read-only mode and alerts admin.

---

## 3. Feedback & Continuous Improvement

### User Flagging

Users can flag responses as:
- **Inaccurate** – factually wrong
- **Missing citation** – source not properly attributed
- **Poor attribution** – paraphrasing masks copyrighted origin
- **Other** – free text

Flags enter `data/feedback_queue.json`; admin reviews within 72 hours.

### Root Cause Categories

| Failure mode | Remediation |
|---|---|
| **Retrieval miss** – relevant source not in top-k | Increase `top_k` or re-index with better chunking |
| **Hallucination** – claim not in any source | Adjust NLI threshold; prompt engineering |
| **Citation missing** – valid source used but not cited | Improve output formatter; train on citation format |
| **Copyright violation** – similarity > threshold | Add source to blacklist; regenerate |
| **Stale source** – factual error in original document | Remove/update source in corpus; add correction notice |

### Knowledge Base Updates

When factual error identified:
1. Remove or flag erroneous source in manifest
2. Add corrected version if available
3. Rebuild index to propagate fix (delta or full)
4. Notify users who received incorrect answer if identifiable (optional)

---

## 4. Model Governance

### Model Selection

Current `config/llm_config.json` specifies providers:
- **Primary**: OpenAI GPT-4-Turbo (highest accuracy)
- **Fallback**: Local Llama 3 8B (offline privacy)

Evaluation criteria for model changes:
- Fact-check pass rate on benchmark ≥99%
- Hallucination rate ≤1%
- Cost per 1k tokens ≤$0.01 (primary), unrestricted (local)

### Model Updates

When new model version arrives:
1. Shadow traffic: 10% of queries routed to new model, results logged
2. Compare factuality, latency, cost against baseline
3. If ≥5% improvement, promote to 50% canary
4. If stable for 1 week, full rollout
5. Record model version in `config/llm_config.json` and every response metadata

### Rollback

If degradation detected:
- Immediate 100% revert to previous model
- Publish incident report within 24h
- Root-cause analysis before next candidate

---

## 5. Security & Compliance

### GDPR / Data Privacy

- No personal data collected by default
- If user history enabled: AES-256 encryption per-session; right to delete via `DELETE /api/v1/history`
- Audit logs anonymized (user_id optional); IP addresses retained 30 days only

### Copyright Compliance

All source licenses tracked in `knowledge/manifest.json`. Queries with license=="proprietary" require explicit user permission before serving.

If copyright claim received:
- Remove disputed content from index
- Regenerate index without it
- Review fair use justification

### Export Controls

System designed for general information; not classified as dual-use. However, scientific queries could touch controlled-tech topics; consult legal before deploying in regulated environments.

---

## 6. Incident Response

### Severity Levels

| Severity | Criteria | Response Time |
|----------|----------|----------------|
| **P0-Critical** | System down, data breach, widespread hallucination | 15 minutes |
| **P1-High** | Major feature failure, audit tampering | 1 hour |
| **P2-Medium** | Non-critical bugs, minor performance degradations | 4 hours |
| **P3-Low** | Cosmetic issues, documentation updates | 24 hours |

### Runbooks

Located in `docs/runbooks/` (to be created):
- `restart_services.md`
- `rotate_hmac_key.md`
- `corpus_corruption_recovery.md`
- `model_fallback_failure.md`

---

## 7. Change Management

All changes require:
1. **Code review** by at least one peer
2. **Testing**: unit ≥80% coverage; integration passes 100-question benchmark
3. **Documentation update** if user-facing
4. **Staging validation** – deploy to staging environment, run smoke tests
5. **Post-deployment monitoring** – watch metrics for 24h

Emergency hotfixes: document deviation, follow up with full review within 48h.

---

## 8. Reporting

Monthly governance report includes:

- Corpus version and update summary
- Audit statistics (volume, top event types, integrity checks)
- Fact-check pass/fail rate trend
- User feedback summary and resolved items
- Cost analysis (LLM API spend, bandwidth)
- Security incidents or near-misses

Report available to stakeholders and archived for compliance.

---

*This governance model ensures Verity Assistant remains a trusted, accountable, and continually improving system aligned with its foundational doctrine.*
