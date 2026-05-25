# Meatapivot 架构审查报告

> **版本**：v1.0  
> **日期**：2026-05-25  
> **来源**：`Meatapivot架构完善与验收标准.md`  
> **目的**：记录架构差异与修复计划，作为开发任务的架构基线

---

## 一、现有架构评估

```
Frontend (React 18 + Vite)
        ↓ HTTP/CORS
Backend (FastAPI + Python 3.11)
  ├── Ontology Layer
  ├── Knowledge Graph API
  ├── Document Management
  └── Decision Flow
        ↓
PostgreSQL | Neo4j | MinIO
RabbitMQ   | Redis  | Keycloak
```

**整体评价**：选型合理，覆盖企业知识图谱平台核心需求，但存在结构性问题需完善。

---

## 二、缺失的架构层次

### 2.1 API Gateway 层

| 项目 | 描述 |
|------|------|
| **现状** | FastAPI 直接暴露给外部，无统一网关 |
| **目标** | Nginx/Kong 作为 API Gateway，负责限流/熔断/SSL 终止/路由分发 |
| **严重度** | P1 |
| **影响** | 生产环境安全风险 |

### 2.2 异步任务层

| 项目 | 描述 |
|------|------|
| **现状** | RabbitMQ 运行但仅用于简单通知，异步用 `BackgroundTasks`（进程内、不持久化） |
| **目标** | Celery Worker 消费 RabbitMQ，处理文档解析/本体编译/决策流执行等异步任务 |
| **严重度** | P0 |
| **影响** | 任务不可恢复、不可扩展 |

### 2.3 AI/向量检索层抽象

| 项目 | 描述 |
|------|------|
| **现状** | `SemanticSearchService` 是具体类，直接调用 `MilvusClient` 和 `neo4j_client` 单例 |
| **目标** | `EmbeddingProvider` / `VectorStore` / `GraphStore` / `RRF Reranker` 可替换接口 |
| **严重度** | P1 |

---

## 三、安全风险

| 风险 | 位置 | 严重度 |
|------|------|--------|
| `.env` 文件可能被提交到 Git | 仓库根目录 | **P0** |
| Cypher 注入防护使用黑名单（仅过滤写操作关键字） | `routers/knowledge_graph.py` | **P0** |
| Function 沙箱使用 `subprocess.run()`，`exec()` 未显式拦截 | `action_executor.py`, `actions.py` | **P0** |
| Auth 完全 Mock，无真实 PostgreSQL 用户存储 | `routers/auth.py` | **P0** |
| Documents 查询返回 Mock 数据 | `routers/documents.py` | P1 |
| Router 层混合业务逻辑 | `routers/ontology/*` | P1 |
| 缺少 Alembic 数据库迁移 | 后端 | P1 |
| MinIO/OneAPI 使用 `latest` 镜像 | `docker-compose.yml` | P2 |

---

## 四、改进后完整架构

```
┌─────────────────────────────────────────┐
│          Frontend (React 18 + Vite)      │
└──────────────────┬──────────────────────┘
                   │ HTTPS
┌──────────────────▼──────────────────────┐
│         Nginx（API Gateway）             │
│    限流 / SSL终止 / 静态文件服务         │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│    FastAPI App（无状态，可水平扩展）      │
│  ┌── TenantMiddleware ──────────────┐   │
│  │  JWT验证 / 租户注入 / OTel追踪   │   │
│  └──────────────┬───────────────────┘   │
│  ┌── Domain Services ───────────────┐   │
│  │  Ontology / KG / Doc / Decision  │   │
│  └──────────────┬───────────────────┘   │
│  ┌── Infrastructure Adapters ───────┐   │
│  │  DB / Neo4j / MinIO / Cache      │   │
│  └──────────────────────────────────┘   │
└──────────┬──────────────────────────────┘
           │                    │
    ┌──────▼──────┐    ┌────────▼────────┐
    │  RabbitMQ   │    │  Redis（缓存）   │
    └──────┬──────┘    └─────────────────┘
    ┌──────▼──────────────────────────────┐
    │      Celery Worker（异步任务）        │
    │  文档解析 / 本体编译 / 决策流执行     │
    └──────────────────────────────────────┘
           │
    ┌──────┴──────┬──────────────┐
    ▼             ▼              ▼
PostgreSQL     Neo4j          MinIO
（行级租户隔离）（图实例）    （对象存储）
```

---

## 五、代码审查问题清单

### P0（安全/功能缺陷—上线前必须修复）

| # | 问题 | 位置 | 修复方案 | 预估 |
|---|------|------|----------|------|
| 1 | `.env` 被提交到 Git | 仓库根目录 | `git rm --cached .env` + 轮换密码 | 0.5d |
| 2 | Cypher 注入防护不足 | `knowledge_graph.py:288-300` | 白名单关键字 + 参数化 | 1d |
| 3 | Function exec() 风险 | `action_executor.py:351-396` | RestrictedPython 替换 | 2d |
| 4 | Auth 完全 Mock | `auth.py:44-83` | 实现 PostgreSQL 用户存储 | 2d |

### P1（架构/可维护性）

| # | 问题 | 位置 | 修复方案 | 预估 |
|---|------|------|----------|------|
| 5 | Router 含业务逻辑 | `routers/ontology/*` | 拆分为 Router/Service/Repository | 5d |
| 6 | 缺少 Alembic 迁移 | 后端 | `alembic init migrations` + CI | 1d |
| 7 | 缺少 Celery Worker | `docker-compose.yml` | 添加 worker 服务 | 3d |
| 8 | Document 查询 Mock | `documents.py:83-109` | 真实 PostgreSQL 查询 | 2d |
| 9 | 多租户无 Middleware | `main.py` | TenantMiddleware 注入 | 1d |
| 10 | Keycloak 未集成 | `auth.py` | python-keycloak OIDC | 3d |

### P2（工程规范）

| # | 问题 | 位置 | 修复方案 | 预估 |
|---|------|------|----------|------|
| 11 | MinIO/OneAPI `latest` | `docker-compose.yml` | 固定版本号 | 0.5d |
| 12 | 前端缺少测试 | `frontend/` | Vitest + Testing Library | 3d |
| 13 | Dashboard Mock 数据 | `Dashboard.tsx` | 接入真实 API | 1d |
| 14 | 缺少 API 版本策略 | `docs/API-SPEC.md` | 补充 v2 升级兼容性承诺 | 0.5d |

---

## 六、优先级行动计划

| 优先级 | 任务 | 预估 | Sprint |
|--------|------|------|--------|
| **P0** | 删除 `.env`，轮换密码 | 0.5d | S1 |
| **P0** | Cypher 白名单注入防护 | 1d | S1 |
| **P0** | RestrictedPython 沙箱 | 2d | S1 |
| **P0** | 实现真实 Auth 存储 | 2d | S2 |
| P1 | Alembic 迁移配置 | 1d | S2 |
| P1 | Celery Worker 服务 | 3d | S2-S3 |
| P1 | Router/Service/Repository 三层分离 | 5d | S3-S4 |
| P1 | TenantMiddleware | 1d | S3 |
| P2 | 固定 Docker 镜像版本 | 0.5d | S4 |
| P2 | 前端测试 | 3d | S5 |
| P2 | 补充 CI 安全扫描 | 1d | S5 |

---

> **维护**：本文档基于代码审查生成，每个 Sprint 结束后更新完成状态。
