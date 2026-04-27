# Deployment Guide

Deploy Verity Assistant to local machine, VM, or cloud.

---

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Compose (local or single server)](#docker-compose)
3. [Production Checklist](#production-checklist)
4. [Cloud Deployment](#cloud-deployment)
   - [AWS](#aws)
   - [Google Cloud](#google-cloud)
   - [Azure](#azure)
5. [Monitoring & Observability](#monitoring)
6. [Scaling](#scaling)
7. [Backup & Recovery](#backup)

---

## Local Development

See `README.md` Quick Start. This section covers production-oriented deployment.

---

## Docker Compose

Single-command deployment suitable for VPS, on-prem server, or dev environment.

### Prerequisites
- Docker Engine 24+ and Docker Compose v2
- At least 8GB RAM, 4 CPU cores
- 20GB disk space

### Steps

1. Clone repository to server:
   ```bash
   git clone <repo_url>
   cd verity-assistant
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env:
   # - Set OPENAI_API_KEY (or enable local LLM)
   # - Set AUDIT_HMAC_KEY (generate with: openssl rand -hex 32)
   # - Optionally set API_KEY_REQUIRED=true and ADMIN_API_KEY
   ```

3. Prepare knowledge corpus:
   ```bash
   # Option A: Download sample (100 articles)
   python scripts/download_sample_corpus.py

   # Option B: Ingest your own documents into knowledge/raw/
   # Then build index:
   python scripts/build_index.py
   ```

4. Deploy:
   ```bash
   docker-compose up -d
   ```

5. Verify:
   ```bash
   docker-compose ps  # All services healthy
   curl http://localhost/health
   ```

   UI: http://localhost  
   API: http://localhost:8000  
   Swagger: http://localhost:8000/docs  

### Updates

```bash
git pull
docker-compose down
docker-compose up --build -d
```

Corpus updates applied automatically on startup if update endpoint configured.

---

## Production Checklist

Before exposing to users:

- [ ] **HTTPS**: Terminate TLS at reverse proxy (nginx/Traefik)
- [ ] **Secrets**: Generate strong `AUDIT_HMAC_KEY`; rotate API keys
- [ ] **Firewall**: Only expose ports 80/443; block 8000 from public
- [ ] **Database**: Backup `data/audit/` daily; encrypted at rest if required
- [ ] **Rate limiting**: Enabled; set per-user limits
- [ ] **Monitoring**: Configure Prometheus/Grafana; health checks active
- [ ] **Redis**: Enable for caching (`REDIS_ENABLED=true`)
- [ ] **Logging**: Forward container logs to centralized system
- [ ] **Updates**: Schedule corpus refresh (daily via cron)

---

## Cloud Deployment

### AWS

**Option A: ECS with Fargate (serverless containers)**
```bash
# 1. Push images to ECR
aws ecr create-repository --repository-name verity-backend
aws ecr create-repository --repository-name verity-frontend

docker build -t verity-backend -f docker/Dockerfile.backend .
docker tag verity-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/verity-backend:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/verity-backend:latest

# 2. Deploy via Terraform (see terraform/ecs/)
terraform apply
```

**Option B: EC2 VM**
```bash
# SSH to Ubuntu 22.04
sudo apt update && sudo apt install -y docker.io docker-compose git
git clone <repo>
cd verity-assistant
docker-compose up -d
```

Configure nginx reverse proxy and certbot for Let's Encrypt.

### Google Cloud

**Cloud Run (fully managed containers)**

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/verity-backend docker/Dockerfile.backend
gcloud run deploy verity-backend --image gcr.io/PROJECT_ID/verity-backend --platform managed --region us-central1

# Frontend
gcloud builds submit --tag gcr.io/PROJECT_ID/verity-frontend docker/Dockerfile.frontend
gcloud run deploy verity-frontend --image gcr.io/PROJECT_ID/verity-frontend ...
```

Set environment variables via `--set-env-vars`.

### Azure

**Azure Container Apps**

```bash
az containerapp create \
  --name verity-backend \
  --resource-group my-rg \
  --environment my-env \
  --image <acr>.azurecr.io/verity-backend:latest \
  --target-port 8000 \
  --env-vars OPENAI_API_KEY=xxx AUDIT_HMAC_KEY=yyy
```

Use Azure Container Registry (ACR) for images.

---

## Monitoring

### Health Endpoints

- `/health` – liveness probe (returns 200 if API process alive)
- `/ready` – readiness probe (checks vector store connectivity, LLM API keys valid)
- `/metrics` – Prometheus metrics (requires `ENABLE_PROMETHEUS=true`)

### Logs

Docker: `docker-compose logs -f backend`

Production: Ship to ELK/Graylog/Datadog. Suggested log levels:
- `INFO` default
- `DEBUG` for troubleshooting
- `AUDIT` channel separate from application logs

### Metrics to monitor

| Metric | Target | Alert threshold |
|--------|--------|-----------------|
| API response latency p95 | <3s | >5s |
| Vector store retrieval latency p95 | <500ms | >1s |
| Audit log write failures | 0 | >0 |
| Rate limit rejections | monitor spike | +50% vs baseline |
| LLM API errors | <1% | >5% |

Grafana dashboard JSON provided in `monitoring/dashboards/`.

---

## Scaling

### Vertical (single instance)

Increase resources:
- RAM: 16GB → 32GB improves cache hit rate
- CPU: 4 cores → 8 cores reduces retrieval latency
- SSD storage: faster index loading

### Horizontal (multiple instances)

Stateless API; scale by running multiple backend replicas behind load balancer.

```yaml
# docker-compose.yml
services:
  backend:
    deploy:
      replicas: 4
    # Shared volumes for knowledge and audit DB require NFS or S3; or use external DB
```

Consider externalizing:
- **Vector store**: Qdrant server or Weaviate cluster (instead of FAISS on filesystem)
- **Audit DB**: PostgreSQL with connection pooling
- **Cache**: Dedicated Redis cluster

---

## Backup & Recovery

### What to backup

- `knowledge/` directory (corpus + embeddings + manifest)
- `data/audit/audit.db` (transaction log)
- `.env` configuration (secrets stored in vault preferred)
- `docker-compose.yml` and `config/` (infrastructure as code)

### Schedule

| Asset | Frequency | Retention |
|-------|-----------|-----------|
| Audit DB | Hourly (incremental) | 90 days |
| Knowledge corpus | Before each update | 2 versions |
| Config files | Every commit | Git history |

### Recovery procedure

1. Stop services: `docker-compose down`
2. Restore `knowledge/` directory from backup
3. Restore `data/audit/audit.db` from latest dump
4. Rebuild index if needed: `python scripts/build_index.py`
5. Restart: `docker-compose up -d`

---

## Troubleshooting Deployment

### Services fail to start
- Check `.env` syntax (no quotes around values)
- Verify ports 80/8000 free
- View logs: `docker-compose logs backend`

### High latency
- Check GPU/CPU usage; consider local LLM fallback disabled
- Enable Redis cache
- Reduce `top_k` from 5 → 3

### Out of disk space
- Audit DB can grow quickly; reduce `retention_days`
- Archive old `logs/` files to object storage

---

## Security Hardening

Additional steps for external deployment:

1. **TLS**: Obtain certificate (Let's Encrypt or commercial), configure nginx in frontend container or external LB
2. **WAF**: Place Web Application Firewall (Cloudflare, AWS WAF) to block OWASP Top 10
3. **Secrets**: Use Docker secrets or HashiCorp Vault instead of .env
4. **Network segmentation**: Frontend ↔ backend in private subnet; DB in isolated subnet
5. **Upload scanning**: If `/ingest` exposed, integrate ClamAV for malware check
6. **Dependency scanning**: CI/CD runs `safety check` and `pip-audit` on every build

---

**Next**: [GOVERNANCE.md] – knowledge curation, audit policy, update process.
