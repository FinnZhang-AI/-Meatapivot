# k6 Performance Tests

S6-1: 性能压测与优化 — P50 < 100ms, P95 < 500ms, 100并发 0 5xx

## Prerequisites

Install k6:
```bash
# macOS
brew install k6

# Linux
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# Docker
docker pull grafana/k6
```

## Test Environment

Start backend with seed data:
```bash
# Start full stack
docker-compose up -d postgres neo4j backend

# Wait for backend
until curl -s http://localhost:8000/health | grep -q healthy; do sleep 2; done

# Create perf test user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"perftest@example.com","password":"perftest123","name":"Perf Test","tenant_id":"00000000-0000-0000-0000-000000000001"}'
```

## Test Scripts

| Script | Purpose | Pass Criteria |
|--------|---------|---------------|
| `smoke-test.js` | Basic functionality (1 VU, 10s) | 0% error rate |
| `load-test-read.js` | Read-heavy load (100 VU, 60s) | P50 < 100ms, P95 < 500ms |
| `load-test-write.js` | Write-heavy load (100 VU, 60s) | P50 < 200ms, P95 < 1000ms |
| `stress-test.js` | Find breaking point (100→400 VU) | < 1% error rate |

## Running Tests

```bash
# Smoke test (1 VU, 10s)
k6 run tests/k6/smoke-test.js

# Load test (100 VU, 60s)
k6 run tests/k6/load-test-read.js

# Stress test (100→400 VU)
k6 run tests/k6/stress-test.js

# Custom target URL
k6 run --env BASE_URL=https://staging.example.com tests/k6/load-test-read.js
```

## Performance Targets (NFR)

| Metric | Target | Critical |
|--------|--------|----------|
| P50 latency | < 100ms | < 200ms |
| P95 latency | < 500ms | < 1000ms |
| P99 latency | < 1000ms | < 2000ms |
| Error rate (5xx) | 0% | < 0.1% |
| Throughput | > 100 req/s | > 50 req/s |
| Concurrent users | 100 | 50 |

## CI Integration

```bash
# In .github/workflows/perf.yml or similar
- name: k6 smoke test
  run: |
    docker run --rm -v $(pwd):/workdir -w /workdir \
      grafana/k6 run tests/k6/smoke-test.js

- name: k6 load test
  run: |
    docker run --rm -v $(pwd):/workdir -w /workdir \
      grafana/k6 run tests/k6/load-test-read.js
```

## Optimization Tips

If tests fail:
1. Check DB connection pool size (`DATABASE_POOL_SIZE` in config)
2. Check Redis cache hit rate (Prometheus: `ontology_cache_hits_total`)
3. Check Neo4j query latency (Prometheus: `neo4j_query_duration_seconds`)
4. Check async worker queue (RabbitMQ management UI)
5. Profile slow endpoints with `py-spy` or `cProfile`
