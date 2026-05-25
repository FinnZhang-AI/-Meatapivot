# Meatapivot Ontology 模块详细设计方案

> **版本**：v1.0  
> **日期**：2026-05-25  
> **状态**：技术设计文档 — 待开发评审  
> **负责团队**：后端架构组 + 产品组

---

## 1. 设计目标与范围

Ontology 模块是 Meatapivot 的语义核心，负责定义企业知识图谱的类型系统——即 ObjectType、LinkType、Interface 和 ActionType 的元数据管理、编译与运行时执行。本文档覆盖以下四个核心子系统：

| 子系统 | 核心职责 | 优先级 |
|--------|----------|--------|
| **编译器（Compiler）** | 将 Ontology 定义编译为 Neo4j 约束 + Pydantic Schema，支持增量编译与版本回滚 | **P0 必须** |
| **Interface 验证链路** | 静态结构验证（编译时）+ 动态实例验证（运行时），双阶段错误分离 | **P0 必须** |
| **版本管理（Versioning）** | 每次编译生成语义版本，保留完整变更历史，支持一键回滚 | **P1 重要** |
| **Function 沙箱（Sandbox）** | 安全执行用户自定义函数，三阶段沙箱演进策略 | **P1 重要** |

---

## 2. 五层语义模型

整个 Ontology 系统由上到下分为五层：

| # | 层次 | 职责 | 技术实现 |
|---|------|------|----------|
| **L1** | 定义层 | ObjectType / LinkType Schema 定义 | PostgreSQL + Pydantic |
| **L2** | 语义约束层 | Interface 声明与检查 | Python 验证引擎 |
| **L3** | 编译层 | 定义编译为 Neo4j 约束 + Pydantic 动态模型 | OntologyCompiler |
| **L4** | 实例层 | Objects / Links 运行时数据 | Neo4j + RLS |
| **L5** | 行动层 | ActionType 执行 + Function 沙箱 | Celery + Sandbox |

---

## 3. 编译器（OntologyCompiler）详细设计

### 3.1 六阶段编译流程

| 阶段 | 名称 | 执行内容 | 失败行为 |
|------|------|----------|----------|
| ① | 加载 | 从 PostgreSQL 读取该租户全量 Ontology 定义 | 返回 404/503 |
| ② | DAG 构建 | 构建 ObjectType → Interface → LinkType 的有向无环图 | 检测到循环 → 返回循环路径 |
| ③ | 静态验证 | 检查 Interface 实现完整性、属性类型合法性、LinkType 端点存在性 | 收集全部错误后一次性返回 |
| ④ | 约束生成 | 生成幂等的 Neo4j CONSTRAINT Cypher（`IF NOT EXISTS`） | 语法错误 → 阻断，不执行 |
| ⑤ | Schema 生成 | 生成 Pydantic 动态模型和 JSON Schema，注册到 SchemaRegistry | 序列化错误 → 回滚 |
| ⑥ | 版本提交 | 写入 compile_logs，更新 current_version，广播编译完成事件 | DB 事务失败 → 全量回滚 |

### 3.2 DAG 依赖图

- 用于：循环依赖检测、编译顺序确定、增量编译影响集计算
- 算法：Kahn 算法拓扑排序 + BFS 下游影响集
- 实现：`domain/ontology/services/compiler/dag.py`

### 3.3 Neo4j 约束生成（幂等）

| 约束类型 | Cypher 模板 |
|----------|------------|
| 唯一性约束 | `CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE` |
| 存在性约束 | `CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.tenant_id IS NOT NULL` |
| 属性类型约束 | `CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS :: {type}` |

### 3.4 增量编译

全量编译仅在首次部署或强制刷新时执行。日常变更触发增量编译：
1. 加载全量 DAG
2. BFS 计算下游影响集
3. 仅加载受影响类型
4. 验证受影响类型
5. 生成约束（仅受影响部分）
6. Bump patch version

---

## 4. Interface 验证链路设计

### 4.1 双阶段验证模型

| 维度 | 编译时验证（静态） | 运行时验证（动态） |
|------|-------------------|-------------------|
| **触发时机** | 调用 POST /compile 时 | 写入 Object 实例时（CREATE/UPDATE） |
| **检查内容** | Interface 属性是否存在于 ObjectType 定义中 | 实例字段值类型、非空、枚举范围 |
| **错误返回** | CompileError 列表 | ValidationError → 422 |
| **性能** | 一次性批量 | 每次写入，缓存 Schema |

### 4.2 SchemaRegistry 缓存

```python
class SchemaRegistry:
    """缓存编译生成的 Pydantic 模型，Redis-backed"""
    def get_model(tenant_id, obj_type_id) -> BaseModel
    def invalidate(tenant_id)
    def _build_model(tenant_id, obj_type_id) -> BaseModel  # create_model()
```

---

## 5. 版本管理设计

### 5.1 语义版本规则

| 版本类型 | 触发条件 | 示例 |
|----------|----------|------|
| Major | 删除/重命名 ObjectType（破坏性变更） | 1.0.0 → 2.0.0 |
| Minor | 新增 ObjectType/LinkType/Interface（兼容扩展） | 1.0.0 → 1.1.0 |
| Patch | 修改属性默认值/描述（增量编译） | 1.0.0 → 1.0.1 |
| 回滚 | POST /compile/rollback | 1.2.3 → rollback to 1.1.0 |

### 5.2 数据库 Schema

```sql
CREATE TABLE ontology_compile_logs (
    id               UUID PRIMARY KEY,
    tenant_id        UUID NOT NULL,
    version          TEXT NOT NULL,          -- major.minor.patch
    parent_version   TEXT,                   -- 父版本（用于回滚链）
    compile_type     TEXT NOT NULL,          -- full | incremental
    affected_types   UUID[] NOT NULL,
    diff_snapshot    JSONB NOT NULL,         -- 变更 diff
    neo4j_stmts      TEXT[],                 -- 执行的 Cypher
    status           TEXT NOT NULL,          -- pending/success/failed/rolled_back
    rolled_back_at   TIMESTAMPTZ,
    rolled_back_by   UUID
);

CREATE TABLE ontology_current_version (
    tenant_id   UUID PRIMARY KEY,
    version     TEXT NOT NULL,
    log_id      UUID REFERENCES ontology_compile_logs(id),
    updated_at  TIMESTAMPTZ
);
```

### 5.3 回滚实现

1. 恢复 PostgreSQL Ontology 定义到目标版本 snapshot
2. 重新触发全量编译（重新生成 Neo4j 约束和 Schema）
3. 更新 current_version 记录
4. 使 SchemaRegistry 缓存失效

---

## 6. Function 沙箱三阶段演进

| 阶段 | 方案 | 隔离能力 | 实施周期 |
|------|------|----------|----------|
| **Phase 1**（当前 P0） | RestrictedPython + 白名单 | 禁用 import/open/__builtins__ | 1周 |
| **Phase 2**（P1） | Pyodide（WebAssembly） | WASM 沙箱，完全隔离文件系统/网络 | 3周 |
| **Phase 3**（P2） | gVisor 容器 | 内核级隔离，30s超时+256MB内存+零网络 | 6周 |

### RestrictedPython 实现要点

```python
ALLOWED_BUILTINS = {
    "len", "range", "enumerate", "list", "dict", "str", "int", "float",
    "sum", "min", "max", "sorted",
    # 明确禁止: open, exec, eval, __import__, compile, subprocess
}

byte_code = compile_restricted(code, "<function>", "exec")
# exec with timeout via asyncio.wait_for
```

---

## 7. API 接口设计

### 7.1 完整 API 列表

| Method | Path | 功能 |
|--------|------|------|
| GET | `/api/v1/ontology/object-types` | 列出 ObjectType |
| POST | `/api/v1/ontology/object-types` | 创建 ObjectType |
| PATCH | `/api/v1/ontology/object-types/{id}` | 增量更新（新增） |
| DELETE | `/api/v1/ontology/object-types/{id}` | 归档（软删除） |
| POST | `/api/v1/ontology/compile` | 触发编译（type=full\|incremental） |
| GET | `/api/v1/ontology/compile/logs` | 编译历史（新增） |
| POST | `/api/v1/ontology/compile/rollback` | 回滚到指定版本（新增） |
| GET | `/api/v1/ontology/compile/validate` | 干跑验证不提交（新增） |
| POST | `/api/v1/ontology/functions/{id}/execute` | 执行 Function |

---

## 8. 目标目录结构

```
backend/app/
├── domain/ontology/
│   ├── models/
│   │   ├── object_type.py
│   │   ├── link_type.py
│   │   ├── interface.py
│   │   └── action_type.py
│   ├── services/
│   │   ├── ontology_service.py
│   │   ├── compiler/
│   │   │   ├── dag.py              # DAG 依赖图
│   │   │   ├── neo4j_emitter.py    # Neo4j 约束生成
│   │   │   ├── schema_emitter.py   # Pydantic 动态模型
│   │   │   ├── incremental.py      # 增量编译
│   │   │   └── compiler.py         # 主入口编排
│   │   ├── validation/
│   │   │   ├── static_validator.py
│   │   │   └── runtime_validator.py
│   │   ├── versioning.py
│   │   └── sandbox/
│   │       ├── restricted.py       # RestrictedPython (P1)
│   │       └── container.py        # gVisor (P2)
│   └── repositories/
│       ├── ontology_repo.py
│       └── neo4j_repo.py
└── routers/ontology/               # 仅 HTTP 转换
    ├── object_types.py
    ├── link_types.py
    └── compile.py
```

---

## 9. 性能目标

| 指标 | 目标值 | 测量方式 | 告警阈值 |
|------|--------|----------|----------|
| 全量编译（100类型） | < 8s | Prometheus histogram | > 15s |
| 增量编译 | < 1.5s | P95 响应时间 | > 5s |
| 运行时 Schema 验证 | < 50ms（缓存命中） | P95 | > 200ms |
| Schema 缓存命中率 | > 95% | schema_registry_hit_rate | < 80% |
| Function 执行超时 | 5s | function_execution_duration | > 4.5s 预警 |
| DAG 循环检测 | < 100ms | 100 节点 | > 500ms |

---

## 10. 验收标准

### 功能验收

| 优先级 | 验收项 | 通过标准 |
|--------|--------|----------|
| **P0** | 循环依赖检测 | A→B→A 返回完整循环路径 |
| **P0** | Interface 缺失属性 | 编译返回 detail 字段 |
| **P0** | Function 注入攻击 | `import os; os.environ` 返回 SecurityError |
| **P0** | 跨租户编译隔离 | 租户A不影响租户B的 Neo4j 约束 |
| P1 | 增量编译正确性 | affected_count 正确 |
| P1 | 版本回滚 | Neo4j 约束恢复 |
| P1 | 编译失败回滚 | PostgreSQL 数据不变 |
| P1 | SchemaRegistry 失效 | 下一次验证使用新版本 |
| P2 | 归档保护 | 有实例的 ObjectType 返回 409 |
| P2 | 并发编译互斥 | 第二次返回 423 Locked |

### 代码质量

| 指标 | 目标 |
|------|------|
| 编译器核心逻辑单元测试覆盖率 | ≥ 85% |
| Router 层无业务逻辑 | Code Review 100% 通过 |
| 所有写操作带 tenant_id | 静态分析 0 violation |
| Function 代码必须经沙箱 | CI lint 检查 |
| API 文档完整性 | 所有端点有描述 + 示例响应 |

---

---

## 11. 代码审查差异分析（附录）

> 此附录于 v2.2 新增，记录设计规范与实际代码库的差异。

### 编译器差异

| # | 设计规范 | 实际代码 | 严重度 | 任务编号 |
|---|----------|----------|--------|----------|
| 1 | DAG 依赖图（拓扑排序 + 循环检测） | 平面遍历，无 DAG，`networkx` 未使用 | **P0** | S3-1 |
| 2 | 分离发射器（neo4j_emitter/schema_emitter） | 全部内联 `ontology_compiler.py`（378行） | P1 | S3-2 |
| 3 | 增量编译 BFS 影响集 | `incremental_compile()` 仅编译单 ID | P1 | S3-2 |
| 4 | 6 阶段流水线编排 | 方法离散存在但无编排 | P1 | S3-7 |

### 验证器差异

| # | 设计规范 | 实际代码 | 严重度 | 任务编号 |
|---|----------|----------|--------|----------|
| 5 | `validation/static_validator.py` | **不存在** | **P0** | S3-3 |
| 6 | `runtime_validator.py` + Pydantic 动态模型 | **不存在** | **P0** | S3-3 |
| 7 | SchemaRegistry 缓存（Redis） | **不存在** | **P0** | S3-4 |

### 版本管理差异

| # | 设计规范 | 实际代码 | 严重度 | 任务编号 |
|---|----------|----------|--------|----------|
| 8 | `ontology_current_version` 表 | **整表缺失** | **P0** | S2-5 |
| 9 | 编译日志表 version/parent_version/diff_snapshot/neo4j_stmts 字段 | **全部缺失** | **P0** | S2-4 |
| 10 | `POST /compile/rollback` | **缺失** | **P0** | S3-5 |
| 11 | `GET /compile/logs` | **缺失** | P1 | S5-1 |

### 沙箱差异

| # | 设计规范 | 实际代码 | 严重度 | 任务编号 |
|---|----------|----------|--------|----------|
| 12 | RestrictedPython + 白名单 | `subprocess.run()` 临时文件执行 | **P0** | S1-2 |
| 13 | `os.system/__import__/subprocess` 拦截 | 未显式拦截（子进程中但内部无限制） | P1 | S1-2 |

### API 差异

| # | 设计规范 | 实际代码 | 严重度 | 任务编号 |
|---|----------|----------|--------|----------|
| 14 | `PATCH /object-types/{id}` | 仅 PUT | P1 | S5-1 |
| 15 | `GET /compile/validate` | **缺失** | P1 | S5-1 |
| 16 | `POST /compile` type 参数 | 无 type 参数 | P1 | S5-1 |

### 目录结构差异

| # | 设计规范 | 实际代码 | 严重度 |
|---|----------|----------|--------|
| 17 | `domain/ontology/models/`（4文件） | `models/ontology_models.py`（单文件） | P2 |
| 18 | `domain/ontology/services/compiler/`（5文件） | `services/ontology_compiler.py`（单文件） | P2 |
| 19 | `domain/ontology/services/validation/`（2文件） | **不存在** | P2 |

### 性能监控差异

| # | 设计规范 | 实际代码 | 严重度 |
|---|----------|----------|--------|
| 20 | Prometheus histogram ×5 | 仅本地 `duration_ms` | P1 |
| 21 | 全量编译 < 8s | 无强制约束 | P1 |
| 22 | 增量编译 < 1.5s | 无强制约束 | P1 |

> **总计**：22 项差异，其中 P0 6 项，P1 10 项，P2 6 项。详见 `GAP-ANALYSIS.md`。

---

> **维护**：本文档由产品/架构联合评审。代码审查差异分析部分随 Sprint 进度更新。所有 P0 安全修复应在正式发版前完成。
