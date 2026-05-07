# Meatapivot 开发任务拆分（基于 PRD v2.0）

> 将 PRD v2.0 中的需求拆分为可独立执行、可追踪的开发任务。每条任务含编号、负责人、预估工时、依赖关系及验收标准。

---

## 模块总览

| 模块编号 | 模块名称 | 任务数 | 总估工时 | 优先级 | 已完成 | 进度 |
|:---------|:---------|:-------|:---------|:-------|:-------|:-----|
| ONT | Ontology 语义层 Backend | 12 | 80h | P1 | 2 项 + 7 项部分 | ~50% |
| AIP | AIP 智能层 Backend | 10 | 72h | P1 | 0 项 + 3 项部分 | ~20% |
| APP-F | Apps 应用层 Frontend | 8 | 64h | P2 | 2 项 + 2 项部分 | ~63% |
| FDR | Foundry 数据层 | 6 | 48h | P3 | 0 项 | 0% |
| INF | 基础设施与集成 | 4 | 24h | P1 | 1 项 + 2 项部分 | ~50% |

---

## 模块 ONT：Ontology 语义层 Backend

### ONT-001：Ontology 数据模型（PostgreSQL）✅ 已完成
- **需求来源**：FR-ONT-001, FR-ONT-005, FR-ONT-008, FR-ONT-011, FR-ONT-016, FR-ONT-018
- **任务描述**：
  1. 创建 `backend/app/models/ontology_models.py`，定义 SQLAlchemy 模型：
     - `ObjectType`, `LinkType`, `InterfaceType`, `ActionType`, `FunctionDef`, `ValueType`
  2. 创建 Writeback 模型：`OntologyObject`, `OntologyLink`, `ActionExecutionLog`, `FunctionVersion`, `OntologyCompileLog`
  3. 所有表包含 `tenant_id` 索引，支持多租户隔离
- **验收标准**：
  - `alembic revision --autogenerate` 可自动生成迁移脚本
  - `pytest` 模型单元测试通过（CRUD + 外键约束）
- **预估工时**：12h
- **依赖**：INF-001（PostgreSQL 连接基座）
- **负责人**：Backend Dev A

### ONT-002：Object Type CRUD API ✅ 已完成
- **需求来源**：FR-ONT-001 ~ FR-ONT-004
- **任务描述**：
  1. 创建 `backend/app/routers/ontology/object_types.py`
  2. 实现 POST / GET / PUT / DELETE / LIST 端点
  3. 属性定义使用 JSON Schema 校验（`jsonschema` 库）
  4. Interface 绑定与校验逻辑
- **验收标准**：
  - Postman 集测试全部通过
  - OpenAPI 文档自动生成并包含示例
- **预估工时**：8h
- **依赖**：ONT-001
- **负责人**：Backend Dev A

### ONT-003：Link Type CRUD API + 关系实例管理 🟡 部分完成（Link Type CRUD 就绪，关系实例 Neo4j 写入待端到端验证）
- **需求来源**：FR-ONT-005 ~ FR-ONT-007
- **任务描述**：
  1. 创建 `backend/app/routers/ontology/link_types.py`
  2. 实现 Link Type 定义端点
  3. 实现关系实例创建端点（写入 Neo4j，参数化 Cypher）
  4. 子图查询 API（支持 depth 参数，最大 5）
- **验收标准**：
  - Neo4j 中可查询到创建的关系
  - 子图查询返回结构化 JSON（nodes + edges）
- **预估工时**：8h
- **依赖**：ONT-001, ONT-002
- **负责人**：Backend Dev A

### ONT-004：Interface 管理与校验 🟡 部分完成（CRUD 就绪，异步全量校验 + WebSocket 推送未实现）
- **需求来源**：FR-ONT-008 ~ FR-ONT-010
- **任务描述**：
  1. Interface CRUD 端点
  2. Interface 校验逻辑（属性缺失检测 + 关系缺失检测）
  3. 异步全量校验任务（后台任务队列）
  4. WebSocket 推送校验结果
- **验收标准**：
  - 变更 Interface 后 5 分钟内完成全量重校验
  - WebSocket 客户端可接收到校验结果
- **预估工时**：8h
- **依赖**：ONT-002
- **负责人**：Backend Dev B

### ONT-005：Ontology 编译器服务 🟡 骨架完成（ontology_compiler.py 已创建，待性能验证 + 增量编译）
- **需求来源**：FR-ONT-019 ~ FR-ONT-021
- **任务描述**：
  1. 创建 `backend/app/services/ontology_compiler.py`
  2. 实现全量编译：
     - 校验 Interface 实现
     - 校验 Link 源/目标存在性
     - 生成 Neo4j Constraints
     - 生成 GraphQL Schema（`strawberry-graphql`）
  3. 增量编译（仅变更类型及其依赖）
  4. 编译日志记录
- **验收标准**：
  - 100 个 Object Type 全量编译 < 30s
  - 增量编译 < 3s
  - 编译失败时回滚，不残留部分约束
- **预估工时**：12h
- **依赖**：ONT-002, ONT-003, ONT-004
- **负责人**：Backend Dev B

### ONT-006：Action 执行引擎 🟡 骨架完成（action_executor.py 已创建，direct 模式可用，沙箱 + workflow 待完善）
- **需求来源**：FR-ONT-011 ~ FR-ONT-015
- **任务描述**：
  1. 创建 `backend/app/services/action_executor.py`
  2. 三种执行方式：
     - `direct`：直接修改 PostgreSQL + Neo4j
     - `function_backed`：调用 FunctionDef 代码（进程级沙箱）
     - `workflow`：触发 Decision Flow
  3. OPA Rules 校验集成（`opa-python` 或 HTTP 调用 OPA 服务）
  4. Writeback 记录写入 `action_execution_logs`
  5. 异步执行（Celery / RabbitMQ）
- **验收标准**：
  - Direct Action P99 < 500ms
  - Function-backed Action 超时 30s，内存限制 256MB
  - 所有执行记录可追溯
- **预估工时**：12h
- **依赖**：ONT-005
- **负责人**：Backend Dev B

### ONT-007：Function 管理与沙箱执行 🟡 部分完成（CRUD 就绪，沙箱执行 + 语法预检待完善）
- **需求来源**：FR-ONT-016 ~ FR-ONT-018
- **任务描述**：
  1. Function CRUD 端点
  2. 版本管理（更新自动创建新版本）
  3. 沙箱执行（`subprocess` + `resource` 限制 + timeout）
  4. 语法预检（`ast.parse` 不执行）
- **验收标准**：
  - 恶意代码（如 `os.system('rm -rf /')`）被沙箱拦截
  - 函数异常返回友好错误 + 堆栈
- **预估工时**：8h
- **依赖**：ONT-006
- **负责人**：Backend Dev C

### ONT-008：语义搜索引擎（向量 + 图谱混合）🟡 部分完成（Milvus 向量搜索已接入，RRF 混合重排 + 异步索引更新待完善）
- **需求来源**：FR-ONT-022 ~ FR-ONT-025
- **任务描述**：
  1. 集成 `sentence-transformers`（BGE-M3）生成 Embedding
  2. 集成 Milvus 向量存储与检索
  3. 图谱邻居扩展检索（Neo4j Cypher）
  4. RRF 混合重排算法实现
  5. 异步索引更新（文档/对象变更时触发）
- **验收标准**：
  - 混合检索 P99 < 500ms
  - Top-10 结果可解释（显示来源：向量/图谱）
- **预估工时**：12h
- **依赖**：INF-003（Milvus 部署）
- **负责人**：Backend Dev C / MLOps

### ONT-009：Ontology 导入/导出 🟡 骨架完成（export/import 端点存在，冲突处理策略待完善）
- **需求来源**：FR-ONT-026 ~ FR-ONT-027
- **任务描述**：
  1. YAML/JSON 导出（含全部定义）
  2. YAML/JSON 导入（Schema 校验 + 冲突处理）
  3. 冲突策略：覆盖 / 跳过 / 重命名
- **验收标准**：
  - 导出的 YAML 可人工编辑后重新导入
  - 冲突时前端可交互选择策略
- **预估工时**：6h
- **依赖**：ONT-005
- **负责人**：Backend Dev A

### ONT-010：Ontology 前端管理界面 ✅ 已完成（ObjectType/LinkType/Interface/ActionType/Function 全部支持 CRUD Modal）
- **需求来源**：配合 ONT-002 ~ ONT-004
- **任务描述**：
  1. Object Type 列表/创建/编辑页
  2. Link Type 管理页
  3. Interface 管理页
  4. 编译状态展示页（含错误列表）
- **验收标准**：
  - 与 Backend API 联调通过
  - 支持表单校验与错误提示
- **预估工时**：8h
- **依赖**：ONT-002, ONT-003, ONT-004
- **负责人**：Frontend Dev A

### ONT-011：语义搜索前端界面 ⬜ 未开始
- **需求来源**：配合 ONT-008
- **任务描述**：
  1. 搜索框（支持按 Object Type 过滤）
  2. 结果列表（显示来源标签：向量/图谱）
  3. 结果详情页（跳转 Object View）
- **验收标准**：
  - 搜索延迟 < 1s（前端感知）
  - 空状态与加载状态友好
- **预估工时**：6h
- **依赖**：ONT-008
- **负责人**：Frontend Dev B

### ONT-012：Action 执行前端界面 ⬜ 未开始
- **需求来源**：配合 ONT-006
- **任务描述**：
  1. Action 按钮组件（动态渲染）
  2. Action 参数表单弹窗（根据 ActionType 定义动态生成）
  3. 执行结果反馈（成功/失败 + 原因）
- **验收标准**：
  - 表单字段类型支持：string/number/date/select/boolean
  - 执行中显示 loading，完成后自动刷新 Object View
- **预估工时**：6h
- **依赖**：ONT-006
- **负责人**：Frontend Dev B

---

## 模块 AIP：AIP 智能层 Backend

### AIP-001：LLM Gateway 集成（One API）🟡 部分完成（OpenAI 后端已接入，限流/配额/多后端切换待完善）
- **需求来源**：FR-AIP-001 ~ FR-AIP-004
- **任务描述**：
  1. Docker Compose 添加 `one-api` 服务
  2. 配置多模型后端（OpenAI / Azure / Claude / Ollama）
  3. 创建 `backend/app/services/llm_gateway.py` 封装调用
  4. 限流与配额管理（Redis 计数器）
  5. 调用日志写入 `aip_llm_calls`
- **验收标准**：
  - 支持至少 3 个模型后端切换
  - 限流触发时返回 429 + 重置时间
- **预估工时**：8h
- **依赖**：INF-001, INF-002（Redis）
- **负责人**：Backend Dev C

### AIP-002：RAG Pipeline（本体感知检索）🟡 部分完成（基础 RAG 查询已可用，BGE-Reranker + 实体识别待接入）
- **需求来源**：FR-AIP-005 ~ FR-AIP-009
- **任务描述**：
  1. 集成 `llama-index` + `milvus` 向量存储
  2. 集成 Neo4j 知识图谱索引
  3. 查询时实体识别（小模型或 LLM 提取 Ontology Object Types）
  4. BGE-Reranker-v2-m3 重排
  5. 生成回答时注入 Ontology Schema 上下文
  6. 可解释性输出（来源标注）
- **验收标准**：
  - RAG 查询 P99 < 2s
  - 回答附带 ≥ 3 个来源引用
- **预估工时**：12h
- **依赖**：AIP-001, ONT-008
- **负责人**：Backend Dev C / MLOps

### AIP-003：Agent Orchestrator（LangGraph）⬜ 未开始
- **需求来源**：FR-AIP-010 ~ FR-AIP-012
- **任务描述**：
  1. 集成 `langgraph` + `langchain`
  2. Agent 定义（角色 + 工具集绑定）
  3. 工作流节点：LLM / Action / Search / Human / Condition / End
  4. 多 Agent 协作（顺序/分支/循环）
  5. 会话状态持久化（Redis / PostgreSQL）
- **验收标准**：
  - 支持至少 3 种工作流模式
  - Human-in-the-loop 节点可暂停并等待用户输入
- **预估工时**：12h
- **依赖**：AIP-002
- **负责人**：Backend Dev C / MLOps

### AIP-004：Guardrails 安全校验 ⬜ 未开始（依赖 guardrails-ai，已加入 requirements.txt）
- **需求来源**：FR-AIP-013 ~ FR-AIP-016
- **任务描述**：
  1. 输入校验：Prompt Injection / Toxicity（`guardrails-ai` 或自研规则）
  2. 输出校验：幻觉检测（Ontology 反查数值/实体/时间）
  3. PII 识别与脱敏（`presidio` 或正则 + 实体识别）
  4. 审计日志写入 `aip_guardrails_logs`
- **验收标准**：
  - 已知攻击模式拒绝率 > 95%
  - PII 脱敏后不可逆
- **预估工时**：10h
- **依赖**：AIP-001
- **负责人**：Backend Dev C

### AIP-005：AIP API 端点 🟡 部分完成（chat/chat_stream/rag 已就绪，agents 为占位符，SSE 流式可用）
- **需求来源**：FR-AIP 全部
- **任务描述**：
  1. 创建 `backend/app/routers/aip.py`
  2. 端点：
     - `POST /api/v1/aip/chat`（通用对话）
     - `POST /api/v1/aip/chat/stream`（SSE 流式）
     - `POST /api/v1/aip/rag/query`（RAG 查询）
     - `POST /api/v1/aip/agents/{id}/run`（运行 Agent）
     - `GET /api/v1/aip/agents/{id}/status`（查询状态）
     - `POST /api/v1/aip/agents/{id}/interrupt`（中断）
  3. SSE 流式输出支持
- **验收标准**：
  - 流式输出首 Token < 2s
  - Postman 集测试通过
- **预估工时**：8h
- **依赖**：AIP-001 ~ AIP-004
- **负责人**：Backend Dev C

### AIP-006：LLM 对话前端界面 🟡 部分完成（Chat 界面 + SSE 流式 + 模型选择已完成，对话历史持久化待实现）
- **需求来源**：配合 AIP-005
- **任务描述**：
  1. Chat 界面（类似 ChatGPT，支持 Markdown）
  2. 模型选择器（下拉切换）
  3. 流式输出展示（SSE）
  4. 对话历史（本地存储 / 后端持久化）
- **验收标准**：
  - 流式输出流畅无卡顿
  - 支持代码高亮与复制
- **预估工时**：8h
- **依赖**：AIP-005
- **负责人**：Frontend Dev B

### AIP-007：RAG 查询前端界面 ⬜ 未开始
- **需求来源**：配合 AIP-002
- **任务描述**：
  1. RAG 搜索页（独立或集成到全局搜索）
  2. 答案展示（高亮引用来源）
  3. 来源卡片（点击跳转 Object View 或文档）
  4. 追问功能（上下文继承）
- **预估工时**：6h
- **依赖**：AIP-005, AIP-006
- **负责人**：Frontend Dev B

### AIP-008：Agent 工作流可视化 ⬜ 未开始
- **需求来源**：配合 AIP-003
- **任务描述**：
  1. Agent 执行过程时序图（Step-by-step）
  2. Thought / Action / Observation 展示
  3. Human-in-the-loop 中断/恢复按钮
  4. 支持重新执行某一步
- **预估工时**：8h
- **依赖**：AIP-005, AIP-006
- **负责人**：Frontend Dev B

### AIP-009：Prompt 管理后台 ⬜ 未开始
- **需求来源**：配合 AIP-001
- **任务描述**：
  1. Prompt 模板 CRUD
  2. 版本管理
  3. A/B 测试标记
  4. 使用统计（调用次数、平均 Token）
- **预估工时**：6h
- **依赖**：AIP-005
- **负责人**：Frontend Dev A

### AIP-010：LLM 成本分析仪表盘 ⬜ 未开始
- **需求来源**：配合 AIP-001
- **任务描述**：
  1. 按模型/租户/时间段的 Token 消耗统计
  2. 成本估算（支持自定义单价）
  3. 预算告警阈值配置
- **预估工时**：6h
- **依赖**：AIP-005
- **负责人**：Frontend Dev A

---

## 模块 APP-F：Apps 应用层 Frontend

### APP-001：Object View 对象详情页 ✅ 已完成（接入真实 API，子图可视化保留，支持 Actions）
- **需求来源**：FR-APP-001 ~ FR-APP-005
- **任务描述**：
  1. 路由：`/objects/{object_type}/{object_id}`
  2. 页面结构：
     - 顶部：对象标题 + 类型标签 + 状态
     - 左侧：属性表（PropertyTable 组件）
     - 右侧：关联对象列表（RelatedObjects 组件）
     - 底部：可用 Actions（ActionButton 组件）
  3. 内嵌子图可视化（React Force Graph，2 跳）
- **验收标准**：
  - 页面加载 < 1s（并行请求属性+关系+Actions）
  - 子图支持拖拽、缩放、点击跳转
- **预估工时**：12h
- **依赖**：ONT-003, ONT-012
- **负责人**：Frontend Dev B

### APP-002：PropertyTable 组件 🟡 部分完成（基础渲染 + 编辑模式已就绪，失焦自动保存待实现）
- **需求来源**：配合 APP-001
- **任务描述**：
  1. 按 ObjectType 定义动态渲染属性字段
  2. 支持编辑模式（有权限时）
  3. 字段类型：text / number / date / select / boolean / json
  4. 变更实时保存（乐观更新）
- **验收标准**：
  - 100 个属性字段渲染 < 200ms
  - 编辑后失焦自动保存，失败时回滚并提示
- **预估工时**：6h
- **依赖**：APP-001
- **负责人**：Frontend Dev B

### APP-003：RelatedObjects 组件 🟡 部分完成（按 Link Type 分组展示已就绪，增删关系待实现）
- **需求来源**：配合 APP-001
- **任务描述**：
  1. 按 Link Type 分组展示关联对象
  2. 每组显示：关系名称 + 对象数量 + 展开列表
  3. 点击对象跳转其 Object View
  4. 支持添加/删除关系（有权限时）
- **验收标准**：
  - 展开动画流畅
  - 关系变更后实时刷新
- **预估工时**：6h
- **依赖**：APP-001
- **负责人**：Frontend Dev B

### APP-004：ActionButton + ActionDialog 组件 ⬜ 未开始
- **需求来源**：配合 ONT-012
- **任务描述**：
  1. ActionButton：动态渲染，根据权限显示/禁用
  2. ActionDialog：根据 ActionType.parameters 动态生成表单
  3. 表单字段支持校验（required, regex, min/max）
  4. 提交后显示进度与结果
- **验收标准**：
  - 表单生成时间 < 100ms
  - 执行失败时显示后端返回的明确错误
- **预估工时**：8h
- **依赖**：ONT-012
- **负责人**：Frontend Dev B

### APP-005：Workshop App Builder（XYFlow 扩展）⬜ 未开始
- **需求来源**：FR-APP-006 ~ FR-APP-008
- **任务描述**：
  1. 左侧组件面板：Object Table / Filter / Chart / Action Button / Link Navigator
  2. 画布拖拽布局（基于 XYFlow）
  3. 组件属性配置面板（右侧）
  4. 组件间数据联动（Filter → Table → Chart）
  5. 应用发布与权限分配
- **验收标准**：
  - 拖拽体验流畅（60fps）
  - 发布的应用可被其他用户访问
- **预估工时**：16h
- **依赖**：APP-001 ~ APP-004
- **负责人**：Frontend Dev A + Frontend Dev B

### APP-006：Ontology 管理后台导航与布局 ✅ 已完成（Layout.tsx 导航 + 路由已就绪，权限控制待完善）
- **需求来源**：配合 ONT-010
- **任务描述**：
  1. 侧边栏新增 "Ontology" 菜单组
  2. 子菜单：Object Types / Link Types / Interfaces / Actions / Functions / Compile Status
  3. 面包屑导航
  4. 权限控制（仅 admin / ontology_manager 可见）
- **验收标准**：
  - 无权限用户无法通过 URL 直接访问管理页
- **预估工时**：4h
- **依赖**：ONT-010
- **负责人**：Frontend Dev A

### APP-007：全局搜索升级（集成语义搜索）⬜ 未开始
- **需求来源**：配合 ONT-008, AIP-002
- **任务描述**：
  1. 搜索框支持模式切换：Keyword / Semantic / RAG
  2. 结果分类展示：Objects / Documents / LLM Answer
  3. 搜索建议（Autocomplete）
  4. 搜索历史（本地存储）
- **验收标准**：
  - 搜索结果页加载 < 1s
  - 支持键盘导航（↑↓ Enter）
- **预估工时**：6h
- **依赖**：ONT-011, AIP-007
- **负责人**：Frontend Dev A

### APP-008：仪表盘首页升级 ⬜ 未开始
- **需求来源**：综合
- **任务描述**：
  1. Ontology 统计卡片（Object Type 数 / 实例数 / Action 执行数）
  2. 最近执行的 Action 列表
  3. 热门搜索词云
  4. LLM 调用成本趋势图
- **验收标准**：
  - 页面加载 < 1.5s
  - 数据自动刷新（30s 间隔）
- **预估工时**：6h
- **依赖**：AIP-010
- **负责人**：Frontend Dev A

---

## 模块 FDR：Foundry 数据层

### FDR-001：SeaTunnel 集成（数据管道）⬜ 未开始
- **需求来源**：FR-FDR-001 ~ FR-FDR-003
- **任务描述**：
  1. Docker Compose 添加 `seatunnel` 服务
  2. 基础配置文件模板（MySQL → PostgreSQL, CSV → Neo4j）
  3. 管道运行状态查询 API（读取 SeaTunnel 日志）
  4. 异常告警（RabbitMQ 通知）
- **验收标准**：
  - 至少完成 MySQL → PostgreSQL 的全量同步验证
  - 异常时 1 分钟内触发告警
- **预估工时**：10h
- **依赖**：INF-001
- **负责人**：Data Engineer

### FDR-002：可视化管道配置器（Frontend）⬜ 未开始
- **需求来源**：配合 FDR-001
- **任务描述**：
  1. 表单化配置 Source（数据库连接 / 文件路径）
  2. 表单化配置 Transform（字段映射 / 过滤 / 类型转换）
  3. 表单化配置 Sink（目标表 / 对象类型）
  4. 自动生成 SeaTunnel conf 文件
  5. 测试连接与预览前 10 条数据
- **验收标准**：
  - 生成的 conf 文件可直接被 SeaTunnel 执行
  - 预览数据与源端一致
- **预估工时**：8h
- **依赖**：FDR-001
- **负责人**：Frontend Dev A

### FDR-003：CDC 实时同步（Debezium）⬜ 未开始
- **需求来源**：FR-FDR-004 ~ FR-FDR-005
- **任务描述**：
  1. Docker Compose 添加 `debezium` 服务
  2. 配置 PostgreSQL / MySQL connector
  3. 变更事件消费 → 转换规则 → Ontology Object 更新
  4. 延迟监控（Prometheus metrics）
- **验收标准**：
  - 端到端延迟 < 5s
  - 不丢失变更事件（至少一次交付）
- **预估工时**：10h
- **依赖**：FDR-001
- **负责人**：Data Engineer

### FDR-004：数据血缘（Apache Atlas）⬜ 未开始
- **需求来源**：FR-FDR-006 ~ FR-FDR-007
- **任务描述**：
  1. Docker Compose 添加 `atlas` 服务
  2. 元数据采集钩子（PostgreSQL / Neo4j / MinIO）
  3. 血缘查询 API（从源到 App 的全链路）
  4. 前端血缘图谱可视化
- **验收标准**：
  - 可查询任意 Ontology Object 的数据来源链路
  - 血缘图谱支持 5 层以上展开
- **预估工时**：12h
- **依赖**：FDR-001, FDR-003
- **负责人**：Data Engineer

### FDR-005：数据质量检查 ⬜ 未开始
- **需求来源**：PRD 隐含
- **任务描述**：
  1. 定义数据质量规则（空值率 / 唯一性 / 格式 / 范围）
  2. 定时执行检查（DolphinScheduler 或 cron）
  3. 质量评分与告警
- **预估工时**：4h
- **依赖**：FDR-001
- **负责人**：Data Engineer

### FDR-006：数据目录（Data Catalog）⬜ 未开始
- **需求来源**：PRD 隐含
- **任务描述**：
  1. 数据源注册与管理
  2. 表/字段级元数据浏览
  3. 与 Ontology Object Type 的映射关系
- **预估工时**：4h
- **依赖**：FDR-004
- **负责人**：Data Engineer + Frontend Dev A

---

## 模块 INF：基础设施与集成

### INF-001：PostgreSQL 连接基座升级 🟡 部分完成（asyncpg + Alembic 基线就绪，多租户连接池隔离待实现）
- **任务描述**：
  1. 确认 `asyncpg` 已加入 `requirements.txt`
  2. 补充 Alembic 迁移基线
  3. 多租户连接池隔离（按 tenant_id 路由）
- **验收标准**：
  - `alembic upgrade head` 成功执行
  - 连接池配置支持 ≥ 100 并发
- **预估工时**：4h
- **依赖**：无
- **负责人**：Backend Dev A

### INF-002：Redis 集成加固 🟡 部分完成（redis_client.py 已创建，Rate Limiting + Session + 降级策略待完善）
- **任务描述**：
  1. 确认 Redis 已在 docker-compose 中启用
  2. 后端集成 `redis-py` 用于：
     - Rate Limiting（slowapi backend）
     - Session / Cache
     - LLM 配额计数
  3. 降级策略（Redis 不可用时回退内存）
- **验收标准**：
  - Redis 故障时系统仍可运行（降级模式）
- **预估工时**：4h
- **依赖**：无
- **负责人**：Backend Dev A

### INF-003：Milvus 向量数据库部署 ✅ 已完成（docker-compose 服务栈 + MilvusClient 封装 + Collection Schema 就绪）
- **任务描述**：
  1. Docker Compose 添加 `milvus` + `etcd` + `minio`（Milvus 专用）
  2. 创建 Collection Schema（`tenant_id` + `embedding` + `metadata`）
  3. 后端封装 `MilvusClient`
- **验收标准**：
  - Milvus 可独立启动，与现有 MinIO 不冲突
  - 向量写入/查询延迟 < 100ms
- **预估工时**：8h
- **依赖**：无
- **负责人**：Backend Dev C / MLOps

### INF-004：CI/CD 流水线更新 ⬜ 未开始
- **任务描述**：
  1. GitHub Actions 添加：
     - SAST 扫描（bandit + semgrep）
     - 单元测试（pytest）
     - 构建镜像并推送 GHCR
  2. 添加 `docker-compose.test.yml`（TestContainers）
- **验收标准**：
  - PR 提交时自动触发检查
  - 无高危漏洞方可合并
- **预估工时**：8h
- **依赖**：无
- **负责人**：DevOps

---

## 任务依赖图

```
Week 1-2:
  INF-001, INF-002, INF-003  →  ONT-001

Week 3-4:
  ONT-001  →  ONT-002, ONT-003
  ONT-002  →  ONT-004

Week 5-6:
  ONT-003, ONT-004  →  ONT-005
  ONT-005  →  ONT-006

Week 7-8:
  ONT-006  →  ONT-007
  INF-003  →  ONT-008
  ONT-008  →  ONT-011
  ONT-002  →  ONT-010
  AIP-001  →  AIP-005
  AIP-005  →  AIP-006, AIP-007

Week 9-10:
  ONT-010, ONT-012  →  APP-001
  APP-001  →  APP-002, APP-003, APP-004
  APP-001~004  →  APP-005

Week 11-12:
  AIP-002  →  AIP-003
  AIP-003  →  AIP-008
  AIP-001  →  AIP-004

Week 13-14:
  FDR-001  →  FDR-003, FDR-005
  FDR-003  →  FDR-004
  FDR-004  →  FDR-006

Week 15-16:
  INF-004  →  All Modules Integration Test
  All  →  Performance Tuning + Documentation
```

---

## 人员分配建议

| 角色 | 人数 | 负责模块 | 核心技能 |
|:-----|:-----|:---------|:---------|
| Backend Dev A | 1 | ONT-001~004, ONT-009, INF-001~002 | FastAPI, SQLAlchemy, PostgreSQL |
| Backend Dev B | 1 | ONT-005~006, ONT-010~012 | Neo4j, GraphQL, Asyncio |
| Backend Dev C | 1 | ONT-007~008, AIP-001~005, INF-003 | LLM, RAG, LangChain, Vector DB |
| Frontend Dev A | 1 | APP-006~008, AIP-009~010, FDR-002, FDR-006 | React, TypeScript, Dashboard |
| Frontend Dev B | 1 | APP-001~005, AIP-006~008 | React, Visualization, XYFlow |
| MLOps / AI | 1 | AIP-002~004, ONT-008 | Embedding, Milvus, LLM Ops |
| Data Engineer | 1 | FDR-001, FDR-003~006 | SeaTunnel, Debezium, Atlas |
| DevOps | 1 | INF-004, 全环境维护 | Docker, K8s, CI/CD, Observability |

**总计**：8 人 × 16 周 = 128 人周

---

## 关键里程碑

| 里程碑 | 日期 | 交付物 | 验收方式 | 当前状态 |
|:-------|:-----|:-------|:---------|:---------|
| M1：模型就绪 | Week 2 | Ontology 全部表 + Alembic 迁移 | `pytest` 通过 | ✅ 已完成 |
| M2：API 就绪 | Week 4 | Object/Link/Interface CRUD API | Postman 集通过 | 🟡 进行中 |
| M3：引擎就绪 | Week 6 | Compiler + Action Executor | 100 Object 编译 < 30s | 🟡 进行中 |
| M4：搜索就绪 | Week 8 | Semantic Search + LLM Gateway | 混合检索 P99 < 500ms | 🟡 进行中 |
| M5：前端就绪 | Week 10 | Object View + Workshop Builder | E2E 测试通过 | 🟡 进行中 |
| M6：智能就绪 | Week 12 | RAG + Agent + Guardrails | 演示通过 | ⬜ 未开始 |
| M7：数据就绪 | Week 14 | CDC + Lineage | 端到端延迟 < 5s | ⬜ 未开始 |
| M8：发布就绪 | Week 16 | v2.0 Release | 集成测试 + 文档齐全 | ⬜ 未开始 |

---

> **维护**：本任务清单随迭代进度每周更新。任务完成后在对应行标记 ✅ 并记录实际工时。
