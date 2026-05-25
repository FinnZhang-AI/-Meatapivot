# Meatapivot Ontology 模块详细设计方案

> **文档状态**：草稿 → 评审中  
> **版本**：v1.0  
> **日期**：2026-05  
> **负责团队**：后端架构组 + 产品组

---

## 1. 设计目标与范围

Ontology 模块是 Meatapivot 的语义核心，负责定义企业知识图谱的"类型系统"——即对象类型（ObjectType）、连接类型（LinkType）、接口（Interface）和行动类型（ActionType）的元数据管理、编译与运行时执行。本文档覆盖以下四个核心子系统的完整设计：

| 子系统 | 核心职责 | 优先级 |
|--------|----------|--------|
| **编译器（Compiler）** | 将 Ontology 定义编译为 Neo4j 约束 + Pydantic Schema，支持增量编译与版本回滚 | **P0 必须** |
| **Interface 验证链路** | 静态结构验证（编译时）+ 动态实例验证（运行时），双阶段错误分离 | **P0 必须** |
| **版本管理（Versioning）** | 每次编译生成语义版本，保留完整变更历史，支持一键回滚到任意版本 | **P1 重要** |
| **Function 沙箱（Sandbox）** | 安全执行用户定义的自定义函数，三阶段沙箱演进策略 | **P1 重要** |

---

## 2. Ontology 架构分层

### 2.1 五层语义模型

| # | 层次 | 职责 | 技术实现 |
|---|------|------|----------|
| **L1** | 定义层 | ObjectType / LinkType 的 Schema 定义，存储于 PostgreSQL | PostgreSQL + Pydantic |
| **L2** | 语义约束层 | Interface 声明与检查，确保 ObjectType 实现约定的属性集合 | Python 验证引擎 |
| **L3** | 编译层 | 将 L1/L2 定义编译为 Neo4j 约束、Pydantic 动态模型、JSON Schema | OntologyCompiler |
| **L4** | 实例层 | Objects / Links 运行时数据，带 tenant_id 的图数据 | Neo4j + RLS |
| **L5** | 行动层 | ActionType 执行、Function 沙箱调用、事件触发 | Celery + Sandbox |

### 2.2 目录结构重构

当前 `ontology_compiler.py` 单文件承担了过多职责，需拆分为以下结构：

```
backend/app/
├── domain/ontology/                  # 领域层（新增）
│   ├── models/                       # 数据模型
│   │   ├── object_type.py            # ObjectType ORM + Pydantic
│   │   ├── link_type.py              # LinkType ORM + Pydantic
│   │   ├── interface.py              # Interface ORM + Pydantic
│   │   └── action_type.py            # ActionType ORM + Pydantic
│   ├── services/                     # 业务服务层（新增）
│   │   ├── ontology_service.py       # 增删改查编排
│   │   ├── compiler/                 # 编译子系统
│   │   │   ├── dag.py                # 依赖图构建与拓扑排序
│   │   │   ├── neo4j_emitter.py      # 生成 Cypher 约束语句
│   │   │   ├── schema_emitter.py     # 生成 Pydantic / JSON Schema
│   │   │   ├── incremental.py        # 增量编译引擎
│   │   │   └── compiler.py           # 主入口编排
│   │   ├── validation/               # 验证子系统
│   │   │   ├── static_validator.py   # 编译时静态验证
│   │   │   └── runtime_validator.py  # 运行时实例验证
│   │   ├── versioning.py             # 版本管理
│   │   └── sandbox/                  # Function 沙箱
│   │       ├── restricted.py         # RestrictedPython（P1）
│   │       └── container.py          # gVisor 容器（P2）
│   └── repositories/                 # 数据访问层（新增）
│       ├── ontology_repo.py          # PostgreSQL CRUD
│       └── neo4j_repo.py             # Neo4j 图操作
└── routers/ontology/                 # 路由层（已有，职责精简）
    ├── object_types.py               # 仅做 HTTP 入参/出参转换
    ├── link_types.py
    └── compile.py
```

---

## 3. 编译器（OntologyCompiler）详细设计

### 3.1 编译流程总览

编译器分为六个阶段，每个阶段失败都会阻断后续阶段，并返回结构化的错误信息：

| 阶段 | 名称 | 执行内容 | 失败行为 |
|------|------|----------|----------|
| ① | 加载 | 从 PostgreSQL 读取该租户当前版本的全量 Ontology 定义 | 返回 404 / 503 |
| ② | DAG 构建 | 构建 ObjectType → Interface → LinkType 的有向无环图 | 检测到循环依赖 → 返回循环路径 |
| ③ | 静态验证 | 检查 Interface 实现完整性、属性类型合法性、LinkType 端点存在性 | 收集全部错误后一次性返回 |
| ④ | 约束生成 | 为每个 ObjectType 生成幂等的 Neo4j CONSTRAINT Cypher | 语法错误 → 阻断，不执行 Neo4j |
| ⑤ | Schema 生成 | 生成 Pydantic 动态模型和 JSON Schema，注册到 SchemaRegistry | 序列化错误 → 回滚本次编译 |
| ⑥ | 版本提交 | 写入 ontology_compile_logs，更新 current_version，广播编译完成事件 | DB 事务失败 → 全量回滚 |

### 3.2 DAG 依赖图设计

依赖图是编译器的基础，用于：① 检测循环依赖；② 确定编译顺序；③ 计算增量编译时的影响集合。

```python
# domain/ontology/services/compiler/dag.py

from collections import defaultdict, deque
from uuid import UUID
from dataclasses import dataclass, field

@dataclass
class OntologyNode:
    id: UUID
    kind: str  # "object_type" | "interface" | "link_type"
    deps: list[UUID] = field(default_factory=list)

class OntologyDAG:
    def __init__(self):
        self.nodes: dict[UUID, OntologyNode] = {}
        self.graph: dict[UUID, set[UUID]] = defaultdict(set)
        self.reverse: dict[UUID, set[UUID]] = defaultdict(set)

    def add_node(self, node: OntologyNode):
        self.nodes[node.id] = node
        for dep in node.deps:
            self.graph[dep].add(node.id)       # dep → node
            self.reverse[node.id].add(dep)

    def topological_sort(self) -> list[UUID]:
        """Kahn 算法拓扑排序，同时检测循环"""
        in_degree = {nid: len(deps) for nid, deps in self.reverse.items()}
        queue = deque([nid for nid in self.nodes if in_degree.get(nid, 0) == 0])
        order = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for neighbor in self.graph.get(nid, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        if len(order) != len(self.nodes):
            cycle = self._find_cycle()
            raise CyclicDependencyError(cycle)
        return order

    def affected_nodes(self, changed_ids: list[UUID]) -> set[UUID]:
        """BFS 找出所有受变更影响的下游节点（用于增量编译）"""
        affected = set(changed_ids)
        queue = deque(changed_ids)
        while queue:
            nid = queue.popleft()
            for neighbor in self.graph.get(nid, set()):
                if neighbor not in affected:
                    affected.add(neighbor)
                    queue.append(neighbor)
        return affected
```

### 3.3 Neo4j 约束生成

约束生成必须满足幂等性（使用 `IF NOT EXISTS`），避免重复执行时报错。需生成三类约束：

| 约束类型 | Cypher 模板 | 说明 |
|----------|------------|------|
| 唯一性约束 | `CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE` | 每个 ObjectType 必须有 |
| 存在性约束 | `CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.tenant_id IS NOT NULL` | 多租户强制 |
| 属性类型约束 | `CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS :: {type}` | Neo4j 5.x+ 支持 |

### 3.4 增量编译引擎

全量编译仅在首次部署或强制刷新时执行。日常变更应触发增量编译：只重新编译变更节点及其下游影响集。

```python
# domain/ontology/services/compiler/incremental.py

async def incremental_compile(
    tenant_id: UUID,
    changed_object_type_ids: list[UUID],
    session: AsyncSession,
) -> CompileResult:
    # 1. 加载全量 DAG
    dag = await build_dag(tenant_id, session)

    # 2. 计算影响集合
    affected = dag.affected_nodes(changed_object_type_ids)

    # 3. 仅加载受影响的 ObjectType 定义
    affected_types = await ontology_repo.get_by_ids(affected, tenant_id, session)

    # 4. 验证受影响类型
    errors = static_validator.validate_subset(affected_types, dag)
    if errors:
        return CompileResult(success=False, errors=errors)

    # 5. 生成约束（仅受影响部分）
    constraints = [neo4j_emitter.emit(t) for t in affected_types]
    await neo4j_repo.apply_constraints(constraints, tenant_id)

    # 6. 更新版本（bump patch version）
    new_version = await versioning.bump_patch(tenant_id, affected, session)
    return CompileResult(success=True, version=new_version, affected_count=len(affected))
```

---

## 4. Interface 验证链路设计

### 4.1 双阶段验证模型

| 维度 | 编译时验证（静态） | 运行时验证（动态） |
|------|-------------------|-------------------|
| 触发时机 | 调用 POST /compile 时 | 写入 Object 实例时（CREATE/UPDATE） |
| 检查内容 | Interface 声明的属性是否全部存在于 ObjectType 定义中 | 实例字段值是否符合属性类型、非空约束、枚举范围 |
| 错误返回 | CompileError 列表，阻断编译 | ValidationError 列表，阻断写入，返回 422 |
| 性能影响 | 一次性批量验证，编译期开销 | 每次写入都执行，需缓存 Schema |
| 关注点 | 用户定义 Ontology 时的结构错误提示 | 用户填写 Object 属性时的字段校验提示 |

### 4.2 静态验证器实现

```python
# domain/ontology/services/validation/static_validator.py

class StaticValidationError:
    object_type_id: UUID
    object_type_name: str
    interface_id: UUID
    interface_name: str
    error_kind: Literal[
        "missing_property",     # 接口要求的属性未在 ObjectType 中声明
        "type_mismatch",        # 属性存在但类型不兼容
        "circular_dependency",  # DAG 中存在循环
        "orphan_link_type",     # LinkType 引用了不存在的 ObjectType
    ]
    detail: str


def validate_interfaces(
    object_types: list[ObjectType],
    interfaces: dict[UUID, Interface],
    dag: OntologyDAG,
) -> list[StaticValidationError]:
    errors = []
    for obj_type in object_types:
        for iface_id in obj_type.implements:
            iface = interfaces.get(iface_id)
            if not iface:
                continue
            for req_prop in iface.required_properties:
                declared = {p.name: p for p in obj_type.properties}
                if req_prop.name not in declared:
                    errors.append(StaticValidationError(
                        object_type_id=obj_type.id,
                        object_type_name=obj_type.name,
                        interface_id=iface_id,
                        interface_name=iface.name,
                        error_kind="missing_property",
                        detail=f"属性 {req_prop.name!r} 为 Interface {iface.name!r} 必须实现",
                    ))
                elif not is_type_compatible(declared[req_prop.name].type, req_prop.type):
                    errors.append(StaticValidationError(
                        ..., error_kind="type_mismatch",
                        detail=f"属性 {req_prop.name!r} 类型不兼容：期望 {req_prop.type}，实际 {declared[req_prop.name].type}",
                    ))
    return errors
```

### 4.3 运行时验证器实现

运行时验证在 Object 写入前执行，使用编译生成的 Pydantic 动态模型，避免重复解析 Schema：

```python
# domain/ontology/services/validation/runtime_validator.py

class SchemaRegistry:
    """缓存编译生成的 Pydantic 模型"""
    _cache: dict[str, type[BaseModel]] = {}

    def get_model(self, tenant_id: UUID, obj_type_id: UUID) -> type[BaseModel]:
        version = redis.get(f"ontology_version:{tenant_id}")
        key = f"{tenant_id}:{obj_type_id}:{version}"
        if key not in self._cache:
            self._cache[key] = self._build_model(tenant_id, obj_type_id)
        return self._cache[key]

    def _build_model(self, tenant_id, obj_type_id) -> type[BaseModel]:
        obj_type = ontology_repo.get(obj_type_id, tenant_id)
        fields = {
            prop.name: (PROP_TYPE_MAP[prop.type], ... if prop.required else None)
            for prop in obj_type.properties
        }
        return create_model(f"Object_{obj_type.name}", **fields)

    def invalidate(self, tenant_id: UUID):
        keys = [k for k in self._cache if k.startswith(str(tenant_id))]
        for k in keys:
            del self._cache[k]


async def validate_object_data(
    data: dict,
    obj_type_id: UUID,
    tenant_id: UUID,
) -> list[RuntimeValidationError]:
    model = schema_registry.get_model(tenant_id, obj_type_id)
    try:
        model(**data)
        return []
    except ValidationError as e:
        return [RuntimeValidationError.from_pydantic(err) for err in e.errors()]
```

---

## 5. 版本管理设计

### 5.1 数据库 Schema

```sql
-- 编译版本日志表（PostgreSQL）
CREATE TABLE ontology_compile_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL REFERENCES tenants(id),
    version          TEXT NOT NULL,           -- 语义版本：major.minor.patch
    parent_version   TEXT,                    -- 父版本，用于回滚链
    compile_type     TEXT NOT NULL,           -- "full" | "incremental"
    affected_types   UUID[] NOT NULL,         -- 受影响的 ObjectType IDs
    diff_snapshot    JSONB NOT NULL,          -- 变更 diff 快照
    neo4j_stmts      TEXT[],                  -- 执行的 Cypher 语句（用于 audit）
    status           TEXT NOT NULL DEFAULT 'pending',
    error_detail     TEXT,                    -- 失败时的错误信息
    compiled_by      UUID REFERENCES users(id),
    compiled_at      TIMESTAMPTZ DEFAULT now(),
    rolled_back_at   TIMESTAMPTZ,
    rolled_back_by   UUID REFERENCES users(id)
);

-- 当前活跃版本（每个租户一行）
CREATE TABLE ontology_current_version (
    tenant_id   UUID PRIMARY KEY REFERENCES tenants(id),
    version     TEXT NOT NULL,
    log_id      UUID REFERENCES ontology_compile_logs(id),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

### 5.2 版本号规则

| 版本类型 | 触发条件 | 示例 |
|----------|----------|------|
| **Major 递增** | 删除或重命名已有 ObjectType / Interface（破坏性变更） | 1.0.0 → 2.0.0 |
| **Minor 递增** | 新增 ObjectType、LinkType、Interface（向后兼容扩展） | 1.0.0 → 1.1.0 |
| **Patch 递增** | 修改属性默认值、更新描述、增量编译少量字段变更 | 1.0.0 → 1.0.1 |
| **回滚** | 调用 POST /compile/rollback，恢复到指定 log_id 的状态 | 1.2.3 → rollback to 1.1.0 |

### 5.3 回滚实现

```python
# domain/ontology/services/versioning.py

async def rollback_to_version(
    tenant_id: UUID,
    target_log_id: UUID,
    operator_id: UUID,
    session: AsyncSession,
) -> RollbackResult:
    target_log = await session.get(OntologyCompileLog, target_log_id)
    if target_log.tenant_id != tenant_id:
        raise PermissionError("无权访问目标版本")

    # 1. 恢复 PostgreSQL 中的 Ontology 定义
    await ontology_repo.restore_snapshot(tenant_id, target_log.diff_snapshot, session)

    # 2. 重新触发全量编译
    compile_result = await full_compile(tenant_id, session)

    # 3. 更新当前版本记录
    await session.execute(
        update(OntologyCurrentVersion)
        .where(OntologyCurrentVersion.tenant_id == tenant_id)
        .values(version=target_log.version, log_id=target_log_id)
    )

    # 4. 使 SchemaRegistry 缓存失效
    schema_registry.invalidate(tenant_id)

    return RollbackResult(version=target_log.version)
```

---

## 6. Function 沙箱三阶段演进策略

### 6.1 风险评估

**高危**：当前直接使用 `subprocess.run()` 执行用户 Python 代码，存在严重安全风险：可读取环境变量、发起任意网络请求、访问文件系统。此问题需 P0 级别优先修复。

| 阶段 | 方案 | 隔离能力 | 实施周期 |
|------|------|----------|----------|
| **Phase 1（当前 P0）** | RestrictedPython + 白名单 | 禁用 import/open/__builtins__ 危险方法，允许纯计算逻辑 | 1 周 |
| **Phase 2（P1）** | Pyodide（WebAssembly） | WASM 沙箱，完全隔离文件系统和网络 | 3 周 |
| **Phase 3（P2）** | gVisor 容器 | 内核级隔离，30s 超时 + 256MB 内存 + 零网络访问 | 6 周 |

### 6.2 Phase 1 实现（RestrictedPython）

```python
# domain/ontology/services/sandbox/restricted.py

from RestrictedPython import compile_restricted, safe_globals, safe_builtins
from RestrictedPython.Guards import safe_iter_unpack_sequence, guarded_getattr
import asyncio

ALLOWED_BUILTINS = {
    **safe_builtins,
    "len": len, "range": range, "enumerate": enumerate,
    "list": list, "dict": dict, "str": str, "int": int, "float": float,
    "sum": sum, "min": min, "max": max, "sorted": sorted,
    "bool": bool, "tuple": tuple, "set": set, "abs": abs,
    "round": round, "zip": zip, "map": map, "filter": filter,
}

async def execute_function(
    code: str,
    input_data: dict,
    timeout: float = 5.0,
) -> FunctionResult:
    try:
        byte_code = compile_restricted(code, "<function>", "exec")
    except SyntaxError as e:
        return FunctionResult(success=False, error=f"语法错误: {e}")

    glb = {
        **safe_globals,
        "__builtins__": ALLOWED_BUILTINS,
        "_getattr_": guarded_getattr,
        "_iter_unpack_sequence_": safe_iter_unpack_sequence,
        "input": input_data,
        "result": None,
    }

    try:
        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, exec, byte_code, glb),
            timeout=timeout
        )
        return FunctionResult(success=True, output=glb.get("result"))
    except asyncio.TimeoutError:
        return FunctionResult(success=False, error="执行超时（限制 5 秒）")
    except Exception as e:
        return FunctionResult(success=False, error=str(e))
```

---

## 7. API 接口设计

### 7.1 Ontology 管理 API

| Method | Path | 功能 | 关键参数/响应 |
|--------|------|------|--------------|
| **GET** | /api/v1/ontology/object-types | 列出所有 ObjectType | `include_archived=bool` |
| **POST** | /api/v1/ontology/object-types | 创建 ObjectType | 返回 201 + 新对象 |
| **PATCH** | /api/v1/ontology/object-types/{id} | 更新 ObjectType（增量） | 不可变字段返回 422 |
| **DELETE** | /api/v1/ontology/object-types/{id} | 归档 ObjectType（软删除） | 有实例时返回 409 |
| **POST** | /api/v1/ontology/compile | 触发全量/增量编译 | `type=full\|incremental` |
| **GET** | /api/v1/ontology/compile/logs | 查询编译历史 | `limit, offset, status` |
| **POST** | /api/v1/ontology/compile/rollback | 回滚到指定版本 | `target_log_id: UUID` |
| **GET** | /api/v1/ontology/compile/validate | 仅执行静态验证不提交 | 返回错误列表 |
| **POST** | /api/v1/ontology/functions/{id}/execute | 执行自定义 Function | `input_data: dict` |

### 7.2 关键响应结构

```python
# 编译结果响应
class CompileResponse(BaseModel):
    success: bool
    version: str                              # e.g. "1.3.0"
    compile_type: Literal["full", "incremental"]
    affected_count: int                       # 受影响的 ObjectType 数量
    duration_ms: int                          # 编译耗时
    errors: list[StaticValidationError]       # 失败时返回，成功时为空
    log_id: UUID                              # 用于后续 rollback

# 静态验证错误
class StaticValidationError(BaseModel):
    object_type_name: str
    interface_name: str | None
    error_kind: str
    detail: str
    suggestion: str | None                    # 给用户的修复建议
```

---

## 8. 完整数据库 Schema

```sql
-- PostgreSQL: Ontology 核心表

CREATE TABLE ontology_object_types (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    name          TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    description   TEXT,
    implements    UUID[],                    -- Interface IDs
    properties    JSONB NOT NULL DEFAULT '[]',
    status        TEXT DEFAULT 'active',     -- active | archived | draft
    version       INT DEFAULT 1,             -- 乐观锁
    created_by    UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE ontology_interfaces (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    name                TEXT NOT NULL,
    required_properties JSONB NOT NULL DEFAULT '[]',
    required_links      JSONB DEFAULT '[]',
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ontology_link_types (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    name         TEXT NOT NULL,
    source_type  UUID NOT NULL REFERENCES ontology_object_types(id),
    target_type  UUID NOT NULL REFERENCES ontology_object_types(id),
    cardinality  TEXT DEFAULT 'MANY_TO_MANY',
    properties   JSONB DEFAULT '[]',
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ontology_functions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    name         TEXT NOT NULL,
    description  TEXT,
    code         TEXT NOT NULL,
    language     TEXT DEFAULT 'python',
    version      INT DEFAULT 1,
    created_at   TIMESTAMPTZ DEFAULT now()
);
```

---

## 9. 性能目标与监控指标

| 指标 | 目标值 | 测量方式 | 告警阈值 |
|------|--------|----------|----------|
| 全量编译（100个 ObjectType） | **< 8 秒** | Prometheus histogram: `ontology_compile_duration_seconds` | > 15s |
| 增量编译（单个类型变更） | **< 1.5 秒** | P95 响应时间 | > 5s |
| 运行时 Schema 验证（单次） | **< 50ms** | P95，已命中缓存 | > 200ms |
| Schema 缓存命中率 | **> 95%** | `schema_registry_hit_rate` | < 80% |
| Function 执行（Phase 1） | **< 5 秒超时** | `function_execution_duration_seconds` | > 4.5s 预警 |
| 循环依赖检测 | **< 100ms** | 100个节点的 DAG 检测耗时 | > 500ms |
| Ontology API P95 | **< 200ms** | FastAPI middleware metrics | > 1s |

---

## 10. 验收标准

### 10.1 功能验收

| 优先级 | 验收项 | 通过标准 | 测试方式 |
|--------|--------|----------|----------|
| **P0** | 循环依赖检测 | 创建 A→B→A 的依赖链，编译时返回完整循环路径 | 单元测试 |
| **P0** | Interface 缺失属性 | ObjectType 声明实现 Interface 但缺少必填属性，编译返回 detail 字段 | 单元测试 |
| **P0** | Function 沙箱注入攻击 | 执行 `import os; os.environ` 返回 SecurityError | 安全测试 |
| **P0** | 跨租户编译隔离 | 租户A的编译不影响租户B的 Neo4j 约束 | 集成测试 |
| **P1** | 增量编译正确性 | 修改1个 ObjectType，仅重新编译其下游 | 集成测试 |
| **P1** | 版本回滚 | 回滚后 Neo4j 约束恢复到目标版本状态 | 集成测试 |
| **P1** | 编译失败回滚 | Neo4j 连接失败时 PostgreSQL 数据不被修改 | 故障注入测试 |
| **P1** | SchemaRegistry 缓存失效 | 编译后运行时验证使用新版本 Schema | 集成测试 |
| **P2** | 归档 ObjectType 保护 | 有实例的 ObjectType 不允许硬删除，返回 409 | 单元测试 |
| **P2** | 并发编译互斥 | 同租户同时触发两次编译，第二次返回 423 | 并发测试 |

### 10.2 代码质量验收

| 质量指标 | 目标 | 工具 |
|----------|------|------|
| 编译器核心逻辑单元测试覆盖率 | ≥ 85% | pytest-cov |
| Router 层无业务逻辑（仅 HTTP 转换） | Code Review 100% 通过 | PR 评审 Checklist |
| 所有 Ontology 写操作带 tenant_id 过滤 | 静态分析 0 violation | 自定义 pylint rule |
| Function 代码必须经过沙箱执行 | `grep exec(` 返回 0 条直接调用 | CI lint 检查 |
| API 文档完整性 | 所有端点有描述 + 示例响应 | FastAPI 自动检查 |

---

## 11. 迁移与实施计划

| Sprint | 优先级 | 任务 | 验收里程碑 |
|--------|--------|------|-----------|
| **Sprint 1** | P0 | ① 替换 exec() 为 RestrictedPython 沙箱<br>② 在 Middleware 层强制 tenant_id 注入<br>③ 补充编译失败回滚机制 | 安全红队测试通过 |
| **Sprint 2** | P0 | ① 拆分 ontology_compiler.py 为 dag.py + neo4j_emitter.py + compiler.py<br>② 实现 DAG 循环依赖检测<br>③ 建立 Router/Service/Repository 三层结构 | 循环依赖场景全覆盖 |
| **Sprint 3** | P1 | ① 实现增量编译引擎（incremental.py）<br>② 实现版本管理表 + 回滚接口<br>③ 实现 SchemaRegistry 缓存 | 增量编译 P95 < 1.5s |
| **Sprint 4** | P1 | ① 实现双阶段验证器（static + runtime）<br>② 接入 Alembic 数据库迁移<br>③ 补充 Prometheus 监控指标 | 验证器单测覆盖率 ≥ 85% |
| **Sprint 5** | P2 | ① 评估 gVisor 沙箱部署方案<br>② 补充并发编译互斥锁<br>③ 完善 API 文档与错误码表 | 全模块验收通过 |

---

> **备注**：本文档由产品/架构联合评审，Sprint 排期需结合团队实际情况调整。所有 P0 安全修复应在正式发版前完成，不得上线存在 `exec()` 直接调用的版本。