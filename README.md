# Meatapivot

> **Open-source enterprise knowledge & decision intelligence platform.**
> An open-source alternative to Palantir for building knowledge graphs, managing documents and orchestrating decision flows with Ontology semantics and AI-powered intelligence.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.2-61DAFB.svg)](https://react.dev)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.15-008CC1.svg)](https://neo4j.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)

---

## Features

### Core Modules

| Module | Capabilities |
|--------|-------------|
| **Ontology Semantic Layer** | Object/Link/Interface/Action/Function definitions, Neo4j constraint compilation, Interface validation, semantic search |
| **Knowledge Graph** | Entity & relationship CRUD, Cypher queries, graph exploration, sub-graph traversal (up to 5 hops) |
| **Document Management** | File upload/download/batch processing, MinIO object storage, metadata management |
| **Decision Flow** | Visual workflow orchestration (query / transform / condition / notification / API call), async execution |
| **Multi-tenant SaaS** | Row-level tenant isolation across PostgreSQL, Neo4j and MinIO |
| **Analytics** | Dashboards, statistical overview and data visualization |
| **Observability** | Prometheus + Grafana + Loki + Tempo + OpenTelemetry tracing |

### Ontology Layer (Palantir-like Semantic Modeling)

- **Object Types** — Define entity schemas with properties (string/int/float/date/boolean/json), icons, and Interface implementations
- **Link Types** — Define relationships between Object Types with cardinality (1:1, 1:N, N:1, N:M)
- **Interfaces** — Semantic contracts that Object Types must implement, with required properties and links
- **Action Types** — Operations that modify ontology instances, with OPA rules validation and execution logging
- **Functions** — Custom business logic in Python/TypeScript with sandboxed execution
- **Compiler** — Full/incremental compilation to generate Neo4j constraints and GraphQL schemas
- **Semantic Search** — Hybrid search combining vector similarity and graph traversal with RRF reranking

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React 18 + Vite)                    │
│     React Router · TanStack Query · Zustand · TailwindCSS           │
│     React Force Graph · XYFlow · Recharts                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP / CORS
┌──────────────────────────────▼──────────────────────────────────────┐
│                     Backend (FastAPI + Python 3.11)                  │
│  JWT Auth · Pydantic v2 · Async Lifespan · Rate Limiting            │
│  OpenTelemetry · Prometheus Instrumentation                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                   Ontology Semantic Layer                     │   │
│   │  Object Types · Link Types · Interfaces · Actions · Funcs  │   │
│   │  OntologyCompiler · SemanticSearch · ActionExecutor          │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                    Existing APIs                              │   │
│   │  Knowledge Graph · Documents · Decision Flows                  │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────┬──────────────────────────────────────┘
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌────────────┐      ┌────────────┐      ┌────────────┐
    │ PostgreSQL │      │   Neo4j    │      │   MinIO    │
    │   (SQL)    │      │   (Graph)  │      │  (Object)  │
    └────────────┘      └────────────┘      └────────────┘
           │                   │                   │
    ┌────────────┐      ┌────────────┐      ┌────────────┐
    │  RabbitMQ │      │   Redis    │      │ Keycloak   │
    │  (Queue)   │      │  (Cache)   │      │   (IAM)    │
    └────────────┘      └────────────┘      └────────────┘
```

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- (Optional) [Node.js 20+](https://nodejs.org/) for local frontend dev
- (Optional) [Python 3.11+](https://www.python.org/downloads/) for local backend dev

### One-line Start (Docker Compose)

```bash
git clone https://github.com/FinnZhang-AI/-Meatapivot.git
cd meatapivot
docker-compose up -d
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
| `/entities/{id}` | GET | Get Entity |
| `/entities/{id}` | PUT | Update Entity |
| `/entities/{id}` | DELETE | Delete Entity |
| `/relationships` | POST | Create Relationship |
| `/query` | POST | Execute read-only Cypher |
| `/search` | POST | Search entities |
| `/explore/{id}` | GET | Explore connections |

---

## Tech Stack

### Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11 | Runtime |
| FastAPI | 0.109.2 | Web framework |
| SQLAlchemy | 2.0.25 | Async ORM |
| Neo4j Python Driver | 5.16.0 | Graph database driver |
| Pika | 1.3.2 | RabbitMQ client |
| MinIO SDK | 7.2.0 | Object storage client |
| Python-JOSE | 3.3.0 | JWT handling |
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
| Recharts | 2.10.3 | Charts |
| XYFlow | 12.0.0 | Node editor |
| React Force Graph | 1.23.20 | Knowledge graph visualization |

### Infrastructure
| Service | Version | Purpose |
|---------|---------|---------|
| PostgreSQL | 15-alpine | Relational data |
| Neo4j | 5.15 + APOC | Graph data |
| RabbitMQ | 3.12-management | Message queue |
| MinIO | latest | Object storage |
| Redis | 7-alpine | Cache |
| Keycloak | 23.0 | IAM / SSO |
| Prometheus | v2.49.1 | Metrics |
| Grafana | 10.2.3 | Visualization |

---

## Project Structure

```
meatapivot/
├── backend/
│   ├── app/
│   │   ├── core/              # Configuration (config.py)
│   │   ├── models/
│   │   │   ├── database_models.py   # User, Document, DecisionFlow, etc.
│   │   │   ├── ontology_models.py   # Ontology ORM models (16 tables)
│   │   │   ├── ontology_schemas.py  # Pydantic schemas for API
│   │   │   └── schemas.py           # Common schemas
│   │   ├── routers/
│   │   │   ├── auth.py              # Authentication
│   │   │   ├── documents.py          # Document management
│   │   │   ├── decision_flow.py      # Decision flows
│   │   │   ├── knowledge_graph.py    # KG operations
│   │   │   └── ontology/
│   │   │       ├── object_types.py   # Object/Link CRUD + subgraph
│   │   │       ├── interfaces.py     # Interface CRUD + validation
│   │   │       └── actions.py        # Action/Function CRUD + execution
│   │   └── services/
│   │       ├── database.py          # SQLAlchemy async engine
│   │       ├── neo4j_client.py      # Neo4j connection
│   │       ├── redis_client.py      # Redis cache
│   │       ├── message_queue.py     # RabbitMQ
│   │       ├── minio_client.py      # MinIO storage
│   │       ├── ontology_compiler.py # Ontology compiler
│   │       └── semantic_search.py   # Hybrid search
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── stores/
│   ├── Dockerfile
│   └── package.json
├── cicd/                          # Prometheus, Grafana, Loki, Tempo configs
├── deployments/                   # Helm charts (Kubernetes)
├── docker/
│   └── postgres/
│       └── schema.sql            # Full database schema (v2.0)
├── docs/                         # Architecture docs
│   ├── PRD-v2.0.md              # Product requirements
│   ├── TASKS.md                 # Development tasks
│   ├── API-SPEC.md              # API specification
│   └── FRONTEND-DESIGN.md       # Frontend design
├── scripts/                      # Dev scripts
└── docker-compose.yml           # Full stack orchestration
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
| `ontology_objects` | Object instances (writeback) |
| `ontology_links` | Link instances (writeback) |
| `ontology_compile_logs` | Compilation history |
| `action_execution_logs` | Action execution audit trail |

### Instance Storage (Neo4j)

- Object Type → Neo4j Label (e.g., `Employee`, `Department`)
- Link Type → Neo4j Edge Type (e.g., `BELONGS_TO`, `MANAGES`)
- Properties stored as node/edge attributes
- Constraints generated by Ontology Compiler

---

## Security Notes

- **JWT Secret**: Change `JWT_SECRET_KEY` and `SECRET_KEY` before production deployment.
- **Database Passwords**: Update all default passwords in `.env`.
- **Cypher Injection**: The `/knowledge-graph/query` endpoint executes raw Cypher; restricted to read-only operations.
- **Tenant Isolation**: All queries include `tenant_id` for row-level security.
- **Function Sandbox**: Custom functions execute with timeout (default 30s) and memory limits (default 256MB).

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

---

> **Disclaimer**: Meatapivot is an independent open-source project. It is not affiliated with, endorsed by, or sponsored by Palantir Technologies Inc.