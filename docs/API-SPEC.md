# Meatapivot API 接口定义（OpenAPI 3.0 + Pydantic v2）

> 本文档定义 PRD v2.0 中 Ontology 语义层与 AIP 智能层的完整 API 规范。包含 Pydantic Schema 与 OpenAPI 端点说明。
> 
> **基础路径**：`https://api.meatapivot.io/api/v1`

---

## 1. Ontology API

**基础路径**：`/api/v1/ontology`

### 1.1 Object Type

#### POST `/ontology/object-types`
创建 Object Type。

**Request Body (ObjectTypeCreate)**:
```python
class ObjectTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r'^[A-Z][a-zA-Z0-9_]*$')
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = Field(default="box", max_length=50)
    properties: List[PropertyDef] = Field(default_factory=list)
    implemented_interfaces: List[UUID] = Field(default_factory=list)
    neo4j_label: Optional[str] = None  # 默认 = name

class PropertyDef(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = None
    type: str = Field(..., pattern=r'^(string|int|float|date|boolean|json)$')
    required: bool = False
    default_value: Optional[Any] = None
    validation: Optional[PropertyValidation] = None
    link_to: Optional[str] = None  # 指向另一个 ObjectType name

class PropertyValidation(BaseModel):
    regex: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    enum: Optional[List[str]] = None
```

**Response 201 (ObjectTypeResponse)**:
```python
class ObjectTypeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str]
    description: Optional[str]
    icon: str
    properties: List[PropertyDef]
    implemented_interfaces: List[UUID]
    neo4j_label: str
    status: str  # draft / active / archived
    version: int
    compile_status: str  # pending / compiled / error
    compile_errors: List[CompileError]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

class CompileError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
```

---

#### GET `/ontology/object-types`
列出 Object Types。

**Query Parameters**:
| 参数 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| status | string | 否 | 过滤状态：draft/active/archived |
| search | string | 否 | 按 name/display_name 模糊搜索 |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，最大 100 |

**Response 200 (PaginatedObjectTypeResponse)**:
```python
class PaginatedObjectTypeResponse(BaseModel):
    items: List[ObjectTypeResponse]
    total: int
    page: int
    page_size: int
    pages: int
```

---

#### GET `/ontology/object-types/{id}`
获取单个 Object Type。

**Path Parameters**:
| 参数 | 类型 | 说明 |
|:-----|:-----|:-----|
| id | UUID | Object Type ID |

**Response 200**: `ObjectTypeResponse`

---

#### PUT `/ontology/object-types/{id}`
更新 Object Type。

**Request Body**: `ObjectTypeUpdate`（字段同 Create，全部可选）

**Response 200**: `ObjectTypeResponse`

---

#### DELETE `/ontology/object-types/{id}`
归档 Object Type（软删除）。

**Response 204**: No Content

---

#### POST `/ontology/object-types/{id}/compile`
编译单个 Object Type。

**Response 200**:
```python
class CompileResult(BaseModel):
    status: str  # compiled / has_errors
    errors: List[CompileError]
    warnings: List[str]
    neo4j_constraints_created: int
    duration_ms: int
```

---

#### POST `/ontology/object-types/{id}/objects`
根据 Object Type 定义创建对象实例。

**Request Body**:
```python
class OntologyObjectCreate(BaseModel):
    object_key: str = Field(..., min_length=1, max_length=255)
    properties: Dict[str, Any] = Field(default_factory=dict)
    # 系统自动校验 properties 是否符合 ObjectType.properties 定义
```

**Response 201 (OntologyObjectResponse)**:
```python
class OntologyObjectResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    object_type_id: UUID
    object_type_name: str
    object_key: str
    properties: Dict[str, Any]
    neo4j_node_id: Optional[str]
    status: str
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
```

---

### 1.2 Link Type

#### POST `/ontology/link-types`
创建 Link Type。

**Request Body (LinkTypeCreate)**:
```python
class LinkTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    source_object_type_id: UUID
    target_object_type_id: UUID
    cardinality: str = Field(default="MANY_TO_ONE", pattern=r'^(ONE_TO_ONE|ONE_TO_MANY|MANY_TO_ONE|MANY_TO_MANY)$')
    neo4j_edge_type: Optional[str] = None  # 默认大写下划线格式
    properties: List[PropertyDef] = Field(default_factory=list)
```

**Response 201 (LinkTypeResponse)**:
```python
class LinkTypeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str]
    source_object_type_id: UUID
    source_object_type_name: str
    target_object_type_id: UUID
    target_object_type_name: str
    cardinality: str
    neo4j_edge_type: str
    status: str
    created_at: datetime
    updated_at: datetime
```

---

#### POST `/ontology/link-types/{id}/links`
创建关系实例。

**Request Body**:
```python
class OntologyLinkCreate(BaseModel):
    source_object_id: UUID
    target_object_id: UUID
    properties: Dict[str, Any] = Field(default_factory=dict)
```

**Response 201 (OntologyLinkResponse)**:
```python
class OntologyLinkResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    link_type_id: UUID
    link_type_name: str
    source_object_id: UUID
    target_object_id: UUID
    properties: Dict[str, Any]
    neo4j_rel_id: Optional[str]
    created_at: datetime
```

---

#### GET `/ontology/objects/{object_id}/graph`
获取对象子图。

**Query Parameters**:
| 参数 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| depth | int | 否 | 遍历深度，默认 2，最大 5 |
| link_types | List[str] | 否 | 过滤特定关系类型 |

**Response 200 (SubgraphResponse)**:
```python
class SubgraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: GraphMetadata

class GraphNode(BaseModel):
    id: str  # neo4j_node_id
    object_id: UUID
    object_type: str
    label: str
    properties: Dict[str, Any]

class GraphEdge(BaseModel):
    id: str  # neo4j_rel_id
    source: str  # node id
    target: str  # node id
    type: str
    properties: Dict[str, Any]

class GraphMetadata(BaseModel):
    center_object_id: UUID
    depth: int
    total_nodes: int
    total_edges: int
    query_time_ms: int
```

---

### 1.3 Interface

#### POST `/ontology/interfaces`
创建 Interface。

**Request Body (InterfaceCreate)**:
```python
class InterfaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    required_properties: List[PropertyDef] = Field(default_factory=list)
    required_links: List[InterfaceLinkRequirement] = Field(default_factory=list)

class InterfaceLinkRequirement(BaseModel):
    name: str
    target_type: str
    cardinality: Optional[str] = "MANY_TO_ONE"
```

**Response 201 (InterfaceResponse)**:
```python
class InterfaceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str]
    required_properties: List[PropertyDef]
    required_links: List[InterfaceLinkRequirement]
    status: str
    created_at: datetime
    updated_at: datetime
```

---

#### GET `/ontology/interfaces/{id}/validate`
校验 Interface 实现。

**Response 200**:
```python
class InterfaceValidationResult(BaseModel):
    interface_id: UUID
    total_implementations: int
    passed: int
    failed: int
    details: List[ImplementationValidation]

class ImplementationValidation(BaseModel):
    object_type_id: UUID
    object_type_name: str
    passed: bool
    missing_properties: List[str]
    missing_links: List[str]
```

---

### 1.4 Action Type

#### POST `/ontology/action-types`
创建 Action Type。

**Request Body (ActionTypeCreate)**:
```python
class ActionTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    target_object_type_id: UUID
    parameters: List[ActionParameter] = Field(default_factory=list)
    modifies_properties: List[str] = Field(default_factory=list)
    modifies_links: List[str] = Field(default_factory=list)
    rules: List[ActionRule] = Field(default_factory=list)
    execution_type: str = Field(default="direct", pattern=r'^(direct|function_backed|workflow)$')
    function_id: Optional[UUID] = None
    workflow_id: Optional[UUID] = None

class ActionParameter(BaseModel):
    name: str
    display_name: Optional[str] = None
    type: str  # string / int / float / date / boolean / object_ref
    object_type_ref: Optional[str] = None  # if type == object_ref
    required: bool = False
    default_value: Optional[Any] = None
    description: Optional[str] = None

class ActionRule(BaseModel):
    name: str
    rule_type: str = Field(..., pattern=r'^(opa|expression)$')
    policy: str  # OPA Rego code or JSON expression
    description: Optional[str] = None
```

**Response 201 (ActionTypeResponse)**:
```python
class ActionTypeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str]
    target_object_type_id: UUID
    target_object_type_name: str
    parameters: List[ActionParameter]
    modifies_properties: List[str]
    modifies_links: List[str]
    rules: List[ActionRule]
    execution_type: str
    function_id: Optional[UUID]
    workflow_id: Optional[UUID]
    status: str
    created_by: Optional[UUID]
    created_at: datetime
```

---

#### POST `/ontology/actions/{id}/execute`
执行 Action。

**Request Body**:
```python
class ActionExecuteRequest(BaseModel):
    target_object_id: Optional[UUID] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    async_execution: bool = False  # True = 返回 execution_id，后台执行
```

**Response 200 (ActionExecuteResponse)**:
```python
class ActionExecuteResponse(BaseModel):
    execution_id: UUID
    status: str  # pending / running / success / failed / timeout
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    rules_evaluation: List[RuleEvaluation]
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

class RuleEvaluation(BaseModel):
    rule_name: str
    passed: bool
    reason: Optional[str] = None
```

---

### 1.5 Function

#### POST `/ontology/functions`
注册 Function。

**Request Body (FunctionCreate)**:
```python
class FunctionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    language: str = Field(default="python", pattern=r'^(python|typescript)$')
    code: str = Field(..., max_length=10000)  # 10KB limit
    read_only: bool = False
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    memory_mb: int = Field(default=256, ge=64, le=1024)
```

**Response 201 (FunctionResponse)**:
```python
class FunctionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str]
    language: str
    code: str
    read_only: bool
    timeout_seconds: int
    memory_mb: int
    current_version: int
    status: str
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
```

---

#### POST `/ontology/functions/{id}/test`
沙箱测试 Function。

**Request Body**:
```python
class FunctionTestRequest(BaseModel):
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)  # mock object data
```

**Response 200**:
```python
class FunctionTestResponse(BaseModel):
    success: bool
    output: Optional[Any] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_ms: int
    memory_peak_mb: Optional[float] = None
```

---

### 1.6 Search & Compile

#### POST `/ontology/search`
语义搜索。

**Request Body (OntologySearchRequest)**:
```python
class OntologySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    object_types: Optional[List[str]] = None
    search_mode: str = Field(default="hybrid", pattern=r'^(vector|graph|hybrid|keyword)$')
    top_k: int = Field(default=20, ge=1, le=100)
    explain: bool = False
```

**Response 200 (OntologySearchResponse)**:
```python
class OntologySearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    total: int
    vector_hits: int
    graph_hits: int
    reranked: bool
    duration_ms: int

class SearchResultItem(BaseModel):
    object_id: UUID
    object_type: str
    object_key: str
    label: str
    score: float
    source: str  # vector / graph / keyword
    explanation: Optional[str] = None  # if explain=True
    properties_preview: Dict[str, Any]
```

---

#### POST `/ontology/compile`
全量编译 Ontology。

**Response 200 (CompileResult)**：同 Object Type 编译结果，但包含全量统计

---

#### GET `/ontology/export`
导出 Ontology。

**Query Parameters**:
| 参数 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| format | string | 否 | yaml / json，默认 yaml |

**Response 200**: 文件下载（`Content-Disposition: attachment`）

---

#### POST `/ontology/import`
导入 Ontology。

**Request**: `multipart/form-data`，字段 `file`

**Query Parameters**:
| 参数 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| conflict_strategy | string | 否 | overwrite / skip / rename，默认 skip |

**Response 200 (OntologyImportResult)**:
```python
class OntologyImportResult(BaseModel):
    imported_object_types: int
    imported_link_types: int
    imported_interfaces: int
    imported_action_types: int
    imported_functions: int
    skipped: int
    errors: List[ImportError]

class ImportError(BaseModel):
    entity_type: str
    entity_name: str
    error: str
```

---

## 2. AIP API

**基础路径**：`/api/v1/aip`

### 2.1 Chat

#### POST `/aip/chat`
通用对话。

**Request Body (ChatRequest)**:
```python
class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None  # 默认使用 tenant 配置
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=2048, ge=1, le=8192)
    stream: bool = False
    tools: Optional[List[ToolDef]] = None

class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r'^(system|user|assistant|tool)$')
    content: str
    name: Optional[str] = None  # for tool messages

class ToolDef(BaseModel):
    type: str = "function"
    function: FunctionToolDef

class FunctionToolDef(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
```

**Response 200 (ChatResponse)**:
```python
class ChatResponse(BaseModel):
    id: str
    model: str
    message: ChatMessage
    usage: TokenUsage
    finish_reason: str

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

---

#### POST `/aip/chat/stream`
流式对话（SSE）。

**Request Body**: 同 `ChatRequest`，`stream` 自动为 `True`

**Response**: `text/event-stream`
```
data: {"chunk": "Hello", "finish_reason": null}
data: {"chunk": " world", "finish_reason": null}
data: {"chunk": "", "finish_reason": "stop", "usage": {...}}
```

---

### 2.2 RAG

#### POST `/aip/rag/query`
本体感知 RAG 查询。

**Request Body (RAGQueryRequest)**:
```python
class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    object_types: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)
    include_sources: bool = True
    include_graph_context: bool = True

class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[RAGSource]
    entities: List[DetectedEntity]
    usage: TokenUsage
    performance: RAGPerformance

class RAGSource(BaseModel):
    source_type: str  # vector / graph / document
    object_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    title: str
    content_snippet: str
    score: float
    metadata: Dict[str, Any]

class DetectedEntity(BaseModel):
    object_type: str
    object_key: str
    confidence: float

class RAGPerformance(BaseModel):
    vector_search_ms: int
    graph_search_ms: int
    rerank_ms: int
    llm_generation_ms: int
    total_ms: int
```

---

### 2.3 Agent

#### POST `/aip/agents/{id}/run`
运行 Agent。

**Request Body (AgentRunRequest)**:
```python
class AgentRunRequest(BaseModel):
    input: str
    session_id: Optional[str] = None  # 为空则创建新会话
    context: Dict[str, Any] = Field(default_factory=dict)
    interruptible: bool = True  # 允许 Human-in-the-loop
```

**Response 202 (AgentRunResponse)**:
```python
class AgentRunResponse(BaseModel):
    session_id: str
    status: str  # running / paused / completed / error
    current_step: Optional[str] = None
    output: Optional[str] = None
    messages: List[AgentMessage]

class AgentMessage(BaseModel):
    step: str
    role: str  # system / agent / user / tool
    content: str
    timestamp: datetime
```

---

#### GET `/aip/agents/{id}/status?session_id={session_id}`
查询 Agent 状态。

**Response 200**: `AgentRunResponse`

---

#### POST `/aip/agents/{id}/interrupt`
中断 Agent（Human-in-the-loop 恢复）。

**Request Body**:
```python
class AgentInterruptRequest(BaseModel):
    session_id: str
    action: str = Field(..., pattern=r'^(resume|cancel|retry)$')
    user_input: Optional[str] = None  # resume 时提供
```

**Response 200**: `AgentRunResponse`

---

## 3. 通用响应规范

### 错误响应

所有错误统一返回：
```python
class ErrorResponse(BaseModel):
    error_code: str          # 机器可读错误码，如 ONTOLOGY_COMPILE_ERROR
    message: str             # 人类可读描述
    details: Optional[Dict[str, Any]] = None
    request_id: str          # 用于追踪的 UUID
    timestamp: datetime
```

**HTTP Status Codes**:
| 状态码 | 场景 |
|:-------|:-----|
| 400 | 请求参数校验失败 |
| 401 | 未认证或 Token 过期 |
| 403 | 无权限（租户隔离或角色不足） |
| 404 | 资源不存在 |
| 409 | 资源冲突（如唯一键重复） |
| 422 | 业务逻辑校验失败（如 Interface 未实现） |
| 429 | 限流触发 |
| 500 | 服务器内部错误 |
| 503 | 依赖服务不可用（降级中） |

### 分页规范

列表接口统一分页参数：
```python
class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: str = Field(default="desc", pattern=r'^(asc|desc)$')
```

分页响应统一：
```python
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_prev: bool
```

---

## 4. WebSocket 事件

### 4.1 Ontology 编译进度

**Endpoint**: `wss://api.meatapivot.io/ws/ontology/compile`

**Message Format**:
```json
{
  "event": "compile_progress",
  "data": {
    "tenant_id": "uuid",
    "compile_id": "uuid",
    "status": "running",
    "progress_percent": 45,
    "current_step": "validating_interfaces",
    "message": "正在校验 Interface 实现..."
  }
}
```

### 4.2 Action 执行进度

**Endpoint**: `wss://api.meatapivot.io/ws/actions/execute`

**Message Format**:
```json
{
  "event": "action_progress",
  "data": {
    "execution_id": "uuid",
    "status": "running",
    "step": "rule_check",
    "message": "OPA 规则校验通过"
  }
}
```

### 4.3 Agent 执行进度

**Endpoint**: `wss://api.meatapivot.io/ws/agents/run`

**Message Format**:
```json
{
  "event": "agent_step",
  "data": {
    "session_id": "uuid",
    "step": "search_knowledge",
    "thought": "用户询问员工张三的部门，我需要先搜索知识图谱",
    "observation": "找到 3 条相关记录",
    "timestamp": "2026-05-04T10:00:00Z"
  }
}
```

---

## 5. 安全与认证

### 5.1 认证方式

所有 API 请求必须在 Header 中携带：
```
Authorization: Bearer <JWT_ACCESS_TOKEN>
X-Tenant-ID: <tenant_uuid>
```

### 5.2 权限矩阵

| 端点 | user | manager | admin |
|:-----|:-----|:--------|:------|
| GET /ontology/object-types | ✅ | ✅ | ✅ |
| POST /ontology/object-types | ❌ | ✅ | ✅ |
| PUT /ontology/object-types/{id} | ❌ | ✅ | ✅ |
| DELETE /ontology/object-types/{id} | ❌ | ❌ | ✅ |
| POST /ontology/compile | ❌ | ✅ | ✅ |
| POST /ontology/actions/{id}/execute | ✅ | ✅ | ✅ |
| POST /ontology/functions/{id}/test | ❌ | ✅ | ✅ |
| POST /aip/chat | ✅ | ✅ | ✅ |
| POST /aip/agents/{id}/run | ✅ | ✅ | ✅ |
| GET /ontology/interfaces/{id}/validate | ❌ | ✅ | ✅ |

---

## 6. 文件索引

| 文件 | 说明 |
|:-----|:-----|
| `backend/app/models/ontology_schemas.py` | Ontology Pydantic Schema |
| `backend/app/models/aip_schemas.py` | AIP Pydantic Schema |
| `backend/app/routers/ontology.py` | Ontology API 路由 |
| `backend/app/routers/aip.py` | AIP API 路由 |
| `docker/postgres/schema.sql` | 数据库 DDL |

---

## 9. v2.3.0 新增端点

> 本节记录 v2.3.0 (2026-06-16) 相对 v2.2.0 的新增端点。旧端点的语义保持不变。

### 9.1 Interface Validation WebSocket (S3-1)

#### WS `/ws/interfaces/{tenant_id}`
长连接。服务端在以下时刻推送 JSON 文本帧：
- 连接建立时，立即回放最近一次报告（若有）
- Interface 创建 / 更新后，Celery 任务完成后推送新报告

**帧格式**：
```json
{
  "status": "completed",
  "tenant_id": "uuid",
  "interfaces_total": 3,
  "interfaces_failed": 1,
  "results": [
    {
      "interface_id": "uuid",
      "interface_name": "string",
      "implementations_total": 4,
      "passed": 3,
      "failed": 1,
      "details": [
        {
          "object_type_id": "uuid",
          "object_type_name": "string",
          "passed": false,
          "missing_properties": ["emp_id"],
          "missing_links": []
        }
      ]
    }
  ],
  "completed_at": "2026-06-16T12:34:56.789Z"
}
```

**退化行为**：当 Redis pub/sub 不可用时，服务端降级为每 5 秒轮询 `interface_validation:latest:{tenant_id}` 键。

### 9.2 Action OPA Policies (S3-2)

#### GET `/ontology/actions/policies`
列出当前加载的 OPA 策略规则。

**Response**:
```json
{
  "rules": [
    {"name": "tenant_isolation", "description": "Rejects actions whose tenant_id does not match the caller's tenant."},
    {"name": "forbidden_parameters", "description": "Disallows dangerous action names..."},
    {"name": "max_parameters", "description": "Rejects actions that pass more than 32 parameters..."}
  ],
  "count": 3
}
```

**OPA 拒绝响应**：`POST /ontology/action-types/{id}/execute` 在 OPA 拒绝时仍返回 200，但 body 里 `success=false`、`message="OPA_REJECTED: <reason>"`，并在 `rule_results` 数组中追加一条 `RuleEvaluation(rule_name="OPA::<rule>", passed=false)`。

### 9.3 LLM Cost Dashboard (S4-1)

#### GET `/aip/llm-cost`
LLM 调用成本聚合。

**Query 参数**：
- `days` (1-90, 默认 30)
- `group_by` ("day" | "hour", 默认 "day")

**Response**:
```json
{
  "tenant_id": "uuid",
  "days": 30,
  "group_by": "day",
  "total_calls": 142,
  "total_tokens": 532000,
  "total_cost_cents": 266,
  "by_model": [
    {"model": "gpt-4o", "call_count": 90, "total_tokens": 400000, "estimated_cost_cents": 200},
    {"model": "claude-3-5-sonnet", "call_count": 52, "total_tokens": 132000, "estimated_cost_cents": 66}
  ],
  "trend": [
    {"bucket": "2026-06-15T00:00", "call_count": 5, "total_tokens": 18000, "estimated_cost_cents": 9}
  ],
  "budget": null,
  "budget_state": "no_budget"
}
```

#### GET `/aip/llm-cost/export`
CSV 下载。Query 参数同 `/aip/llm-cost` 但 `group_by` 不适用。返回 `text/csv`，文件名 `llm-cost-{days}d.csv`。

**CSV 列**：`id, created_at, model, provider, prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, status`

#### GET `/aip/llm-budgets`
返回当前租户的预算，无则 `null`。

#### POST `/aip/llm-budgets`
幂等创建或替换预算。Body:
```json
{
  "monthly_budget_cents": 10000,
  "alert_threshold_percent": 80,
  "model_overrides": {"gpt-4o": 600},
  "notes": "Cap for the next 60 days"
}
```

#### PUT `/aip/llm-budgets`
局部更新。404 if no budget set yet — use POST.

**budget_state 取值**：`ok` (低于阈值)、`warning` (≥alert_threshold)、`exceeded` (≥100%)、`no_budget` (未设置或 cap=0)。

### 9.4 Workshop App Builder (S3-3)

#### POST `/workshop/apps`
创建应用。Body:
```json
{
  "name": "Sales Dashboard",
  "description": "Q3 sales overview",
  "graph": {
    "nodes": [
      {"id": "t1", "type": "table", "position": {"x": 0, "y": 0}, "data": {"label": "Sales Table"}},
      {"id": "c1", "type": "chart", "position": {"x": 200, "y": 0}, "data": {"label": "Revenue Chart"}}
    ],
    "edges": [{"id": "e1", "source": "t1", "target": "c1", "animated": true}],
    "viewport": {"x": 0, "y": 0, "zoom": 1}
  }
}
```

#### GET `/workshop/apps`
分页列表。Query: `page`, `page_size` (1-100), `status` (可选).

#### GET `/workshop/apps/{app_id}`
获取单个应用。

#### PUT `/workshop/apps/{app_id}`
更新（全部或部分字段）。

#### DELETE `/workshop/apps/{app_id}`
删除（204 No Content）。

**节点类型**（S3-3 MVP）：`table`、`chart`、`action`。S3-3.1 计划补 `filter` 和 `link-nav`。

### 9.5 Ontology Search Suggest (S3-4)

#### GET `/ontology/search/suggest`
顶栏自动补全端点。

**Query 参数**：
- `q` (1-100 字符)
- `limit` (1-20, 默认 8)

**Response**:
```json
{
  "query": "emp",
  "suggestions": [
    {"kind": "object_type", "id": "uuid", "label": "Employee", "hint": "员工"},
    {"kind": "document", "id": "uuid", "label": "employee-handbook.pdf", "hint": "PDF"}
  ],
  "count": 2
}
```

---

## 10. v2.4.0 新增端点

> v2.4.0 相对 v2.3.x 的新增端点。S3-3 引入的 `/workshop/apps` CRUD 仍在 9.4 节。

### 10.1 Workshop Runtime Execution (V4-1)

#### POST `/workshop/apps/{app_id}/run`
同步执行一个 Workshop app 一次，返回每节点结果。

**Request Body** (`WorkshopExecutionRequest`):
```json
{
  "node_overrides": {
    "action_1": {"parameters": {"reason": "manual override"}}
  }
}
```

**Response** (`WorkshopExecutionResponse`):
```json
{
  "id": "uuid",
  "app_id": "uuid",
  "tenant_id": "uuid",
  "status": "completed",  // running | completed | partial | failed
  "results": {
    "table_1": {
      "node_id": "table_1",
      "node_type": "table",
      "status": "done",   // pending | running | done | error | skipped
      "output": {"node_id": "table_1", "items": [...], "count": 42},
      "error": null,
      "duration_ms": 23
    },
    "filter_1": {
      "node_id": "filter_1",
      "node_type": "filter",
      "status": "done",
      "output": {"items": [...], "count": 12, "filter": {"field": "status", "operator": "==", "value": "active"}},
      "error": null,
      "duration_ms": 5
    }
  },
  "started_at": "2026-06-18T12:00:00Z",
  "completed_at": "2026-06-18T12:00:00.123Z",
  "duration_ms": 123,
  "error_message": null
}
```

**节点类型 → 输出格式**：
- `table`：`{node_id, object_type_id, items: [...], count}`
- `filter`：`{node_id, items, count, filter: {field, operator, value}}`
- `chart`：`{node_id, group_by, series: [{name, value}], total}`
- `linknav`：`{node_id, link_type_id, link_type_name, target_object_type_id, items, count}`
- `action`：`{node_id, action_type_id, action_type_name, success, message, result, blocked}`

**状态机**：
- `completed` — 所有节点 done
- `partial` — 至少一个 error、至少一个 done
- `failed` — 所有节点 error，或图有环

#### GET `/workshop/apps/{app_id}/executions`
分页列出历史运行。Query: `page`, `page_size` (1-100).

#### GET `/workshop/apps/{app_id}/executions/{execution_id}`
获取单次历史运行完整 per-node 结果。

---

> **版本历史**：
> - v2.4.0 (2026-06-18): 新增 10.x 节（Workshop runtime + executions）
> - v2.3.0 (2026-06-16): 新增 9.1-9.5 节（WS 接口验证、OPA policies、LLM cost、Workshop、Search suggest）
> - v2.0 (2026-05-04): 基于 PRD v2.0 创建，覆盖 Ontology + AIP 全部端点
