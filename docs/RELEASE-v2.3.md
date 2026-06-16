# Meatapivot v2.3 — Release & Deployment Guide

> **Delta from v2.2.0.** v2.2.0 deployment instructions still apply;
> this document only covers the v2.3.0 additions, migrations, and
> things operators must do differently.
>
> See [RELEASE.md](./RELEASE.md) for the full production guide (which
> itself is the v2.2.0 baseline).

## What changed at a glance

| Area | v2.2.0 | v2.3.0 |
|------|--------|--------|
| Ontology | Compiler v2.2 + 3-layer | unchanged + OPA policies (read-only) |
| AIP | Agent + Guardrails + Prompt | + LLM cost dashboard + OPA at action exec |
| Workshop | (none) | MVP: Table / Chart / Action nodes + persistence |
| Search | `/ontology/search` | + `/search/suggest`, top-bar `GlobalSearch` |
| Dashboard | Mock charts | Real data + 30 s refresh |
| WebSocket | (none) | First WS surface: `/ws/interfaces/{tenant_id}` |

## New / changed infrastructure

### Database — DDL

`docker/postgres/init.sql` now includes two new tables. Fresh
deployments pick them up automatically; existing deployments running
the same image will also see them because the script uses
`CREATE TABLE IF NOT EXISTS`.

```sql
-- S3-3
CREATE TABLE IF NOT EXISTS workshop_apps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    graph JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_workshop_apps_tenant ON workshop_apps(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workshop_apps_status ON workshop_apps(tenant_id, status);

-- S4-1
CREATE TABLE IF NOT EXISTS llm_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    monthly_budget_cents INTEGER NOT NULL DEFAULT 10000,
    alert_threshold_percent INTEGER NOT NULL DEFAULT 80,
    model_overrides TEXT,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_budgets_tenant ON llm_budgets(tenant_id);
```

For an **existing** deployment where `Base.metadata.create_all()` has
already run, either:

1. Re-run the init script via `psql -f docker/postgres/init.sql`, or
2. Apply the DDL manually to your production database.

`create_all` is only additive — never drops columns.

### nginx — WebSocket route

`docker/nginx/nginx.conf` now exposes a WebSocket location. v2.2.0
configurations need the following block added inside `server { ... }`:

```nginx
location /ws/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400s;
}
```

Without this block, `WS /ws/interfaces/{tenant_id}` will be served as
plain HTTP and immediately 426 / fail.

### Environment — new optional vars

| Var | Default | Effect |
|-----|---------|--------|
| `LLM_PRICING_OVERRIDES` | `""` | JSON `{"gpt-4o": 1234, ...}` patching the pricing catalog at import time. Useful for self-hosted models with non-default rates. |
| `RABBITMQ_URL` / `REDIS_URL` | localhost defaults | unchanged, but the WebSocket layer now *requires* Redis for the cross-worker publish path. If Redis is unreachable, the WS endpoint silently falls back to 5-second polling. |

### Frontend dev proxy

`frontend/vite.config.ts` now also proxies `/ws` to the FastAPI server.
The default config already includes the entry; if you maintain a custom
Vite config, mirror the new block:

```ts
'/ws': {
  target: 'ws://localhost:8000',
  ws: true,
  changeOrigin: true,
}
```

## Operational impact

- **No new external services**. v2.3.0 still uses the same Redis /
  RabbitMQ / Neo4j / etc. that v2.2.0 ran on. The WebSocket layer
  rides on the existing Redis and the new Celery task uses the
  existing RabbitMQ broker.
- **The OPA client runs in-process**. No OPA server to deploy. The
  policy bundle lives in source (`app/services/opa_client.py`); a
  policy upgrade is a code deploy.
- **k6 load tests require a k6 binary** in CI. The scripts in
  `tests/k6/` are static JS and require no compile step. Install
  instructions for the perf workflow: see
  `.github/workflows/perf.yml` (already wired in v2.2.0).

## Rollout

1. Apply DDL (above) to PostgreSQL.
2. Update the nginx config and reload.
3. Pull the v2.3.0 image, restart the API and worker containers.
4. Verify the WebSocket: `wscat -c ws://your-host/ws/interfaces/<tenant>`.
5. Verify the new routes:
   - `curl http://your-host/api/v1/ontology/actions/policies` → 3 rules
   - `curl http://your-host/api/v1/ontology/search/suggest?q=emp` → suggestions list
   - `curl http://your-host/api/v1/aip/llm-cost?days=7` → JSON report
6. Smoke the dashboard / workshop pages from the UI.

## Rollback

The v2.3.0 release is **backward compatible** at the API level — all
new routes are additive. The only data change is two new empty
tables, which the v2.2.0 backend simply ignores. To roll back:

1. Re-deploy the v2.2.0 image.
2. Optionally drop the new tables:
   ```sql
   DROP TABLE IF EXISTS workshop_apps;
   DROP TABLE IF EXISTS llm_budgets;
   ```
3. Revert the nginx config (remove the `/ws/` block).

UI links for `/workshop`, `/aip/cost`, and the top-bar `GlobalSearch`
will be absent in the rolled-back frontend — they will 404 if anyone
clicks them, but the rest of the application is unaffected.

## Known limitations

- **OPA in-process only** — policies must be deployed as code. A
  real OPA HTTP service is a future enhancement.
- **Workshop MVP** — only Table / Chart / Action node types. Filter
  and LinkNav are tracked in v2.3.1.
- **LLM cost export** — capped at 10 000 rows per CSV. For larger
  exports, query `aip_llm_calls` directly.
- **WebSocket is single-process scoped for in-process broadcasts**;
  Redis pub/sub is the cross-process path. If you scale the API
  beyond one replica, the WS endpoint will only receive events
  emitted by its own process *unless* the Redis pub/sub is
  reachable, in which case fan-out works.
