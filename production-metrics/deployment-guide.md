# Deployment Guide

How to deploy the FastAPI Products API in different environments.

---

## Local Development

### Without Docker

```bash
# Prerequisites: PostgreSQL and Redis running locally

# Install dependencies
uv sync

# Set environment variables (or use defaults)
export DATABASE_URL="postgresql+asyncpg://myuser:mypassword@localhost:5432/mydb"
export REDIS_URL="redis://localhost:6379/0"

# Run with hot reload
uv run uvicorn main:app --reload
```

### With Docker (Full Stack)

```bash
# Start everything: app + postgres + redis + prometheus + grafana
docker compose up -d

# Check all services
docker compose ps

# View logs
docker compose logs -f app

# Stop everything
docker compose down

# Stop and delete all data (volumes)
docker compose down -v
```

### Service URLs (Local)

| Service | URL | Credentials |
|---------|-----|-------------|
| FastAPI API | http://localhost:8000/docs | — |
| Health Check | http://localhost:8000/health | — |
| Prometheus Metrics | http://localhost:8000/metrics | — |
| Prometheus UI | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / admin |
| PostgreSQL | localhost:5432 | myuser / mypassword |
| Redis | localhost:6379 | — |

---

## Production Deployment

### Run Commands

```bash
# Development (single worker, hot reload)
uv run uvicorn main:app --reload

# Production (multi-worker)
uv run gunicorn main:app -c gunicorn.conf.py

# Docker
docker compose up -d --build
```

### Environment Variables

| Variable | Description | Default | Production Example |
|----------|-------------|---------|-------------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://myuser:mypassword@localhost:5432/mydb` | `postgresql+asyncpg://user:pass@rds-host:5432/proddb` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` | `redis://elasticache-host:6379/0` |
| `CACHE_TTL` | Cache expiry in seconds | `10` | `10` - `60` depending on freshness needs |

### Gunicorn Configuration

Located in `gunicorn.conf.py`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `workers` | CPU × 2 + 1 | One worker per core, plus spare |
| `worker_class` | `uvicorn.workers.UvicornWorker` | Async event loop per worker |
| `timeout` | 120s | Kill workers that hang |
| `keepalive` | 5s | Keep connections open between requests |
| `max_requests` | 5000 | Restart workers to prevent memory leaks |
| `max_requests_jitter` | 500 | Stagger restarts so they don't all happen at once |

### Connection Pool Configuration

Located in `database.py`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `pool_size` | 10 | Base connections per worker |
| `max_overflow` | 5 | Extra connections under load |
| `pool_pre_ping` | True | Check connection health before use |
| `pool_recycle` | 300s | Refresh connections every 5 min |
| `pool_timeout` | 10s | Fail fast if no connection available |

**Total connections:** workers × (pool_size + max_overflow) = 17 × 15 = 255
**PostgreSQL max_connections:** 300 (leaves 45 for admin, pgadmin, monitoring)

---

## Health Checks

### Endpoint: GET /health

Returns status of all dependencies:

```json
// Healthy (200)
{
  "app": "healthy",
  "postgres": "healthy",
  "redis": "healthy"
}

// Unhealthy (503)
{
  "app": "healthy",
  "postgres": "unhealthy",
  "redis": "healthy"
}
```

Used by:
- Docker health checks (in docker-compose.yml)
- Load balancers (to route traffic away from unhealthy instances)
- Monitoring alerts (trigger when health check fails)

---

## Monitoring

### Prometheus Metrics (GET /metrics)

Automatically tracked:
- `http_requests_total` — request count by method, status, handler
- `http_request_duration_seconds` — response time histogram
- `http_requests_in_progress` — currently processing requests

### Grafana Dashboards

Pre-provisioned "FastAPI Production" dashboard with 5 panels:

1. **Requests Per Second** — total and per endpoint
2. **Response Time Percentiles** — p50, p95, p99
3. **Error Rate** — 4xx and 5xx errors per second
4. **Active Requests** — in-flight request count
5. **Response Time by Endpoint** — p95 per handler

### What to Watch

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| p95 response time | < 200ms | 200-500ms | > 500ms |
| Error rate | 0% | > 0.1% | > 1% |
| RPS | Stable | Dropping with same users | Flat while users increase |
| Health check | 200 | Intermittent 503 | Sustained 503 |

---

## Scaling Checklist

When you need to handle more traffic:

- [ ] Deploy on a dedicated server (not shared with other services)
- [ ] Use managed PostgreSQL (AWS RDS, GCP Cloud SQL)
- [ ] Use managed Redis (AWS ElastiCache, GCP Memorystore)
- [ ] Add a load balancer in front of multiple app servers
- [ ] Set up CI/CD pipeline for automated deployments
- [ ] Move secrets to a secrets manager (AWS Secrets Manager, Vault)
- [ ] Add TLS/HTTPS via load balancer or nginx
- [ ] Set up alerting (Grafana alerts or PagerDuty)
- [ ] Add database migrations (Alembic)
- [ ] Add read replicas if database is the bottleneck

---

## Docker Compose Services

```
docker-compose.yml
├── app          → FastAPI (builds from Dockerfile)
├── postgres     → PostgreSQL 15 (persistent volume)
├── redis        → Redis 7
├── prometheus   → Scrapes /metrics every 5s
└── grafana      → Dashboards (auto-provisioned)
```

### Rebuild After Code Changes

```bash
docker compose up -d --build app
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f app
```
