# Architecture

## System Overview

```
                          ┌──────────────────────────────┐
                          │        Locust (testing)       │
                          └──────────────┬───────────────┘
                                         │
                          ┌──────────────▼───────────────┐
                          │     Gunicorn (17 workers)     │
                          │  ┌─────────────────────────┐  │
                          │  │  FastAPI + Uvicorn       │  │
                          │  │  (async event loop)      │  │
                          │  │                          │  │
                          │  │  GET  /health            │  │
                          │  │  GET  /metrics           │  │
                          │  │  GET  /products          │  │
                          │  │  POST /products          │  │
                          │  └──────┬──────────┬───────┘  │
                          └─────────┼──────────┼──────────┘
                                    │          │
                        ┌───────────▼──┐  ┌────▼──────────┐
                        │  Redis 7     │  │ PostgreSQL 15  │
                        │  (cache)     │  │ (persistence)  │
                        │  TTL: 10s    │  │ max_conn: 300  │
                        └──────────────┘  └───────────────┘

                          ┌──────────────────────────────┐
                          │  Prometheus → Grafana         │
                          │  (scrapes /metrics every 5s)  │
                          └──────────────────────────────┘
```

## Request Flow

### GET /products (cache hit)

```
Client → Gunicorn → Worker → FastAPI → Redis → Response (< 5ms)
```

No database touched. ~90% of GET requests follow this path.

### GET /products (cache miss)

```
Client → Gunicorn → Worker → FastAPI → Redis (miss) → PostgreSQL → Redis (set) → Response
```

Result is cached for 10 seconds. Next identical request will be a cache hit.

### POST /products

```
Client → Gunicorn → Worker → FastAPI → PostgreSQL (INSERT) → Redis (invalidate) → Response
```

After creating a product, all cached product lists are invalidated so the next GET returns fresh data.

### GET /health

```
Client → FastAPI → PostgreSQL (SELECT 1) + Redis (PING) → 200 or 503
```

Checks connectivity to both dependencies. Used by Docker health checks and load balancers.

## File Structure

```
FastAPI-Production/
├── main.py                  # App setup, endpoints, health check, metrics
├── database.py              # Async engine, session factory, get_db dependency
├── models.py                # SQLAlchemy Product model
├── schemas.py               # Pydantic request/response schemas
├── cache.py                 # Redis cache (get, set, invalidate)
├── gunicorn.conf.py         # Multi-worker production config
├── locustfile.py            # Load test scenarios
├── Dockerfile               # Multi-stage build
├── docker-compose.yml       # Full stack (5 services)
├── prometheus.yml           # Prometheus scrape config
├── .env                     # Environment variables (not in git)
├── .env.example             # Template for environment variables
├── .dockerignore            # Files excluded from Docker build
├── pyproject.toml           # Dependencies (managed by uv)
├── uv.lock                  # Locked dependency versions
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasource.yml   # Prometheus as data source
│   │   └── dashboards/
│   │       └── dashboard.yml    # Dashboard auto-provisioning
│   └── dashboards/
│       └── fastapi.json         # FastAPI Production dashboard
└── production-metrics/
    ├── load-testing-guide.md    # How to load test
    ├── performance-journey.md   # Optimization history
    ├── deployment-guide.md      # How to deploy
    └── architecture.md          # This file
```

## Technology Choices

| Layer | Technology | Why |
|-------|-----------|-----|
| **Framework** | FastAPI | Async-native, auto OpenAPI docs, Pydantic validation |
| **ASGI Server** | Uvicorn | High-performance async server for Python |
| **Process Manager** | Gunicorn | Multi-worker, production-tested, graceful restarts |
| **ORM** | SQLAlchemy (async) | Industry standard, connection pooling, migration support |
| **DB Driver** | asyncpg | Fastest async PostgreSQL driver for Python |
| **Database** | PostgreSQL 15 | ACID, indexes, full-text search, battle-tested |
| **Cache** | Redis 7 | Sub-millisecond reads, async client, TTL support |
| **Metrics** | Prometheus + prometheus-fastapi-instrumentator | Auto-instruments all endpoints, industry standard |
| **Dashboards** | Grafana | Real-time visualization, alerting, free |
| **Package Manager** | uv | Fast, deterministic, lockfile support |
| **Containerization** | Docker + Docker Compose | Reproducible builds, service orchestration |
| **Load Testing** | Locust | Python-based, web UI, realistic user simulation |

## Connection Pool Math

```
Gunicorn workers = (2 × CPU cores) + 1 = (2 × 8) + 1 = 17

Per worker:
  pool_size     = 10  (base connections)
  max_overflow  =  5  (burst connections)
  total         = 15

Across all workers:
  17 × 15 = 255 connections

PostgreSQL max_connections = 300
  255 for app + 45 headroom (admin, pgadmin, monitoring)
```

## Caching Strategy

| Action | Cache Behavior |
|--------|---------------|
| GET /products?page=1&page_size=20 | Cache key: `products:page=1:page_size=20` |
| GET /products?search=widget | Cache key: `products:page=1:page_size=20:search=widget` |
| POST /products | Invalidates all keys starting with `products:` |
| Cache TTL expires (10s) | Next GET rebuilds cache from PostgreSQL |

Trade-off: New products may take up to 10 seconds to appear in GET results. Acceptable for most applications.
