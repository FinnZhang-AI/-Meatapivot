# Changelog

All notable changes to Meatapivot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.1] - 2026-06-16

### Workshop App Builder — Filter and LinkNav node types

Closes the v2.3.0 deferred items for the Workshop App Builder. The
S3-3 MVP shipped with Table / Chart / Action node types; v2.3.1
finishes the catalogue with the two originally scoped node types.

### Added

- **Filter node** (`type: "filter"`) — consumes the upstream Table
  node's instance list and applies a property + operator + value
  triple. Configurable from the property panel:
  - `field` — which property to test (free text, e.g. `status`)
  - `operator` — one of `==`, `!=`, `>`, `>=`, `<`, `<=`,
    `contains`, `in`
  - `value` — the comparison value (free text)
  - The node card shows a live summary like `status == active`.
- **LinkNav node** (`type: "linknav"`) — consumes a Table node and
  navigates to a related ObjectType via a configured LinkType.
  Configurable from the property panel:
  - `linkTypeName` — the LinkType name (e.g. `BELONGS_TO`)
  - `targetObjectType` — the target ObjectType (e.g. `Department`)
  - The node card shows a live summary like `BELONGS_TO → Department`.
- Both node types are added to the left-side component panel; they
  serialize through the same JSONB `graph` column with no backend
  schema change.
- `test_workshop_v231_filter_and_linknav_nodes_persist` — new
  contract test in `backend/tests/test_sprint4.py` covering
  the new node data shape on the Workshop create / update path.

### Notes

- Both nodes render the configuration as a static summary string
  on the canvas. Runtime evaluation of the filter / navigation
  expression is part of the Workshop executor (tracked in v2.4).

## [2.3.0] - 2026-06-16

## [2.3.0] - 2026-06-16

### v2.3 "AI-Native" Release — AIP Smart Layer + Workshop + Dashboard

This release closes v2.3 of the development plan, focusing on the AI
platform, ontology polish, app builder, and observability. The previous
release (v2.2.0) shipped the core ontology compiler and security hardening;
v2.3.0 layers the production-ready AI stack on top.

### Added — S3-5: Dashboard real-time data

- **`GET /api/v1/aip/llm-calls/aggregate`** — bucketed LLM usage (calls,
  total tokens, estimated cost cents) for any window from 1 to 168 hours
- **`GET /api/v1/ontology/stats`** gains `object_type_distribution` —
  top-8 ObjectTypes by instance count for the dashboard pie chart
- Dashboard now consumes real data: hourly LLM call + token trend line
  chart, object type distribution pie chart, summary cards pulled every
  30 seconds via TanStack Query

### Added — S3-1: Async interface validation

- **`GET /ws/interfaces/{tenant_id}`** — first WebSocket surface in the
  platform. Pushes interface compliance reports to subscribed clients.
- **`validate_all_interfaces` Celery task** — runs the same logic the
  synchronous `/validate` endpoint uses, publishes results to Redis pub/sub
  (`interface_validation:{tenant_id}`) with a 5-minute TTL fallback key.
- Interface create / update enqueue the task; the WebSocket layer replays
  the most recent report on connect and degrades to a 5-second poll loop
  when Redis pub/sub is unavailable.
- Frontend `useInterfaceValidationWS` hook + `ValidationToaster` surface
  the result as a tone-coded toast (green / red / blue) for 6 seconds.
- nginx gains a `/ws/` location with `Upgrade` / `Connection` headers and
  24h read-timeout; Vite dev proxy adds `/ws` so the editor can subscribe
  during local development.

### Added — S3-2: Action OPA integration

- `app/services/opa_client.py` — in-process Rego-subset evaluator (see
  *Implementation note* below). Boolean expressions over an `input`
  document, with safe-AST evaluation and `count()` support.
- 3 baseline rules:
  - `tenant_isolation` — rejects actions whose tenant_id does not match
    the caller's tenant
  - `forbidden_parameters` — blocks `system.drop_database` /
    `system.purge_all`
  - `max_parameters` — caps parameter count at 32
- `ActionExecutor` invokes the client between the in-Python rule engine
  and mode-specific execution. OPA denials return `success=false` with a
  `RuleEvaluation(rule_name="OPA::<rule>", passed=false, reason=...)` so
  the existing call site shape is unchanged.
- **`GET /api/v1/ontology/actions/policies`** — enumerates the loaded
  rules for the admin UI.
- 7 inline unit tests in `backend/tests/test_sprint4.py` cover match,
  cross-tenant denial, forbidden name, parameter cap, empty tenant, rule
  selector, and malformed-bundle fail-open behavior.

**Implementation note**: DEVPLAN-v2.3 referenced `opa-python` as the
embedding library, but no such package exists on PyPI. The embedded
evaluator is the implementation. The `OPAClient.evaluate(input_doc) ->
PolicyDecision` interface is the swap point if/when a real OPA HTTP
service is adopted.

### Added — S3-4: Global search upgrade

- **`GET /api/v1/ontology/search/suggest`** — tenant-scoped prefix matches
  on ObjectType names and Document titles (PG `ILIKE`).
- Frontend `GlobalSearch` component in the top bar replaces the inline
  form. Three modes (keyword / semantic / rag), debounced autocomplete
  (150 ms), per-user localStorage history (cap 8, deduped by
  query + mode, individually removable).
- `SemanticSearch` page gains the RAG mode (calls `/aip/rag/query` and
  renders the answer + cited sources above the ontology result list).
  Non-RAG modes get a classification banner.

### Added — S3-3: Workshop App Builder (MVP)

- `workshop_apps` table — PG JSONB column stores the full React Flow
  graph (`{ nodes, edges, viewport }`).
- **CRUD** at `/api/v1/workshop/apps` — list / create / get / update /
  delete, all tenant-scoped, paginated list endpoint.
- `WorkshopList` page — create / list apps with status badges.
- `WorkshopEditor` — XYFlow canvas with Background / Controls / MiniMap,
  three custom node types (Table / Chart / Action) and a property panel.
  Chart nodes auto-display the upstream Table label when a connection is
  made, demonstrating the data-binding direction. PUT persists the graph.
- New "Workshop" entry in the sidebar; new route `/workshop/editor/:appId`.
- Filter and LinkNav node types are deferred to v2.3.1.
- `docker/postgres/init.sql` — DDL for `workshop_apps` + indexes so fresh
  deployments pick up the table on first boot.

### Added — S4-1: LLM cost dashboard

- `LLM_MODEL_PRICING` catalog in `app/services/llm_pricing.py` — 13
  mainstream models (gpt-4o, claude-3-5-sonnet, qwen-max, deepseek-chat,
  …) priced in USD cents per 1M tokens. Overridable via the
  `LLM_PRICING_OVERRIDES` env var (JSON).
- `llm_budgets` table — per-tenant monthly cap (USD cents) + alert
  threshold percent. `model_overrides` JSON field for per-model rate
  overrides.
- **`GET /api/v1/aip/llm-cost`** — daily / hourly aggregation with
  per-model breakdown and a contiguous trend. Budget state machine
  (`ok` / `warning` / `exceeded` / `no_budget`) classifies the current
  spend against the budget.
- **`GET /api/v1/aip/llm-cost/export`** — CSV download (per-call rows,
  capped at 10 000 rows to keep the response reasonable).
- **`/api/v1/aip/llm-budgets`** — POST upserts, PUT partial-updates,
  GET returns the row (or `null` if none set).
- Frontend `pages/aip/CostDashboard.tsx` — three summary cards, cost
  trend line chart, model distribution pie chart, per-model table, CSV
  export button, and a tone-coded budget banner with inline editor.
  60-second auto-refresh.
- "成本仪表盘" entry in the AIP sidebar.

### Added — S4-2: Sprint 4 E2E tests

- `backend/tests/test_sprint4.py` — 14 tests covering Workshop CRUD
  (router endpoint presence, schema round-trip), LLM cost (pricing
  arithmetic, env override, format helper, budget state classification,
  schema shape, budget CRUD validation), and OPA (cross-tenant block,
  forbidden name, runaway parameters, normal allow, malformed fail-open,
  self-counting guard).

### Added — S4-3: k6 performance scripts

- **`tests/k6/agent-test.js`** — Agent `/run` and `/status` P95 < 2 s
  with 100 concurrent users.
- **`tests/k6/rag-test.js`** — `/aip/rag/query` P95 < 2 s with 100
  concurrent users, 5 rotating queries to avoid hot-spot bias.
- **`tests/k6/workshop-test.js`** — list / get / create all under 1 s
  P95 with 100 concurrent users.
- `config.js` helpers (`authGet` / `authPost` / `authPut` / `authDelete`)
  now accept a 4th `options` argument so callers can attach k6 tags for
  per-endpoint thresholds.

### Changed

- `Layout.tsx` — sidebar gained "Workshop" (S3-3) and "成本仪表盘" (S4-1)
  entries; the top-bar search form was replaced with the new
  `GlobalSearch` component.
- `App.tsx` — `/workshop`, `/workshop/editor/:appId`, `/aip/cost` routes
  added.
- `vite.config.ts` — dev proxy now routes `/ws` to the FastAPI server
  with `ws: true` so the interface validation WebSocket works during
  local development.

### Fixed

- `Layout.tsx` — unused `searchQuery` / `setSearchQuery` / `navigate`
  state in the shell component removed after the search form was
  replaced; tsc now reports zero unused-variable warnings.

### Out of scope (deferred)

- Workshop Filter and LinkNav node types — v2.3.1.
- Real OPA HTTP service — embed stays; swap is a single-file change.
- Per-direction (input vs. output) token pricing — `AIPLLMCall` does
  not record them separately yet.

### Verification

- `npx tsc --noEmit` — clean
- Python `ast.parse` on every modified / new backend file — clean
- Inline unit tests:
  - `llm_pricing.py` — 14 arithmetic + format cases pass
  - `opa_client.py` — 5 rule-classification cases pass
  - `llm_cost_service.py::budget_state` — 10 boundary cases pass
- `backend/tests/test_sprint4.py` — 14 tests; 7 are dependency-bound
  (pydantic / sqlalchemy / fastapi) and run in CI; 7 are pure-stdlib
  and verified above.

## [2.2.0] - 2026-06-11

## [2.2.0] - 2026-06-11

### Sprint 1-6 Complete Release

This release represents the completion of all 6 sprints in the v2.2 development plan,
delivering a production-ready enterprise knowledge management platform with security,
infrastructure, ontology compiler v2.2, three-layer architecture, full API set, and
release documentation.

### Added — Sprint 6: Performance + Release

- **S6-1: k6 Performance Testing** — 4 test scripts (`smoke`, `load-read`, `load-write`, `stress`)
  validating P50 < 100ms, P95 < 500ms at 100 concurrent users with 0 5xx errors
- **S6-2: Frontend Vitest Tests** — Component tests for PropertyTable, RelatedObjects,
  ActionDialog, Chat (test suite)
- **S6-3: CI/CD Security Scanning** — GitHub Actions workflows with bandit, semgrep,
  Trivy, npm audit, pip-audit; weekly scheduled scans
- **S6-4: Release Documentation** — `CHANGELOG.md`, `version.py`, `docs/RELEASE.md`
- **CI workflow** (`.github/workflows/ci.yml`) — Backend tests, frontend build,
  Docker security (Trivy), SAST (Semgrep)
- **Performance workflow** (`.github/workflows/perf.yml`) — Scheduled k6 performance tests
- **Security workflow** (`.github/workflows/security.yml`) — Weekly security scans

### Added — Sprint 5: Architecture + API

- **S5-1: New API Endpoints** — `PATCH /object-types/{id}` (incremental update),
  `GET /compile/logs` (paginated), `POST /compile/rollback`,
  `POST /compile/validate`
- **S5-2: Prometheus Custom Metrics** — 5 histograms (compile_full/incremental,
  validation, dag_detect, function_exec) + 2 counters + 3 gauges
- **S5-3: Nginx API Gateway** — Rate limiting (api/auth zones), SSL termination,
  reverse proxy, routing for backend/frontend/metrics
- **S5-4: Keycloak OIDC Integration** — `python-keycloak` client, OIDC router
  (login/callback/userinfo/logout/config) with graceful fallback to JWT
- **S5-5: Dashboard Real API** — Backend `/stats` endpoint exposing
  ObjectType/LinkType/Interface/ActionType/Function counts + recent actions

### Added — Sprint 4: Three-Layer Architecture Separation

- **S4-1: ObjectType Module Separation** — 7 new repository methods
  (`object_type_name_exists`, `get_object`, `object_key_exists`, `create_object`,
  `list_objects_by_type`, `get_object_type_names`, `update_object`); service layer
  wraps all CRUD operations
- **S4-2: LinkType + Interface Module Separation** — 4 new repository methods
  (`get_link`, `delete_link`, `list_object_links`, `get_link_type_names`); service
  layer for all link instance operations
- **S4-3: Action + Function Module Separation** — Service layer fully integrated
  for ActionType/Function CRUD and execution
- **S4-4: TenantMiddleware** — JWT-based tenant isolation with `X-Tenant-ID` header
  fallback; registered in FastAPI middleware chain

### Added — Sprint 3: Ontology Compiler v2.2

- **S3-1: DAG Dependency Graph** — `OntologyDAG` with Kahn topological sort,
  DFS cycle detection, BFS impact set
- **S3-2: Compiler 5-Module Split** — `compiler/` package: `compiler.py` (pipeline
  orchestrator), `neo4j_emitter.py` (graph constraints), `schema_emitter.py`
  (PostgreSQL JSON schema), `incremental.py`, `__init__.py`
- **S3-3: Dual-Stage Validator** — `StaticValidator` (compile-time schema checks)
  + `RuntimeValidator` (Pydantic dynamic models for runtime)
- **S3-4: SchemaRegistry Cache** — Redis-backed cache for compiled schemas with
  local fallback; batch invalidation support
- **S3-5: Versioning + Rollback** — `versioning.py` with semver utilities
  (`VersionInfo`, `compute_next_version`, `build_diff_snapshot`); semver-based
  version bumping on compile; rollback endpoint
- **S3-6: Transaction Rollback** — Pipeline halt triggers Neo4j constraint
  rollback via `emitter.drop_constraints()`; PostgreSQL data integrity preserved
- **S3-7: 6-Stage Compilation Pipeline** — Load → DAG → Validate → Neo4j →
  Schema → Commit; pre/post-compile snapshots, diff_snapshot generation,
  version computation, and `COMPILE_ROLLED_BACK` error code

### Added — Sprint 2: Infrastructure + Data Model

- **S2-1: Real Authentication** — bcrypt password hashing, PostgreSQL user
  storage, JWT issuance/validation
- **S2-2: Document Query Real** — Real PostgreSQL queries + MinIO storage
  for document upload/download/search
- **S2-3: Alembic Migrations** — Baseline migration `000000000001_initial_schema.py`
  with full schema sync
- **S2-4: Compile Log Fields** — `version`, `parent_version`, `diff_snapshot`,
  `neo4j_stmts`, `rolled_back_at` columns
- **S2-5: Current Version Table** — `OntologyCurrentVersion` model for tracking
  active ontology version per tenant
- **S2-6: Celery Worker** — Async task processing service in docker-compose

### Added — Sprint 1: Security Fixes

- **S1-1: Cypher Whitelist** — `knowledge_graph.py` enforces
  `MATCH/WITH/RETURN/CALL/UNWIND` start tokens; rejects
  `CREATE/SET/DELETE/MERGE/DROP`; parameterized queries
- **S1-2: RestrictedPython Sandbox** — `sandbox_restricted.py` with
  ALLOWED_BUILTINS, FORBIDDEN_NAMES, asyncio timeout; `compile_restricted` AST check
- **S1-3: Environment File Hygiene** — `.env` removed from git tracking;
  `.gitignore` updated with `.env` / `.env.*.local` rules
- **S1-4: Docker Image Pinning** — All `latest` tags replaced with pinned
  versions (minio `RELEASE.2024-01-16T16-07-38Z`, one-api `v0.6.7`)

### Changed

- Router layer: All direct `select()` / `session.execute()` calls removed for
  ObjectType, Object instance, LinkType, Interface, OntologyLink, ActionType,
  Function modules; calls routed through `OntologyService`
- `ontology.py` router now uses `compile_ontology()` and `compile_object_type()`
  from new `CompilationPipeline` instead of legacy `OntologyCompiler`
- `compiler.run_full()` fixed: removed duplicate commit invocation; added
  diff_snapshot capture and version bumping
- Default password defaults strengthened in `.env` template

### Fixed

- Compiler pipeline no longer double-invokes commit stage
- Compile failure now correctly rolls back Neo4j constraints and marks compile
  log as failed (was leaving partial state)
- TenantMiddleware correctly reads `tenant_id` from JWT payload with
  `X-Tenant-ID` header fallback

### Security

- P0-SEC-01: Cypher injection blocked via whitelist validation
- P0-SEC-02: Function execution sandboxed via RestrictedPython
- P0-SEC-03: Passwords stored with bcrypt (cost factor 12)
- P0-SEC-04: Document queries use real database lookups (no mock data)

### P0 Closure (14/14)

All 14 P0 items closed:
- P0-SEC-01, 02, 03, 04: Security
- P0-ARCH-01, 02, 03: Architecture
- P0-ONT-01, 02, 03, 04, 05, 06, 07: Ontology compiler

## [2.1.0] - 2026-05-09

### Added

- Initial Ontology v2.1 design (DAG, dual-stage validator, SchemaRegistry)
- Knowledge graph with entity/relationship storage
- Basic authentication with JWT

## [2.0.0] - 2026-04-15

### Added

- Initial multi-tenant SaaS architecture
- PostgreSQL + Neo4j + Redis + MinIO + RabbitMQ + Keycloak stack
- FastAPI backend with async support
- React + TypeScript + Vite frontend

## [1.0.0] - 2026-03-01

### Added

- Initial MVP release
- Basic document management
- Simple entity storage
