# Meatapivot 项目需求文档 v2.2

> **版本**：2.2  
> **日期**：2026-05-25  
> **状态**：需求评审中  
> **变更**：基于 GAP-ANALYSIS.md 代码审查结果，重组需求优先级

---

## v2.1 → v2.2 变更摘要

| 变更类型 | 内容 | 来源 |
|----------|------|------|
| **新增文档** | `GAP-ANALYSIS.md` — 30 项差异全景分析 | 代码审查 |
| **需求重组** | 基于差距分析重排优先级，P0 从 8 项增至 14 项 | `GAP-ANALYSIS.md` |
| **新增 P0** | DAG 依赖图、双阶段验证器、编译日志表补充、current_version 表、回滚端点、SchemaRegistry | `ONTOLOGY-DESIGN-v1.0.md` |
| **模块状态** | ONT 模块完成度下调：75% → 50%（编译器/验证器/版本管理核心功能缺失） | `GAP-ANALYSIS.md` |
| **里程碑** | M0 拆分为 M0a（安全修复）和 M0b（Ontology 数据模型修复） | — |
| **Sprint 调整** | S1-S2 扩展以覆盖 14 个 P0 项 | — |

---

## 1. 项目当前状态

### 1.1 核心数据

| 指标 | 数值 |
|------|------|
| 代码审查发现的差距总数 | **30 项** |
| P0（阻塞上线） | **14 项** |
| P1（本迭代修复） | **13 项** |
| P2（下迭代修复） | **3 项** |

### 1.2 模块完成度（v2.2 修正）

| 模块 | v2.1 完成度 | v2.2 修正 | 修正原因 |
|------|-----------|----------|----------|
| FIX（架构修复） | 0%→100%（目标） | 0% | 新增 6 项 P0 |
| ONT（Ontology） | 75% | **50%** | 编译器/验证器/版本管理核心功能缺失 |
| AIP（AI 平台） | 20% | 20% | 无变化 |
| APP-F（前端） | 63% | 63% | 无变化 |
| FDR（数据层） | 0% | 0% | 延后 v3.0 |
| INF（基础设施） | 50% | **40%** | Alembic/Celery Worker 缺失 |

---

## 2. P0 需求清单（14 项 — 阻塞上线）

### 2.1 安全修复（4 项）

| 编号 | 需求 | 位置 | 验收标准 |
|------|------|------|----------|
| **P0-SEC-01** | Cypher 白名单注入防护 | `knowledge_graph.py:288` | `CREATE/DELETE/MERGE/SET/REMOVE` + 子查询注入被拒绝 |
| **P0-SEC-02** | RestrictedPython 沙箱 | `action_executor.py:351` | `os.system/__import__/subprocess` 被拦截，`exec()` 零直接调用 |
| **P0-SEC-03** | 真实 Auth 存储 | `auth.py:44-83` | 注册写入 PostgreSQL + bcrypt，过期 token → 401 |
| **P0-SEC-04** | Document 查询真实化 | `documents.py:83-238` | `get/search/download` 查真实 PostgreSQL + MinIO |

### 2.2 架构修复（3 项）

| 编号 | 需求 | 位置 | 验收标准 |
|------|------|------|------|
| **P0-ARCH-01** | Alembic 数据库迁移 | `backend/` | `alembic init && revision --autogenerate && upgrade head` 成功 |
| **P0-ARCH-02** | Celery Worker 异步任务服务 | `docker-compose.yml` | Worker 消费 RabbitMQ，任务状态可查询，失败重试 |
| **P0-ARCH-03** | Router/Service/Repository 三层分离 | `routers/ontology/` | Router 无 SQLAlchemy 查询，Service 可独立测试 |

### 2.3 Ontology 编译器修复（7 项）

| 编号 | 需求 | 位置 | 验收标准 |
|------|------|------|------|
| **P0-ONT-01** | DAG 依赖图（拓扑排序 + 循环检测） | 新增 `compiler/dag.py` | A→B→A 编译返回循环路径 |
| **P0-ONT-02** | 双阶段验证器（static + runtime） | 新增 `validation/static_validator.py` + `runtime_validator.py` | Interface 缺失属性返回 detail |
| **P0-ONT-03** | 编译日志表补充版本字段 | `ontology_models.py` | +`version`, `parent_version`, `diff_snapshot`, `neo4j_stmts` |
| **P0-ONT-04** | `ontology_current_version` 表 | `ontology_models.py` | 每租户一行，记录当前活跃版本 |
| **P0-ONT-05** | 回滚端点 `POST /compile/rollback` | `routers/ontology/` | 回滚后 Neo4j 约束恢复 |
| **P0-ONT-06** | SchemaRegistry 缓存 | 新增 `validation/runtime_validator.py` | Pydantic 动态模型缓存，命中率 > 95% |
| **P0-ONT-07** | 编译失败事务回滚 | `compiler/compiler.py` | PostgreSQL 数据不被修改 |

---

## 3. P1 需求清单（13 项 — 本迭代）

| 编号 | 需求 | 验收标准 |
|------|------|----------|
| P1-01 | 编译器五模块拆分（neo4j_emitter/schema_emitter/incremental/compiler） | 代码在 `services/compiler/` 目录 |
| P1-02 | 增量编译 BFS 影响集 | affected_count 正确 |
| P1-03 | 6 阶段编译流水线编排 | 各阶段失败正确阻断 |
| P1-04 | PATCH /object-types/{id} | 增量更新 |
| P1-05 | GET /compile/logs | 编译历史分页查询 |
| P1-06 | GET /compile/validate | 干跑验证 |
| P1-07 | POST /compile type 参数 | type=full\|incremental |
| P1-08 | Prometheus 自定义指标（5 个 histogram） | 全量/增量编译、验证、DAG、Function 执行 |
| P1-09 | 沙箱 os.system/__import__/subprocess 显式拦截 | CI lint 检查 |
| P1-10 | Nginx API Gateway | 独立 Nginx 服务，ssl + 限流 |
| P1-11 | TenantMiddleware | `request.state.tenant_id` 自动注入 |
| P1-12 | Keycloak OIDC 集成 | SSO 登录 |
| P1-13 | Dashboard 接入真实 API | 非 Mock 数据 |

---

## 4. P2 需求清单（3 项 — 后续）

| 编号 | 需求 |
|------|------|
| P2-01 | 固定 Docker 镜像版本（去除 `latest`） |
| P2-02 | `domain/ontology/` 目录结构迁移 |
| P2-03 | `implements` 字段类型从 JSONB 改为 UUID[] |

---

## 5. 非功能需求（NFR）

| 编号 | 类别 | 需求 | v2.2 目标 | 测量 |
|------|------|------|-----------|------|
| NFR-001 | 性能 | 全量编译 | < 8s | Prometheus |
| NFR-002 | 性能 | 增量编译 | < 1.5s | P95 |
| NFR-003 | 性能 | 运行时验证 | < 50ms | P95 |
| NFR-004 | 性能 | DAG 循环检测 | < 100ms | 100 节点 |
| NFR-005 | 安全 | Cypher 注入 | 0 漏洞 | 安全测试 |
| NFR-006 | 安全 | Function 沙箱 | 0 危险调用 | CI lint |
| NFR-007 | 工程 | 后端测试覆盖率 | ≥ 70% | pytest-cov |
| NFR-008 | 工程 | Alembic 迁移 | upgrade/downgrade 全流程 | CI |

---

## 6. 实施里程碑

| 里程碑 | Sprint | 交付物 | 验收方式 |
|--------|--------|--------|----------|
| M0a | S1 | 4 项安全修复完成 | 安全扫描 0 Critical |
| M0b | S1-S2 | 7 项 Ontology 数据模型修复 | `alembic upgrade head` + 表结构验证 |
| M1 | S3 | 编译器 v2.2（DAG + 验证器 + 回滚） | 全量 < 8s / 增量 < 1.5s |
| M2 | S4 | 三层架构分离 | Router 无 SQLAlchemy 查询 |
| M3 | S5 | 全部 P0 + P1 完成 | 30 项差距 27 项闭合 |
| M4 | S6 | 性能达标 + v2.2 Release | 全部 NFR 通过 |

---

## 7. P0 闭合计分卡

| 编号 | 需求 | Sprint | 状态 |
|------|------|--------|------|
| P0-SEC-01 | Cypher 白名单 | S1 | ⬜ |
| P0-SEC-02 | RestrictedPython 沙箱 | S1 | ⬜ |
| P0-SEC-03 | 真实 Auth 存储 | S2 | ⬜ |
| P0-SEC-04 | Document 查询真实化 | S2 | ⬜ |
| P0-ARCH-01 | Alembic 迁移 | S2 | ⬜ |
| P0-ARCH-02 | Celery Worker | S2 | ⬜ |
| P0-ARCH-03 | 三层分离 | S4 | ⬜ |
| P0-ONT-01 | DAG 依赖图 | S3 | ⬜ |
| P0-ONT-02 | 双阶段验证器 | S3 | ⬜ |
| P0-ONT-03 | 编译日志字段补全 | S2 | ⬜ |
| P0-ONT-04 | current_version 表 | S2 | ⬜ |
| P0-ONT-05 | 回滚端点 | S3 | ⬜ |
| P0-ONT-06 | SchemaRegistry 缓存 | S3 | ⬜ |
| P0-ONT-07 | 编译失败回滚 | S3 | ⬜ |

---

## 8. 参考文档

| 文档 | 用途 |
|------|------|
| [`GAP-ANALYSIS.md`](GAP-ANALYSIS.md) | 30 项差异全景分析 |
| [`ARCHITECTURE-REVIEW.md`](ARCHITECTURE-REVIEW.md) | 架构审查报告 |
| [`ONTOLOGY-DESIGN-v1.0.md`](ONTOLOGY-DESIGN-v1.0.md) | Ontology 模块详细设计 |
| [`ACCEPTANCE.md`](ACCEPTANCE.md) | 验收标准 |
| [`DEVPLAN-v2.2.md`](DEVPLAN-v2.2.md) | 开发计划 |
| [`TASKS.md`](TASKS.md) | 任务拆分 |

---

> **维护**：v2.2 基于 `GAP-ANALYSIS.md` 代码审查结果生成。P0 项闭合前不可发布正式版本。
