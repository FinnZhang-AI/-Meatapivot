# Meatapivot

> **Open-source enterprise knowledge & decision intelligence platform.**  
> An open-source alternative to Palantir for building knowledge graphs, managing documents and orchestrating decision flows with Ontology semantics and AI-powered intelligence.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.2-61DAFB.svg)](https://react.dev)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.15-008CC1.svg)](https://neo4j.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![Project Progress](https://img.shields.io/badge/Progress-45%25-orange.svg)](docs/PROGRESS.md)

---

## Features

### Core Modules

| Module | Capabilities | Status |
|--------|-------------|--------|
| **Ontology Semantic Layer** | Object/Link/Interface/Action/Function definitions, Neo4j constraint compilation, Interface validation, semantic search | ~75% |
| **Knowledge Graph** | Entity & relationship CRUD, Cypher queries, graph exploration, sub-graph traversal (up to 5 hops) | ~60% |
| **Document Management** | File upload/download/batch processing, MinIO object storage, metadata management | ~40% |
| **Decision Flow** | Visual workflow orchestration (query / transform / condition / notification / API call), async execution | ~30% |
| **AIP (AI Platform)** | LLM Gateway, RAG Pipeline, Agent Orchestrator, Guardrails security | ~20% |
| **Multi-tenant SaaS** | Row-level tenant isolation across PostgreSQL, Neo4j and MinIO | ~60% |
| **Analytics** | Dashboards, statistical overview and data visualization | ~30% |
| **Observability** | Prometheus + Grafana + Loki + Tempo + OpenTelemetry tracing | ~50% |

### Ontology Layer (Palantir-like Semantic Modeling)

- **Object Types** — Define entity schemas with properties (string/int/float/date/boolean/json), icons, and Interface implementations
- **Link Types** — Define relationships between Object Types with cardinality (1:1, 1:N, N:1, N:M)
- **Interfaces** — Semantic contracts that Object Types must implement, with required properties and links
- **Action Types** — Operations that modify ontology instances, with OPA rules validation and execution logging
- **Functions** — Custom business logic in Python/TypeScript with sandboxed execution
- **Compiler** — Full/incremental compilation to generate Neo4j constraints and GraphQL schemas
- **Semantic Search** — Hybrid search combining vector similarity (Milvus) and graph traversal (Neo4j) with RRF reranking

---

## Architecture

### Production Architecture (with API Gateway & Worker Layer)

```
┌─────────────────────────────────────────────────────────┐
│              Frontend (React 18 + Vite)                  │
│  React Router · TanStack Query · Zustand · TailwindCSS  │
│  React Force Graph · XYFlow · Recharts                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────┐
│            Nginx (API Gateway)                           │
│     Rate Limiting / SSL Termination / Static Files      │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│       FastAPI App (Stateless, Horizontally Scalable)     │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Middleware Layer                     │   │
│  │  JWT Validation / Tenant Injection / OTel Trace  │   │
│  └──────────────────┬───────────────────────────────┘   │
│  ┌──────────────────▼───────────────────────────────┐   │
│  │              Domain Services                      │   │
│  │  Ontology / KG / Documents / Decision Flow / AIP │   │
│  └──────────────────┬───────────────────────────────┘   │
│  ┌──────────────────▼───────────────────────────────┐   │
│  │          Infrastructure Adapters                  │   │
│  │  PostgreSQL / Neo4j / MinIO / Redis / Milvus     │   │
│  └──────────────────────────────────────────────────┘   │
└──────────┬───────────────────────────────┬──────────────┘
           │                               │
    ┌──────▼──────┐              ┌─────────▼────────┐
    │  RabbitMQ   │              │  Redis (Cache)    │
    └──────┬──────┘              └──────────────────┘
    ┌──────▼────────────────────────────────────────┐
    │         Celery Worker (Async Tasks)            │
    │  Doc Parsing / Ontology Compile / Flow Exec   │
    └──────────────────┬────────────────────────────┘
           ┌───────────┼───────────┐
           ▼           ▼           ▼
     ┌──────────┐ ┌──────────┐ ┌──────────┐
     │PostgreSQL│ │  Neo4j   │ │  MinIO   │
     │(Row-level│ │ (Graph)  │ │ (Object) │
     │ tenant)  │ │          │ │          │
     └──────────┘ └──────────┘ └──────────┘
```

### Data Persistence Layer

| Database | Purpose | Isolation Strategy |
|----------|---------|-------------------|
| **PostgreSQL 15** | Ontology definitions, Users, Documents, Decision Flows | Row-level `tenant_id` |
| **Neo4j 5.15** | Ontology instances, Knowledge graph entities | Graph database name per tenant |
| **Milvus v2.3** | Vector embeddings for semantic search | Collection per tenant |
| **MinIO** | Document files, artifacts | Bucket per tenant |
| **Redis 7** | Cache, Rate limiting, Session, LLM quota | Key prefix per tenant |

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- (Optional) [Node.js 20+](https://nodejs.org/) for local frontend dev
- (Optional) [Python 3.11+](https://www.python.org/downloads/) for local backend dev

### Full Stack Deployment (Production-like)

```bash
git clone https://github.com/FinnZhang-AI/-Meatapivot.git
cd meatapivot

# Copy environment template
cp .env.deploy .env
# Edit .env and change all default passwords!

# Start all services (20+ containers)
./scripts/deploy-local.sh up
```

### Lightweight Development Mode

```bash
# Only core services: PostgreSQL + Neo4j + Redis + Backend + Frontend
docker-compose -f docker-compose.light.yml up -d
```

### Service Endpoints

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Web App | http://localhost:3000 | — |
| API Docs | http://localhost:8000/docs | — |
| PostgreSQL | localhost:5432 | knowledge / knowledge123 |
| Neo4j Browser | http://localhost:7474 | neo4j / neo4j123 |
| RabbitMQ Mgmt | http://localhost:15672 | admin / admin123 |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin123 |
| Grafana | http://localhost:3001 | admin / admin |
| Keycloak | http://localhost:8080 | admin / admin123 |
| One API (LLM) | http://localhost:3005 | — |
| Prometheus | http://localhost:9090 | — |

---

## API Reference

### Ontology API (`/api/v1/ontology`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/object-types` | POST | Create Object Type |
| `/object-types` | GET | List Object Types (paginated) |
| `/object-types/{id}` | GET | Get Object Type |
| `/object-types/{id}` | PUT | Update Object Type |
| `/object-types/{id}` | DELETE | Archive Object Type |
| `/object-types/{id}/compile` | POST | Compile Object Type |
| `/object-types/{id}/objects` | POST | Create Ontology Object instance |
| `/objects/{id}/graph` | GET | Get subgraph (up to 5 hops) |
| `/link-types` | POST | Create Link Type |
| `/link-types` | GET | List Link Types |
| `/link-types/{id}/links` | POST | Create relationship instance |
| `/interfaces` | POST | Create Interface |
| `/interfaces` | GET | List Interfaces |
| `/interfaces/{id}/validate` | GET | Validate Interface implementation |
| `/action-types` | POST | Create Action Type |
| `/action-types` | GET | List Action Types |
| `/actions/{id}/execute` | POST | Execute Action |
| `/functions` | POST | Register Function |
| `/functions` | GET | List Functions |
| `/functions/{id}/test` | POST | Test Function in sandbox |
| `/search` | POST | Semantic search (hybrid) |
| `/compile` | POST | Full Ontology compile |

### Knowledge Graph API (`/api/v1/knowledge-graph`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/entities` | POST | Create Entity |
| `/entities/{id}` | GET/PUT/DELETE | Get/Update/Delete Entity |
| `/relationships` | POST | Create Relationship |
| `/query` | POST | Execute read-only Cypher |
| `/search` | POST | Search entities |
| `/explore/{id}` | GET | Explore connections |

### AIP API (`/api/v1/aip`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Chat with LLM (via One API) |
| `/chat/stream` | POST | Chat with SSE streaming |
| `/rag/query` | POST | Ontology-aware RAG query |
| `/agents/{id}/run` | POST | Run Agent workflow |
| `/agents/{id}/status` | GET | Query Agent status |

---

## Tech Stack

### Backend

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11 | Runtime |
| FastAPI | 0.109.2 | Web framework |
| SQLAlchemy | 2.0.25 | Async ORM |
| Pydantic | 2.5.3 | Data validation |
| Neo4j Driver | 5.16.0 | Graph database |
| aio-pika | 9.4.0 | RabbitMQ client |
| MinIO SDK | 7.2.0 | Object storage |
| Python-JOSE | 3.3.0 | JWT handling |
| pymilvus | 2.3.6 | Vector database |
| OpenTelemetry | 1.22.0 | Distributed tracing |

### Frontend

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.2.0 | UI framework |
| TypeScript | 5.3.3 | Type safety |
| Vite | 5.0.12 | Build tool |
| TanStack Query | 5.17.9 | Server state |
| Zustand | 4.4.7 | Client state |
| TailwindCSS | 3.4.1 | Styling |
| XYFlow | 12.0.0 | Workflow editor |
| React Force Graph | 1.23.20 | Graph visualization |

### Infrastructure

| Service | Version | Purpose |
|---------|---------|---------|
| PostgreSQL | 15-alpine | Relational data |
| Neo4j | 5.15 + APOC | Graph data |
| RabbitMQ | 3.12-management | Message queue |
| MinIO | RELEASE.2023-03-20 | Object storage |
| Redis | 7-alpine | Cache & rate limiting |
| Keycloak | 23.0 | IAM / SSO |
| Milvus | v2.3.6 | Vector database |
| One API | latest | LLM gateway |
| Prometheus | v2.49.1 | Metrics |
| Grafana | 10.2.3 | Dashboards |
| Loki | 2.9.3 | Log aggregation |
| Tempo | 2.3.1 | Distributed traces |

---

## Project Structure

```
meatapivot/
├── backend/
│   ├── app/
│   │   ├── core/                  # Configuration
│   │   │   └── config.py          # Pydantic settings
│   │   ├── models/
│   │   │   ├── database_models.py # User, Document, DecisionFlow, etc.
│   │   │   ├── ontology_models.py # Ontology ORM (17 tables)
│   │   │   ├── ontology_schemas.py# Pydantic API schemas
│   │   │   ├── aip_schemas.py     # AIP schemas
│   │   │   └── schemas.py         # Common schemas
│   │   ├── routers/
│   │   │   ├── auth.py            # JWT authentication
│   │   │   ├── documents.py       # Document management
│   │   │   ├── decision_flow.py   # Decision flows
│   │   │   ├── knowledge_graph.py # KG operations
│   │   │   ├── aip.py             # AIP endpoints
│   │   │   ├── ontology.py        # Ontology main router
│   │   │   └── ontology/
│   │   │       ├── object_types.py# Object/Link CRUD + subgraph
│   │   │       ├── link_types.py  # Link Type CRUD
│   │   │       ├── interfaces.py  # Interface CRUD + validation
│   │   │       └── actions.py     # Action/Function CRUD + execution
│   │   ├── services/
│   │   │   ├── database.py        # SQLAlchemy async engine
│   │   │   ├── neo4j_client.py    # Neo4j connection
│   │   │   ├── redis_client.py    # Redis cache
│   │   │   ├── message_queue.py   # RabbitMQ
│   │   │   ├── minio_client.py    # MinIO storage
│   │   │   ├── milvus_client.py   # Milvus vector DB
│   │   │   ├── llm_gateway.py     # One API integration
│   │   │   ├── ontology_compiler.py   # Ontology compiler
│   │   │   ├── semantic_search.py     # Hybrid search
│   │   │   ├── action_executor.py     # Action execution engine
│   │   │   └── guardrails_service.py  # AI security
│   │   └── main.py                # FastAPI app
│   ├── tests/
│   │   ├── test_ontology_core.py
│   │   ├── test_ontology_crud.py
│   │   └── test_ontology_integration.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ontology/          # PropertyTable, RelatedObjects, etc.
│   │   │   ├── aip/               # ChatMessageBubble, ModelSelector
│   │   │   └── Layout.tsx         # Main layout
│   │   ├── hooks/                 # useOntology, useAIP, useAuth
│   │   ├── pages/
│   │   │   ├── ontology/          # 7 ontology management pages
│   │   │   ├── objects/           # Object View detail page
│   │   │   ├── aip/               # Chat, RAGSearch
│   │   │   └── ...                # Dashboard, KG, Documents, etc.
│   │   ├── stores/                # Zustand stores
│   │   └── types/                 # TypeScript types
│   ├── Dockerfile
│   ├── Dockerfile.prod            # Production Nginx build
│   └── package.json
├── cicd/                          # Observability configs
│   ├── prometheus/
│   ├── grafana/
│   ├── loki/
│   ├── otel-collector/
│   └── tempo-config.yml
├── deployments/
│   └── helm/                      # Kubernetes Helm charts
├── docker/
│   └── postgres/
│       └── init.sql               # Database initialization
├── docs/
│   ├── PRD-v2.0.md               # Product requirements
│   ├── TASKS.md                  # Development tasks
│   ├── API-SPEC.md               # API specification
│   ├── FRONTEND-DESIGN.md        # Frontend design
│   ├── PROGRESS.md               # Progress tracking
│   └── ACCEPTANCE.md             # Acceptance criteria
├── scripts/
│   ├── deploy-local.sh           # Local deployment script
│   └── ...
├── .github/workflows/
│   └── ci-cd.yml                 # CI/CD pipeline
├── docker-compose.yml            # Full stack (20+ services)
├── docker-compose.deploy.yml     # Production local deployment
├── docker-compose.light.yml      # Lightweight dev (5 services)
├── .env.deploy                   # Deployment env template
├── .env.example                  # Example env vars
├── AGENTS.md                     # AI coding assistant guide
└── SECURITY.md                   # Security policy
```

---

## Ontology Data Model

### Core Tables (PostgreSQL)

| Table | Purpose |
|-------|---------|
| `ontology_object_types` | Object Type definitions (entity schemas) |
| `ontology_link_types` | Link Type definitions (relationships) |
| `ontology_interfaces` | Interface definitions (semantic contracts) |
| `ontology_action_types` | Action Type definitions (operations) |
| `ontology_functions` | Function definitions (custom logic) |
| `ontology_value_types` | Value Type definitions |
| `ontology_objects` | Object instances (writeback) |
| `ontology_links` | Link instances (writeback) |
| `ontology_compile_logs` | Compilation history |
| `action_execution_logs` | Action execution audit trail |
| `function_versions` | Function version history |

### Instance Storage (Neo4j)

- Object Type → Neo4j Label (e.g., `Employee`, `Department`)
- Link Type → Neo4j Edge Type (e.g., `BELONGS_TO`, `MANAGES`)
- Properties stored as node/edge attributes
- Constraints generated by Ontology Compiler

---

## Security

### Pre-deployment Checklist

| Check | Status |
|-------|--------|
| Change `JWT_SECRET_KEY` (≥ 32 chars) | Required |
| Change all database default passwords | Required |
| Verify `.env` is NOT committed to Git | Required |
| Run `pip audit` — no Critical vulnerabilities | Required |
| Run `npm audit` — no Critical vulnerabilities | Required |
| Verify Cypher query endpoint is read-only | Required |
| Function sandbox enabled (no raw `exec()`) | Required |

### Security Architecture

- **JWT Secret**: Change `JWT_SECRET_KEY` before production deployment
- **Cypher Injection**: Read-only Cypher queries enforced via whitelist validation
- **Function Sandbox**: Custom functions execute with timeout (30s) and memory limits (256MB)
- **Tenant Isolation**: All queries include `tenant_id` filtering via middleware injection
- **PII Protection**: Guardrails service for input/output validation and masking

---

## Progress

| Module | Completion | Details |
|--------|-----------|---------|
| Ontology Backend | ~75% | CRUD APIs, Compiler, Action Executor functional |
| Frontend | ~63% | Ontology management pages, Chat UI, Object View |
| Infrastructure | ~50% | Docker Compose, CI/CD, Observability stack |
| AIP (AI Platform) | ~20% | LLM Gateway working, Agent/Guardrails pending |
| Foundry Data Layer | 0% | SeaTunnel, CDC, Debezium not started |

See [docs/PROGRESS.md](docs/PROGRESS.md) for detailed status.  
See [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) for acceptance criteria.

---

## Development

### Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Testing

```bash
# Backend tests
cd backend
pytest --cov=app -v

# Lint
ruff check backend/
black --check backend/
```

### CI/CD

The project uses GitHub Actions for CI/CD:
- **Lint**: Ruff + Black + isort (backend), ESLint + TypeScript (frontend)
- **Test**: pytest with PostgreSQL, Neo4j, Redis service containers
- **Security**: pip-audit + Trivy scanning
- **Build**: Docker images pushed to GHCR
- **Deploy**: Helm charts to Kubernetes (staging/production)

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

All PRs must pass CI checks (lint, test, security scan) before merging.

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

Copyright (c) 2026 ZhangShunguo

---

> **Disclaimer**: Meatapivot is an independent open-source project. It is not affiliated with, endorsed by, or sponsored by Palantir Technologies Inc.
