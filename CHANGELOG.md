# Changelog

All notable changes to Meatapivot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
