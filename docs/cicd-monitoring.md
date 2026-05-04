# CI/CD 与运维监控模块

> **版本：** 1.0.0  
> **日期：** 2026-05-03

---

## 1. 概述

本文档描述知识决策平台的持续集成/持续部署（CI/CD）流水线与可观测性（Observability）体系设计，覆盖代码提交到生产部署的全生命周期，以及系统运行时的指标、日志与链路追踪能力。

---

## 2. CI/CD 流水线架构

### 2.1 工作流总览

```
Push/PR
   │
   ▼
┌──────────────┐
│  Lint Stage  │ ──► Ruff / Black / ESLint / Type Check
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Test Stage  │ ──► pytest + Coverage / Vitest + Coverage
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Security Scan│ ──► pip-audit / Trivy / SARIF Upload
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Build & Push │ ──► Docker Image → GHCR
└──────┬───────┘
       │
       ├─────────── develop branch ──► Staging (Helm)
       │
       └─────────── tag v* ─────────► Production (Helm)
```

### 2.2 GitHub Actions 工作流

文件位置：`.github/workflows/ci-cd.yml`

| Stage | 任务 | 触发条件 |
|-------|------|----------|
| `lint-backend` | Ruff、Black、isort | PR / Push |
| `lint-frontend` | ESLint、TypeScript | PR / Push |
| `test-backend` | pytest + PostgreSQL/Neo4j/Redis Service Containers | PR / Push |
| `test-frontend` | Vitest + Coverage | PR / Push |
| `security-scan` | pip-audit、Trivy SARIF | PR / Push |
| `build-and-push` | Docker Buildx → GHCR | Push (非 PR) |
| `deploy-staging` | Helm upgrade --install | develop branch |
| `deploy-production` | Helm upgrade --install | tag v* |

### 2.3 环境配置

| 环境 | Namespace | 触发方式 | 镜像 Tag |
|------|-----------|----------|----------|
| Staging | `staging` | develop 分支推送 | `github.sha` |
| Production | `production` | Git Tag `v*` | `github.ref_name` |

需要在 GitHub Repository Settings → Secrets 中配置：
- `KUBECONFIG_STAGING` (base64 编码的 kubeconfig)
- `KUBECONFIG_PROD` (base64 编码的 kubeconfig)
- `GITHUB_TOKEN` (默认提供，用于 GHCR 登录)

---

## 3. 自动化部署

### 3.1 Kubernetes 部署

脚本：`scripts/deploy-k8s.sh`

```bash
# Staging 部署
bash scripts/deploy-k8s.sh staging knowledge-platform $(git rev-parse --short HEAD)

# Production 部署
bash scripts/deploy-k8s.sh production knowledge-platform v1.0.0
```

Helm Chart 位置：`deployments/helm/`
- 基础模板已包含 backend/frontend Deployment、Service、Ingress
- 依赖子 Chart：PostgreSQL、Neo4j、RabbitMQ、MinIO、Keycloak

### 3.2 Docker Compose 部署

脚本：`scripts/deploy-compose.sh`

```bash
# 开发环境
bash scripts/deploy-compose.sh dev

# 生产环境（拉取最新镜像）
bash scripts/deploy-compose.sh prod
```

---

## 4. 运维监控体系

### 4.1 可观测性三大支柱

| 支柱 | 技术方案 | 用途 |
|------|----------|------|
| **Metrics** | Prometheus + Grafana | 系统指标、业务指标、告警 |
| **Logs** | Loki + Promtail | 结构化日志聚合与检索 |
| **Traces** | Tempo + OpenTelemetry | 分布式链路追踪 |

### 4.2 监控栈服务

监控服务已集成至 `docker-compose.yml`：

| 服务 | 端口 | 说明 |
|------|------|------|
| Prometheus | 9090 | 指标采集与存储 |
| Grafana | 3001 | 可视化仪表盘 |
| Loki | 3100 | 日志聚合 |
| Promtail | — | 日志采集 Agent |
| Tempo | 3200 | 链路追踪存储 |
| OpenTelemetry Collector | 4317/4318 | OTel 数据接收与转发 |
| postgres-exporter | 9187 | PostgreSQL 指标 |
| redis-exporter | 9121 | Redis 指标 |

### 4.3 后端指标集成

后端通过 `prometheus-fastapi-instrumentator` 自动暴露 `/metrics` 端点：

- `http_requests_total` — HTTP 请求总数（按 method、status 分类）
- `http_request_duration_seconds` — 请求延迟直方图
- `process_resident_memory_bytes` — 进程内存占用
- 数据库连接池指标（通过 SQLAlchemy 事件）

### 4.4 链路追踪

后端集成 OpenTelemetry Python SDK：
- 自动注入 FastAPI、HTTP Client、SQLAlchemy、Redis、Neo4j Instrumentation
- Trace 数据通过 OTLP 推送到 OpenTelemetry Collector
- Collector 将 Trace 转发至 Tempo 存储
- Grafana 中通过 Tempo 数据源查询链路

### 4.5 日志收集

- 所有服务输出 JSON 结构化日志
- Promtail 采集容器 stdout 日志
- 日志标签自动附加：`service_name`、`tenant_id`、`trace_id`
- Loki 中支持按 Trace ID 检索关联日志

---

## 5. 访问地址

| 服务 | 本地地址 | 默认账号 |
|------|----------|----------|
| 前端 | http://localhost:3000 | — |
| 后端 API | http://localhost:8000 | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3001 | admin / admin |
| Tempo | http://localhost:3200 | — |
| RabbitMQ Mgmt | http://localhost:15672 | admin / admin123 |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin123 |

---

## 6. 告警规则（推荐）

在 Prometheus 中配置以下告警规则：

```yaml
groups:
  - name: knowledge-platform
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
      - alert: ServiceDown
        expr: up{job=~"knowledge-platform-.*"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency is above 2 seconds"
```

---

## 7. 演进路线

| 阶段 | 时间 | 任务 |
|------|------|------|
| **短期** | 1-2 周 | 配置 GitHub Secrets、验证 Staging 部署、导入 Grafana Dashboard |
| **中期** | 1 个月 | 接入 Alertmanager、配置钉钉/飞书告警通知、完善 SLO/SLI |
| **长期** | 2-3 个月 | 引入混沌工程（Chaos Mesh）、自动化回滚策略、成本监控 |
