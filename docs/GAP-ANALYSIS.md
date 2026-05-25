# Meatapivot 差异分析报告

> **版本**：v1.0  
> **日期**：2026-05-25  
> **范围**：架构设计 vs 代码库实现 + Ontology 模块详细设计 vs 代码库实现

---

## 总览

| 模块 | 检查项 | P0 | P1 | P2 | 合计 |
|------|--------|----|----|----|------|
| **整体架构** | 12 | 7 | 3 | 1 | 11 |
| **Ontology 编译器** | 8 | 7 | 10 | 2 | 19 |
| **合计** | — | **14** | **13** | **3** | **30** |

---

## 一、整体架构差异

### P0（安全/功能缺陷）

| # | 差异点 | 设计目标 | 实际状态 | 文件位置 |
|---|--------|----------|----------|----------|
| 1 | **Auth 认证** | Keycloak/PostgreSQL 真实用户存储 | 完全 Mock，`login()` 接受任意凭据 | `routers/auth.py:44-83` |
| 2 | **Celery Worker** | RabbitMQ + Celery 独立异步任务服务 | 无 Celery 服务/依赖，用 `BackgroundTasks` | `docker-compose.yml`，`requirements.txt` |
| 3 | **Cypher 注入** | 白名单关键字（MATCH/WITH/RETURN/CALL/UNWIND） | 黑名单（仅过滤写操作关键字） | `routers/knowledge_graph.py:288-300` |
| 4 | **Function 沙箱** | RestrictedPython 安全执行 | `subprocess.run()` 临时文件执行 | `action_executor.py:351-396` |
| 5 | **Alembic 迁移** | `alembic revision --autogenerate` 管理 schema | `init.sql` + `Base.metadata.create_all()` | 无 `alembic/` 目录 |
| 6 | **Router 分层** | Router/Service/Repository 三层分离 | Router 含业务逻辑（如 853 行 `object_types.py`） | `routers/ontology/object_types.py` |
| 7 | **Document 查询** | 真实 PostgreSQL + MinIO | `get_document()` / `search_documents()` 返回 Mock | `routers/documents.py:83-109` |

### P1（架构问题）

| # | 差异点 | 当前状态 |
|---|--------|----------|
| 8 | API Gateway（Nginx） | 仅 `frontend/Dockerfile.prod` 内嵌 nginx |
| 9 | 多租户 Middleware | 无 `TenantMiddleware`，各 endpoint 手动提取 |
| 10 | Keycloak 集成 | Keycloak 运行但 Auth 代码未集成 |

### P2

| # | 差异点 | 当前状态 |
|---|--------|----------|
| 11 | Docker `latest` 标签 | `minio/minio:latest`, `one-api:latest` |

---

## 二、Ontology 模块差异

### 2.1 编译器架构

| # | 设计规范 | 实际代码 | 严重度 |
|---|----------|----------|--------|
| 1 | **DAG 依赖图**（拓扑排序 + 循环检测） | **缺失**。遍历为平面顺序，`networkx` 在 requirements.txt 但未使用 | **P0** |
| 2 | **分离发射器**（neo4j_emitter.py + schema_emitter.py） | **缺失**。全部内联在 `ontology_compiler.py`（378行单文件） | P1 |
| 3 | **增量编译 BFS 影响集** | `incremental_compile()` 仅编译单 ID，无可达下游 BFS | P1 |
| 4 | **6 阶段流水线**（加载→DAG→验证→生成→Schema→提交） | 方法离散存在但无编排 | P1 |
| 5 | **Prometheus 自定义指标** | 仅有 `duration_ms` 本地计时 | P1 |

### 2.2 验证系统

| # | 设计规范 | 实际代码 | 严重度 |
|---|----------|----------|--------|
| 6 | **验证子目录**（`services/validation/`） | **不存在** | **P0** |
| 7 | **静态验证器**（static_validator.py） | **缺失** | **P0** |
| 8 | **运行时验证器**（runtime_validator.py + Pydantic 动态模型） | **缺失** | **P0** |
| 9 | **SchemaRegistry 缓存**（Redis-backed） | **缺失** | P1 |

### 2.3 版本管理

| # | 设计规范 | 实际代码 | 严重度 |
|---|----------|----------|--------|
| 10 | **`ontology_current_version` 表** | **整表缺失** | **P0** |
| 11 | **回滚端点** `POST /compile/rollback` | **缺失** | **P0** |
| 12 | **编译日志字段**（parent_version, diff_snapshot, neo4j_stmts） | **全部缺失** | **P0** |
| 13 | **编译历史** `GET /compile/logs` | **缺失** | P1 |

### 2.4 沙箱与 API

| # | 设计规范 | 实际代码 | 严重度 |
|---|----------|----------|--------|
| 14 | **RestrictedPython 依赖** | **缺失** | P1 |
| 15 | **危险调用拦截**（os.system/__import__/subprocess） | **未显式拦截**（在子进程中执行但内部无限制） | P1 |
| 16 | **PATCH /object-types/{id}** | 仅 PUT 存在 | P1 |
| 17 | **GET /compile/validate**（干跑验证） | **缺失** | P1 |
| 18 | **POST /compile type 参数** | `POST /compile` 存在但无 `type` 参数 | P1 |
| 19 | **`domain/ontology/` 目录** | **完全不存在** | P2 |

---

## 三、数据库 Schema 差异

| 字段 | 设计规范 | 实际代码 | 严重度 |
|------|----------|----------|--------|
| `ontology_compile_logs.version` | TEXT（major.minor.patch） | **缺失** | **P0** |
| `ontology_compile_logs.parent_version` | TEXT | **缺失** | **P0** |
| `ontology_compile_logs.diff_snapshot` | JSONB | **缺失** | **P0** |
| `ontology_compile_logs.neo4j_stmts` | TEXT[] | **缺失** | **P0** |
| `ontology_compile_logs.rolled_back_at` | TIMESTAMPTZ | **缺失** | **P0** |
| `ontology_current_version` | 整表 | **整表缺失** | **P0** |
| `ontology_object_types.implements` | `UUID[]` | `JSONB` 字符串数组 | P2 |

---

## 四、性能监控差异

| 指标 | 目标 | 实际 |
|------|------|------|
| 全量编译（100类） | < 8s（Prometheus histogram） | `duration_ms` 本地计时，无 Prometheus |
| 增量编译 | < 1.5s（P95） | 同上 |
| 运行时验证 | < 50ms（缓存命中） | 不适用（无运行时验证器） |
| DAG 循环检测 | < 100ms | 不适用（无 DAG） |
| Function 执行超时 | 5s | 当前 30s 硬编码 |

---

## 五、差距优先级矩阵

### P0 汇总（14 项 — 阻塞上线）

| # | 来源 | 差异项 |
|---|------|--------|
| 1 | 架构 | Auth 完全 Mock（无真实 PostgreSQL 存储） |
| 2 | 架构 | 无 Celery Worker 异步任务服务 |
| 3 | 架构 | Cypher 注入使用黑名单 |
| 4 | 架构 | Function 沙箱使用 subprocess |
| 5 | 架构 | 无 Alembic 迁移 |
| 6 | 架构 | Router 混合业务逻辑 |
| 7 | 架构 | Document 查询返回 Mock |
| 8 | Ontology | 编译器无 DAG 依赖图 |
| 9 | Ontology | 无验证系统（static + runtime） |
| 10 | Ontology | 无 `ontology_current_version` 表 |
| 11 | Ontology | 无回滚端点 |
| 12 | Ontology | 编译日志表缺版本字段 |
| 13 | Ontology | 无 SchemaRegistry 缓存 |
| 14 | Ontology | 无 RestrictedPython 依赖 |

### P1 汇总（13 项）

| # | 差异项 |
|---|--------|
| 1 | 无 API Gateway (Nginx) |
| 2 | 无 TenantMiddleware |
| 3 | Keycloak 未集成 |
| 4 | 编译器单文件（未拆分发射器） |
| 5 | 增量编译无 BFS 影响集 |
| 6 | 无 Prometheus 指标 |
| 7 | 无 PATCH ObjectType |
| 8 | 无 compile/logs 端点 |
| 9 | 无 compile/validate 端点 |
| 10 | compile 无 type 参数 |
| 11 | 沙箱危险调用未拦截 |
| 12 | 无 6 阶段流水线编排 |
| 13 | 无编译失败事务回滚 |

### P2 汇总（3 项）

| # | 差异项 |
|---|--------|
| 1 | Docker 镜像 `latest` 标签 |
| 2 | `domain/ontology/` 目录平整为零 |
| 3 | `implements` 字段类型不同 |

---

## 六、修复实施建议

### Week 0-1：P0 安全基线（Sprint 1）

```
Day 1-2   FIX-002: Cypher 白名单（1d）
          FIX-003: RestrictedPython 沙箱（2d 开始）

Day 3-4   FIX-003: RestrictedPython 沙箱（完成）
          ONT-SCHEMA: 编译日志表补充字段（1d）
          ONT-CURRENT-VERSION: 新增表（0.5d）

Day 5     FIX-007: 实现真实 Auth 存储（2d 开始）
          FIX-008: 固定 Docker 镜像版本（0.5d）
```

### Week 2：P0 基础设施就绪（Sprint 2）

```
Day 1-2   FIX-007: 实现真实 Auth 存储（完成）
          FIX-004: Alembic 迁移配置（1d）

Day 3-5   FIX-006: Celery Worker 服务（3d）
          DOCUMENT-REAL: 修复 Document 查询 Mock（2d）
```

### Week 3-4：P1 编译器重构（Sprint 3）

```
Day 1-3   ONT-DAG: DAG 依赖图 + 循环检测（16h）
Day 4-6   ONT-COMPILER-SPLIT: 编译器五模块拆分（24h）
Day 7-8   ONT-VALIDATION: 双阶段验证器 + SchemaRegistry（16h）
Day 9-10  ONT-VERSIONING: 版本管理 + 回滚端点（16h）
```

### Week 5：P1 架构重构（Sprint 4）

```
Day 1-2   ONT-API: 新增 API 端点（PATCH/logs/rollback/validate）（8h）
Day 3-5   FIX-005: Router/Service/Repository 三层分离（40h，分模块并行）
          ├── Object Type 模块（2d 验证方案）
          ├── Link Type 模块（1d）
          ├── Interface 模块（1d）
          └── Action 模块（1d）
```

### Week 6-8：P1/P2 收尾（Sprint 5）

```
Day 1-2   Prometheus 自定义指标（8h）
Day 3-4   前端测试（16h）
Day 5-7   TenantMiddleware + Keycloak 集成（3d 可选）
Day 8-10  Nginx Gateway + 性能压测（24h）
```

---

> **维护**：本报告基于代码审查生成，与 `ARCHITECTURE-REVIEW.md` 和 `ONTOLOGY-DESIGN-v1.0.md` 配套使用。每个 Sprint 结束后更新完成状态。
