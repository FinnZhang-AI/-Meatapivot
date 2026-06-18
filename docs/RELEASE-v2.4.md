# Meatapivot v2.4 — Release & Deployment Guide

> **Delta from v2.3.1.** v2.3.1 deployment instructions still apply;
> this document only covers the v2.4.0 additions, the new table, and
> things operators must do differently.
>
> See [RELEASE.md](./RELEASE.md) for the full production guide
> (v2.2.0 baseline) and [RELEASE-v2.3.md](./RELEASE-v2.3.md) for the
> v2.3.0 → v2.3.1 delta.

## What changed at a glance

| Area | v2.3.1 | v2.4.0 |
|------|--------|--------|
| Workshop | Config-only (5 node types, no run) | **+ runtime executor + run history** |
| Frontend tests | Vitest absent | **+ 4 test files, 17 tests, npm test in CI** |
| Celery | 2 of 4 tasks were `# TODO` skeletons | **+ process_document + execute_function_action** |
| Routes | 9.4 had Workshop CRUD only | **+ /run, /executions, /executions/{id}** |

## Database — DDL

`docker/postgres/init.sql` gains one new table. Fresh deployments
pick it up automatically; existing deployments either re-run the
script or apply the DDL manually.

```sql
-- V4-1
CREATE TABLE IF NOT EXISTS workshop_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    app_id UUID NOT NULL REFERENCES workshop_apps(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    graph_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    results JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    triggered_by UUID REFERENCES users(id),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_workshop_executions_app ON workshop_executions(app_id);
CREATE INDEX IF NOT EXISTS idx_workshop_executions_tenant ON workshop_executions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workshop_executions_status ON workshop_executions(tenant_id, status);
```

## Python dependencies

`backend/requirements.txt` adds two **optional-at-runtime** parsers:

```
pypdf==4.0.1
python-docx==1.1.0
```

If the libraries are missing at runtime, `process_document` falls
back to UTF-8 decode and records a `parser_warning` on the
Document row. No hard dependency.

## Frontend dependencies

`frontend/package.json` adds the Vitest toolchain (devDependencies):

- `vitest@^1.4.0`
- `jsdom@^24.0.0`
- `@testing-library/react@^14.2.1`
- `@testing-library/jest-dom@^6.4.2`
- `@testing-library/user-event@^14.5.2`

Two new scripts: `npm test` and `npm run test:watch`.

## CI

`.github/workflows/ci.yml` adds a `Run unit tests` step to the
existing `frontend-test` job. The Vitest suite runs in CI on every
push to main / develop and on every PR.

## Operational impact

- **Workshop runtime is synchronous.** A typical app (5-10 nodes,
  one PG query each) finishes in under a second. No new background
  worker is required. V4.1 may add a Celery + SSE path if very large
  graphs surface.
- **No new external services** — the executor uses the same
  PostgreSQL, MinIO, and Neo4j as everything else.
- **The executor is tenant-scoped** — every query filters by
  `request.state.tenant_id` so Workshop apps cannot leak across
  tenants.

## Rollout

1. Apply the new DDL block to PostgreSQL.
2. `pip install -r requirements.txt` to pick up the parser libraries
   (or skip — UTF-8 fallback works).
3. `npm install` in `frontend/` to pick up the Vitest toolchain.
4. Pull the v2.4.0 image, restart the API container.
5. Verify:
   - `curl -X POST http://your-host/api/v1/workshop/apps/{id}/run \
      -H "Authorization: Bearer …" -d '{}'` → 200 with `results`
   - `npm test` exits 0 in the frontend container
   - The `process_document` Celery task logs a successful run when
     you upload a PDF

## Rollback

The v2.4.0 release is **backward compatible** at the API level — the
new routes are additive, and the existing Workshop CRUD + UI
continue to work. To roll back:

1. Re-deploy the v2.3.1 image.
2. Optionally drop the new table:
   ```sql
   DROP TABLE IF EXISTS workshop_executions;
   ```
3. Revert the `npm install` of Vitest if you care about lockfile
   cleanliness; the test files are never executed in production.

The Workshop editor loses the `▶ 运行` button (which is a no-op
without `/run`), and the `frontend-test` CI step will fail without
the Vitest toolchain — neither blocks other app areas.

## Known limitations

- Workshop runtime is **synchronous** — long-running graphs will
  block the request thread. V4.1 candidate.
- The executor's topological sort is correct but unweighted; the
  cycle detector uses standard white/gray/black coloring and rejects
  the whole run on any back-edge.
- The `process_document` parser is a thin wrapper around
  `pypdf` / `python-docx`. Complex PDF layouts (tables, images) will
  not round-trip — `pypdf.extract_text` is a text-only call.
- `compile_ontology` and `execute_decision_flow` Celery tasks are
  intentionally `NotImplementedError` and pushed to v2.4.1; the
  synchronous routes they would back (`/ontology/compile`,
  `/decision-flow/execute`) continue to work.
- Vitest is configured but `coverage` is off; flip
  `coverage.enabled = true` and add a `--coverage` flag to the
  workflow when ready.
