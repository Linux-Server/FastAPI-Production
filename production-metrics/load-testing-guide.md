# Load Testing Guide for FastAPI

## What is Load Testing?

Load testing simulates real users hitting your API to answer three questions:
1. **How fast** is my API under load? (response time)
2. **How much** traffic can it handle? (throughput / RPS)
3. **When does it break?** (breaking point)

Without load testing, you're guessing. With it, you know exactly what your API can handle before real users find out the hard way.

---

## Tools We Use

**Locust** — a Python-based load testing tool with a web UI.

- Run: `uv run locust`
- Open: `http://localhost:8089`
- Make sure your FastAPI server is running before starting Locust

---

## What to Set in Locust UI

There are 3 fields:

| Field | What it means | Example |
|-------|---------------|---------|
| **Number of users** | Total simulated users hitting your API at the same time | 50 |
| **Ramp up (users/sec)** | How many new users join every second until the target is reached | 10 |
| **Host** | The base URL of your running API | `http://localhost:8000` |

**Example:** 200 users with ramp up of 20 means Locust starts with 0 users, adds 20 every second, and reaches 200 users in 10 seconds. Then all 200 keep making requests until you stop.

---

## Testing Strategy (4 Rounds)

Run each round for **2-3 minutes**. Stop the current test before starting the next (click "Stop" then "New test").

| Round | Users | Ramp up | Purpose |
|-------|-------|---------|---------|
| 1 | 50 | 10 | **Baseline** — sanity check, everything should be green |
| 2 | 200 | 20 | **Normal load** — simulates typical production traffic |
| 3 | 500 | 50 | **Heavy load** — finds where performance starts degrading |
| 4 | 1000 | 100 | **Stress test** — finds the absolute breaking point |

### What to do between rounds

1. Note down: RPS, p95 response time, failure rate
2. Compare with the previous round
3. If Round N already shows failures > 5%, no need to go higher — you found the limit

---

## Understanding the Locust Charts

### Chart 1: Response Times

The top chart shows response times over time. Two lines matter:

- **Median (p50)** — half of requests are faster than this
- **95th percentile (p95)** — 95% of requests are faster than this

**Why p95 matters more than average:** If 95 requests take 10ms and 5 requests take 2000ms, the average is 109ms (looks fine), but p95 is 2000ms (tells you 1 in 20 users has a terrible experience).

| Response time | What it means |
|---------------|---------------|
| < 50ms | Excellent — API feels instant |
| 50-100ms | Great — no user will notice |
| 100-300ms | Good — acceptable for most applications |
| 300-500ms | Okay — users start noticing slight delay |
| 500ms-1s | Slow — noticeable lag, needs optimization |
| 1-3s | Bad — users get frustrated |
| > 3s | Critical — users will abandon the action |
| > 5s | Broken — most users will leave |

### Chart 2: Number of Users

Shows how many simulated users are active. This should ramp up to your target and stay flat. If it doesn't reach the target, Locust itself might be bottlenecking (rare).

### Chart 3: Requests Per Second (RPS)

Shows how many requests your API processes every second.

**Healthy pattern:**
```
Users increase → RPS increases proportionally
```

**Unhealthy pattern (saturation):**
```
Users: 100 → RPS: 200
Users: 200 → RPS: 350
Users: 500 → RPS: 360   ← RPS stopped growing = ceiling reached
Users: 1000 → RPS: 340  ← RPS drops = app is overloaded
```

When RPS flattens or drops while users increase, you've found your app's maximum capacity.

### Chart 4: Failures

Shows failed requests over time. In a healthy test, this line should stay at **zero**.

Common failure types:
- **ConnectionError** — your app crashed or ran out of connections
- **Timeout** — request took too long, Locust gave up
- **HTTP 500** — your app threw an unhandled error
- **HTTP 502/503** — server is overwhelmed

---

## Key Metrics and Production Targets

### The 5 Numbers to Record from Each Test

| Metric | What it tells you | How to find it |
|--------|-------------------|----------------|
| **p50 (median)** | Typical user experience | Response time chart or statistics table |
| **p95** | Worst experience for most users | Statistics table → 95% column |
| **p99** | Worst experience for almost all users | Statistics table → 99% column |
| **RPS** | Throughput — how much work your API does | RPS chart or "Aggregated" row in stats |
| **Failure %** | Reliability | Statistics table → Failures column |

### Production-Grade Targets

| Metric | Minimum | Good | Excellent |
|--------|---------|------|-----------|
| p50 response time | < 200ms | < 100ms | < 50ms |
| p95 response time | < 500ms | < 200ms | < 100ms |
| p99 response time | < 1000ms | < 500ms | < 200ms |
| Failure rate | < 1% | < 0.1% | 0% |
| RPS | Handles expected peak | 2x expected peak | 5x expected peak |

### Real-World Example

If your app has **10,000 daily active users**:
- Not all are online at once. Typically **5-10%** are active in peak hour
- 500-1000 concurrent users at peak
- Each user makes ~1 request every few seconds
- Expected peak: **~100-300 RPS**
- Your target: handle **600-1500 RPS** (2-5x headroom)

---

## How to Estimate Required RPS

| Daily Active Users | Peak Concurrent (5-10%) | Expected Peak RPS | Target RPS (3x buffer) |
|--------------------|-------------------------|--------------------|-----------------------|
| 100 | 5-10 | 2-5 | 15 |
| 1,000 | 50-100 | 10-50 | 150 |
| 10,000 | 500-1000 | 100-300 | 900 |
| 100,000 | 5000-10000 | 1000-5000 | 15,000 |
| 1,000,000 | 50000-100000 | 10000-50000 | 150,000 |

For > 10,000 RPS, you'd typically need multiple servers behind a load balancer, not just one machine.

---

## Common Bottlenecks and How to Fix Them

### 1. Database is slow (most common)

**Symptom:** Response times increase as data grows or users increase. CPU on app server is low, but DB CPU is high.

**Fixes:**
- Add database indexes on columns used in WHERE/ORDER BY
- Use pagination (don't load all rows at once)
- Add connection pooling (already done in our app)
- Add caching (Redis) for frequently read data

### 2. Not enough workers/processes

**Symptom:** RPS flattens early, CPU usage on the app server is low.

**Fixes:**
- Use gunicorn with multiple workers: `gunicorn main:app -c gunicorn.conf.py`
- Formula: `workers = (2 x CPU_cores) + 1`
- Each worker handles requests independently

### 3. Sync code blocking the event loop

**Symptom:** p95 spikes randomly even under low load.

**Fixes:**
- Use `async def` endpoints (not `def`)
- Use async database driver (`asyncpg`, not `psycopg2`)
- Never call `time.sleep()` or blocking I/O in async endpoints

### 4. Connection pool exhausted

**Symptom:** Sudden spike in failures (ConnectionError) when users exceed a threshold.

**Fixes:**
- Increase `pool_size` and `max_overflow` in database config
- Ensure connections are properly closed (use `Depends(get_db)`)
- Check for connection leaks (sessions not being closed)

### 5. Memory leak

**Symptom:** Response times gradually get worse over hours, app eventually crashes.

**Fixes:**
- Profile memory usage
- Ensure no unbounded lists/caches growing in memory
- Restart workers periodically (gunicorn `max_requests` setting)

---

## Single Worker vs Multi-Worker

| Setup | Command | Best for |
|-------|---------|----------|
| **Single worker (dev)** | `uvicorn main:app --reload` | Development, debugging |
| **Multi-worker (prod)** | `gunicorn main:app -c gunicorn.conf.py` | Production, handling real traffic |

**Why multi-worker matters:**
- Python has the GIL (Global Interpreter Lock) — one process can only use one CPU core
- Gunicorn spawns multiple processes, each with its own event loop and connection pool
- 4 CPU cores → 9 workers → roughly 9x the throughput of a single worker

---

## Testing Checklist

Before deploying to production, your API should pass these tests:

- [ ] **Baseline (50 users):** p95 < 100ms, 0% failures
- [ ] **Normal load (200 users):** p95 < 200ms, 0% failures
- [ ] **Heavy load (500 users):** p95 < 500ms, < 1% failures
- [ ] **Stress test (1000 users):** Know where the breaking point is
- [ ] **Endurance test (200 users, 30 minutes):** No memory leaks, no gradual degradation
- [ ] **Tested with gunicorn** (multi-worker), not just single uvicorn
- [ ] **Tested with realistic data** (not an empty database)
