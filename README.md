# Meatapivot

> **Open-source enterprise knowledge & decision intelligence platform.**
> An open-source alternative to Palantir for building knowledge graphs, managing documents and orchestrating decision flows.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.2-61DAFB.svg)](https://react.dev)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.15-008CC1.svg)](https://neo4j.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)

---

## 🚀 Features

| Module | Capabilities |
|--------|-------------|
| **Knowledge Graph** | Entity & relationship CRUD, Cypher queries, graph exploration, full-text search |
| **Document Management** | File upload/download/batch processing, MinIO object storage, metadata management |
| **Decision Flow** | Visual workflow orchestration (query / transform / condition / notification / API call), async execution |
| **Multi-tenant SaaS** | Row-level tenant isolation across PostgreSQL, Neo4j and MinIO |
| **Analytics** | Dashboards, statistical overview and data visualization |
| **Observability** | Prometheus + Grafana + Loki + Tempo + OpenTelemetry tracing |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React 18 + Vite)            │
│  React Router · TanStack Query · Zustand · TailwindCSS       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / CORS
┌──────────────────────────▼──────────────────────────────────┐
│                        Backend (FastAPI + Python 3.11)       │
│  JWT Auth · Pydantic v2 · Async Lifespan · Rate Limiting     │
└──────────────────────────┬──────────────────────────────────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ PostgreSQL │  │   Neo4j    │  │   MinIO    │
    │   (Rel)    │  │   (Graph)  │  │  (Object)  │
    └────────────┘  └────────────┘  └────────────┘
           │               │               │
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  RabbitMQ  │  │   Redis    │  │  Keycloak  │
    │  (Queue)   │  │  (Cache)   │  │   (IAM)    │
    └────────────┘  └────────────┘  └────────────┘
```

---

## ⚡ Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- (Optional) [Node.js 20+](https://nodejs.org/) for local frontend dev
- (Optional) [Python 3.11+](https://www.python.org/downloads/) for local backend dev

### One-line Start (Docker Compose)

```bash
git clone https://github.com/FinnZhang-AI/-Meatapivot.git
cd meatapivot
bash scripts/dev-start.sh
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

## 🛠️ Tech Stack

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

### Infrastructure
| Service | Version | Purpose |
|---------|---------|---------|
| PostgreSQL | 15-alpine | Relational data |
| Neo4j | 5.15 + APOC | Graph data |
| RabbitMQ | 3.12-management | Message queue |
| MinIO | latest | Object storage |
| Redis | 7-alpine | Cache |
| Keycloak | 23.0 | IAM / SSO |

---

## 📁 Project Structure

```
meatapivot/
├── backend/
│   ├── app/
│   │   ├── core/          # Configuration
│   │   ├── models/        # SQLAlchemy & Pydantic models
│   │   ├── routers/       # API endpoints
│   │   └── services/      # Database & storage clients
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── pages/
│   ├── Dockerfile
│   └── package.json
├── cicd/                  # Prometheus, Grafana, Loki, Tempo configs
├── deployments/           # Helm charts
├── docker/                # DB init scripts
├── docs/                  # Architecture & troubleshooting docs
├── scripts/               # Dev & deployment scripts
└── docker-compose.yml
```

---

## 🔐 Security Notes

- **JWT Secret**: Change `JWT_SECRET_KEY` and `SECRET_KEY` before production deployment.
- **Database Passwords**: Update all default passwords in `.env`.
- **Cypher Injection**: The `/knowledge-graph/query` endpoint executes raw Cypher; restrict to read-only in production.
- **TLS**: Enable HTTPS/TLS for production deployments.

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

---

> **Disclaimer**: Meatapivot is an independent open-source project. It is not affiliated with, endorsed by, or sponsored by Palantir Technologies Inc.
