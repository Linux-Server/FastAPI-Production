# Performance Optimization Journey

A record of every optimization made to the FastAPI Products API, what problem it solved, and the measurable impact.

---

## Starting Point

- **App**: Sync FastAPI with in-memory list storage
- **Endpoints**: GET /products, POST /products
- **Database**: None (data lost on restart)
- **Concurrency**: Single-threaded, blocking

---

## Phase 1: PostgreSQL Integration

**Problem:** No data persistence. Products disappear on server restart.

**Changes:**
- Added PostgreSQL 15 (Docker container on port 5432)
- SQLAlchemy ORM with `Product` model (id, name, price, description, created_at, updated_at)
- Pydantic schemas with input validation (name min/max length, price > 0)
- Pagination on GET endpoint (page, page_size, search)
- Error handling with proper HTTP status codes (409, 500, 503)

**Files created:** `database.py`, `models.py`, `schemas.py`

---

## Phase 2: Async Conversion

**Problem:** Sync endpoints block the event loop. Under load, requests queue behind each other.

**Changes:**
- Replaced `psycopg2-binary` (sync) with `asyncpg` (async PostgreSQL driver)
- Switched to `create_async_engine` + `AsyncSession`
- Converted all endpoints to `async def`
- Replaced `db.query()` with `select()` + `await db.execute()`
- Added `gunicorn` with `UvicornWorker` for multi-process serving
- Workers formula: `(2 × CPU cores) + 1` = 17 workers on 8-core machine

**Files changed:** `database.py`, `main.py`
**Files created:** `gunicorn.conf.py`

---

## Phase 3: Connection Pool Fix

**Problem:** 9.87% failure rate at 500 users. All failures were HTTP 500 — database connection pool exhausted.

**Root cause:** Each gunicorn worker had `pool_size=20, max_overflow=30` (50 connections per worker). With 17 workers, that's 850 potential connections, but PostgreSQL only allowed 100.

**Changes:**
- Reduced pool per worker to `pool_size=3, max_overflow=2` (5 per worker × 17 = 85, under 100 limit)
- Increased PostgreSQL `max_connections` from 100 → 300
- Added `pool_recycle=300` (refresh stale connections every 5 min)
- Added `pool_timeout=10` (fail fast instead of hanging)
- Added `OperationalError` handling → returns 503 instead of 500
- Added trigram index (`pg_trgm`) on product name for faster `ILIKE` search
- Added `max_requests=5000` in gunicorn for worker memory leak prevention

**Results:**

| Metric | Before | After |
|--------|--------|-------|
| Failure rate | 9.87% (4,155 fails) | 0% |
| Median response | 72 ms | 180 ms |
| Max response | 1,946 ms | 2,776 ms |

Trade-off: Higher median because connections now queue instead of failing. Correct behavior — better to be slightly slower than drop requests.

---

## Phase 4: Redis Caching

**Problem:** Every GET request hits PostgreSQL, even identical queries repeated within seconds.

**Changes:**
- Added Redis (async client via `redis` package)
- GET /products responses cached for 10 seconds (configurable via `CACHE_TTL` env var)
- Cache key includes page, page_size, search — different queries get different cache entries
- POST /products invalidates the cache so new data appears immediately
- Database pool increased to `pool_size=10, max_overflow=5` (now fits within 300 max_connections)

**Files created:** `cache.py`
**Files changed:** `main.py`, `database.py`

**Results (500 users):**

| Metric | Before Redis | After Redis |
|--------|-------------|-------------|
| Failure rate | 0% | 0.01% (3 connection resets) |
| RPS | 365 | 383 |
| Median | 180 ms | 8 ms |
| Avg | 259 ms | 25 ms |
| Max | 2,776 ms | 1,291 ms |

Massive improvement — median response dropped from 180ms to 8ms because ~90% of GET requests now serve from Redis cache instead of hitting PostgreSQL.

---

## Phase 5: Dockerization + Monitoring

**Problem:** No containerization, no observability, no health checks.

**Changes:**
- Multi-stage Dockerfile (python:3.12-slim, uv for dependency management)
- docker-compose.yml with 5 services: app, postgres, redis, prometheus, grafana
- Health check endpoint (`GET /health`) — checks app, PostgreSQL, and Redis connectivity
- Prometheus metrics via `prometheus-fastapi-instrumentator` — auto-tracks request count, response time histograms, error rates
- Metrics exposed at `GET /metrics`
- Grafana dashboard with 5 panels: RPS, Response Time Percentiles (p50/p95/p99), Error Rate, Active Requests, Response Time by Endpoint
- PostgreSQL container starts with `max_connections=300`
- Service health checks with dependency ordering (postgres/redis healthy → app starts → prometheus/grafana start)
- `.env.example` for environment variable documentation
- `.dockerignore` to keep images lean

**Files created:** `Dockerfile`, `docker-compose.yml`, `.env`, `.env.example`, `.dockerignore`, `prometheus.yml`, `grafana/provisioning/datasources/datasource.yml`, `grafana/provisioning/dashboards/dashboard.yml`, `grafana/dashboards/fastapi.json`
**Files changed:** `main.py` (added /health, /metrics)

**Dockerized Results (400 users):**

| Metric | Before Docker | Dockerized |
|--------|--------------|------------|
| Failures | 0% | 0% |
| RPS | 316.9 | 316.2 |
| Median | 8 ms | 4 ms |
| Avg | 10.2 ms | 5.2 ms |

---

## Final Performance Summary

All tests run with Locust, ~2 minute duration.

| Phase | Users | RPS | Median | Failures | Key Change |
|-------|-------|-----|--------|----------|------------|
| Sync + broken pool | 500 | 362 | 72 ms | 9.87% | Baseline |
| Pool fix | 500 | 365 | 180 ms | 0% | Right-sized pool |
| + Redis cache | 500 | 383 | 8 ms | 0.01% | Caching layer |
| + Docker stack | 400 | 316 | 4 ms | 0% | Containerized |
| Sustained load | 500 | 365 | 13 ms | 0.00% | 6 min, 147K requests |

---

## Architecture (Final State)

```
Locust (load testing)
  ↓
FastAPI App (gunicorn, 17 uvicorn workers)
  ├── GET /health     → checks postgres + redis
  ├── GET /metrics    → prometheus metrics
  ├── GET /products   → redis cache → postgres (on miss)
  └── POST /products  → postgres → invalidate cache
  ↓
PostgreSQL 15 (max_connections=300, trigram index)
Redis 7 (10s TTL cache)
Prometheus (scrapes /metrics every 5s)
Grafana (real-time dashboards)
```

---

## Key Lessons

1. **Profile before optimizing** — Locust revealed the real bottleneck was connection pool exhaustion, not slow queries
2. **Pool math matters** — workers × pool_size must fit within PostgreSQL max_connections
3. **Caching is the biggest win** — Redis dropped median from 180ms to 8ms (22x faster)
4. **Async alone isn't enough** — async helps concurrency, but without proper pool sizing it still breaks
5. **Monitor everything** — Grafana + Prometheus shows issues in real-time, not after users complain
