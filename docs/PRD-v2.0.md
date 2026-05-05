# Meatapivot 项目需求文档（PRD）v2.0

> **目标**：基于 Palantir 五层架构模型，补齐 Meatapivot 在 Ontology 语义层、AIP 智能层、Apps 应用层及 Foundry 数据层的核心能力，使其成为可落地的企业级开源知识决策平台。
> 
> **版本**：2.0  
> **日期**：2026-05-04  
> **状态**：需求冻结，待开发评审

---

## 1. 项目背景与目标

### 1.1 现状差距

| Palantir 五层 | Meatapivot 现状 | 完成度 | 优先级 |
|:-------------|:---------------|:------|:------|
| **Platform**（基础设施） | Keycloak + 多租户 + Grafana 全家桶 | 80% | P4 |
| **Foundry**（数据工程） | MinIO 文件上传 | 10% | P3 |
| **Ontology**（语义层） | Neo4j 图 CRUD | 15% | **P1** |
| **Apps**（应用层） | 基础 Recharts 仪表盘 | 30% | P2 |
| **AIP**（AI 平台） | 完全缺失 | 0% | **P1** |

### 1.2 总体目标

1. **构建 Ontology 语义建模层**：支持 Object Type、Link Type、Interface、Action、Function 的定义、编译与执行，实现从"图数据"到"业务语义"的跃迁。
2. **构建 AIP 智能层**：集成 LLM Gateway、RAG Pipeline、Agent Orchestrator，让平台具备自然语言交互与智能决策能力。
3. **构建 Apps 应用层**：提供 Object View 对象浏览器与 Workshop-like 可视化应用构建器，降低业务用户的使用门槛。
4. **补齐 Foundry 数据层**：引入数据集成管道（SeaTunnel）、CDC 实时同步、数据血缘追踪，打通企业数据孤岛。

---

## 2. 需求范围

### 2.1 本次迭代范围（Phase 1：Week 1-8）

**Phase 1 聚焦 P1 需求——Ontology 语义层 + AIP 基础能力**，确保平台的核心差异化能力先落地。

- ✅ Ontology 数据模型与 CRUD API
- ✅ Ontology 编译器（编译至 Neo4j + GraphQL Schema）
- ✅ Action 执行引擎（含 Rules 校验 + Writeback）
- ✅ 语义搜索引擎（向量 + 图谱混合检索）
- ✅ AIP LLM Gateway（One API 集成）
- ✅ AIP RAG Pipeline（本体感知检索）
- ✅ 前端 Object View 页面

### 2.2 后续迭代范围（Phase 2：Week 9-16）

- Workshop-like 应用构建器
- Agent Orchestrator（LangGraph）
- Guardrails（输入/输出校验 + PII 脱敏）
- Foundry 数据管道（SeaTunnel + Debezium）
- 数据血缘（Apache Atlas）
- 审计日志与合规增强

---

## 3. 功能需求

### 3.1 Ontology 语义层（P1）

#### 3.1.1 Object Type 管理（FR-ONT-001 ~ FR-ONT-004）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-ONT-001 | 支持创建 Object Type，定义其属性（JSON Schema）、图标、状态 | API 返回 201，数据持久化至 PostgreSQL，属性支持 string/int/float/date/boolean 及自定义 Value Type |
| FR-ONT-002 | 支持列出、查询、更新、归档 Object Type | 支持按 tenant_id 过滤，支持分页，更新时自动记录版本历史 |
| FR-ONT-003 | Object Type 支持实现 Interface | 创建/更新时可绑定多个 Interface，系统校验属性是否满足 Interface 契约 |
| FR-ONT-004 | Object Type 编译后自动生成 Neo4j Constraints | 编译时根据 Object Type 的唯一属性创建 Neo4j `CREATE CONSTRAINT`，编译失败返回详细错误列表 |

#### 3.1.2 Link Type 管理（FR-ONT-005 ~ FR-ONT-007）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-ONT-005 | 支持创建 Link Type，定义源/目标 Object Type、基数（1:1/1:N/N:M） | 系统校验源/目标 Object Type 必须存在，Neo4j 边类型命名唯一 |
| FR-ONT-006 | 支持基于 Link Type 在 Neo4j 中创建关系实例 | API 接收 source_id + target_id，在 Neo4j 中执行参数化 Cypher，返回关系 RID |
| FR-ONT-007 | 支持查询某对象的关联子图（多跳） | 支持 depth 参数（默认 2，最大 5），返回节点+边的结构化数据供前端可视化 |

#### 3.1.3 Interface 管理（FR-ONT-008 ~ FR-ONT-010）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-ONT-008 | 支持创建 Interface，定义必须实现的属性列表和必须实现的关系列表 | 属性列表支持类型校验，关系列表支持源/目标 Object Type 约束 |
| FR-ONT-009 | 支持校验 Object Type 是否完整实现 Interface | 校验接口返回布尔值+缺失项列表，异步校验任务支持进度查询 |
| FR-ONT-010 | Interface 变更时，自动触发所有实现者的重新校验 | 变更后 5 分钟内完成全部校验，结果通过 WebSocket 推送 |

#### 3.1.4 Action Type & 执行引擎（FR-ONT-011 ~ FR-ONT-015）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-ONT-011 | 支持创建 Action Type，定义参数、修改的属性/关系、前置规则 | 规则字段支持 OPA Rego 或简单 JSON 表达式，执行方式支持 direct/function_backed/workflow |
| FR-ONT-012 | Action 执行前必须经过 Rules 校验 | OPA 校验平均延迟 < 100ms，拒绝时返回明确原因与触发规则 |
| FR-ONT-013 | 支持 Direct Action（直接修改属性/关系） | 执行后立即写回 PostgreSQL + Neo4j，事务一致性 |
| FR-ONT-014 | 支持 Function-backed Action（调用自定义函数） | 函数代码支持 Python/TypeScript，运行在沙箱环境（超时 30s，内存 256MB） |
| FR-ONT-015 | 所有 Action 执行记录写入 Writeback 表 + 审计日志 | Writeback 表支持按 tenant_id + object_id + action_type 查询，审计日志不可篡改 |

#### 3.1.5 Function 管理（FR-ONT-016 ~ FR-ONT-018）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-ONT-016 | 支持注册自定义函数，指定语言与源代码 | 代码长度限制 10KB，支持语法预检（不执行） |
| FR-ONT-017 | 支持沙箱测试函数执行 | 测试环境隔离，输入/输出 JSON 序列化，异常捕获并返回堆栈 |
| FR-ONT-018 | 函数支持版本管理 | 更新函数时自动创建新版本，Action 可绑定特定版本 |

#### 3.1.6 Ontology 编译器（FR-ONT-019 ~ FR-ONT-021）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-ONT-019 | 支持全量编译租户 Ontology | 编译过程原子化，失败时回滚，输出 Neo4j Constraints + GraphQL Schema |
| FR-ONT-020 | 编译时校验 Interface 实现完整性 | 缺失实现时标记为 error，不影响其他合法类型的编译 |
| FR-ONT-021 | 支持增量编译（单个 Object Type） | 仅重新编译变更类型及其依赖，耗时 < 3s |

#### 3.1.7 语义搜索引擎（FR-ONT-022 ~ FR-ONT-025）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-ONT-022 | 支持对 Ontology 对象进行向量化（Embedding） | 使用 BGE-M3 模型，向量维度 1024，存储至 Milvus，支持增量更新 |
| FR-ONT-023 | 支持向量语义检索（Milvus） | 检索延迟 < 200ms，支持按 Object Type 过滤，支持余弦相似度阈值 |
| FR-ONT-024 | 支持图谱邻居扩展检索（Neo4j） | 基于关键词模糊匹配 + 关系遍历，返回带路径的子图 |
| FR-ONT-025 | 支持 RRF 混合重排 | 向量结果与图谱结果融合，Top-10 重排后返回，支持 explain（显示来源） |

#### 3.1.8 导入/导出（FR-ONT-026 ~ FR-ONT-027）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-ONT-026 | 支持导出 Ontology 定义为 YAML/JSON | 导出包含全部 Object/Link/Interface/Action/Function 定义，格式可人工编辑 |
| FR-ONT-027 | 支持从 YAML/JSON 导入 Ontology 定义 | 导入时自动校验 Schema，冲突时提示并支持覆盖/跳过/重命名策略 |

---

### 3.2 AIP 智能层（P1）

#### 3.2.1 LLM Gateway（FR-AIP-001 ~ FR-AIP-004）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-AIP-001 | 集成 One API 作为统一 LLM 网关 | 支持 OpenAI / Azure / Claude / 本地模型（Ollama）等多后端切换 |
| FR-AIP-002 | 支持模型路由（按场景/成本/延迟自动选择） | 配置化路由规则，优先级：成本 < 延迟 < 质量，支持 fallback |
| FR-AIP-003 | 支持限流与配额管理 | 按 tenant + user 维度限流，支持 Token 级计费统计 |
| FR-AIP-004 | 支持调用日志与成本分析 | 日志保留 30 天，支持按模型/租户/时间段聚合成本报表 |

#### 3.2.2 RAG Pipeline（FR-AIP-005 ~ FR-AIP-009）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-AIP-005 | 构建本体感知 RAG 引擎（LlamaIndex） | 同时检索向量索引（Milvus）和知识图谱索引（Neo4j），检索结果带来源标注 |
| FR-AIP-006 | 查询时自动提取 Ontology Entity Context | LLM 从查询中识别涉及的 Object Types，用于过滤检索范围，准确率 > 80% |
| FR-AIP-007 | 检索结果融合与重排序（BGE-Reranker） | 混合检索后使用 BGE-Reranker-v2-m3 重排，Top-5 准确率提升 > 15% |
| FR-AIP-008 | 生成回答时注入 Ontology Schema 上下文 | 系统提示词自动附加相关 Object Type 的属性定义与关系约束 |
| FR-AIP-009 | 支持 RAG 结果的可解释性（Explainability） | 返回每个来源的相似度分数、图谱路径、引用文档片段 |

#### 3.2.3 Agent Orchestrator（FR-AIP-010 ~ FR-AIP-012）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-AIP-010 | 支持定义 Agent 角色与工具集 | Agent 可绑定 Ontology Action、Function、Search、LLM 等工具 |
| FR-AIP-011 | 支持多 Agent 协作工作流（LangGraph） | 支持顺序、分支、循环、人机协同（Human-in-the-loop）节点 |
| FR-AIP-012 | Agent 执行过程可视化 | 前端展示 Agent 每一步的 Thought/Action/Observation，支持中断与恢复 |

#### 3.2.4 Guardrails（FR-AIP-013 ~ FR-AIP-016）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-AIP-013 | 输入内容安全校验（Prompt Injection / Toxicity） | 集成 Guardrails AI，拒绝率 > 95% 的已知攻击模式 |
| FR-AIP-014 | 输出内容安全校验（幻觉检测 / 事实核查） | 对数值型/时间型/实体型输出进行 Ontology 反查，不一致时标红提示 |
| FR-AIP-015 | PII 敏感信息识别与脱敏 | 支持身份证号、手机号、邮箱、银行卡等实体的自动识别与掩码替换 |
| FR-AIP-016 | 审计日志记录所有 LLM 交互 | 记录完整 prompt/response/token 消耗，支持按合规要求导出 |

---

### 3.3 Apps 应用层（P2）

#### 3.3.1 Object View（FR-APP-001 ~ FR-APP-005）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-APP-001 | 对象详情页展示属性表（Property Table） | 按 Object Type 定义动态渲染属性，支持编辑（有权限时） |
| FR-APP-002 | 对象详情页展示关联对象（Related Objects） | 按 Link Type 分组展示，支持展开/折叠，点击跳转 |
| FR-APP-003 | 对象详情页展示可用 Actions | 动态渲染当前用户有权限执行的 Action 按钮，点击弹出参数表单 |
| FR-APP-004 | 对象详情页内嵌子图可视化 | 使用 React Force Graph 展示以当前对象为中心的 2 跳子图，支持拖拽/缩放 |
| FR-APP-005 | Object View 支持 URL 直接访问 | 路由格式 `/objects/{object_type}/{object_id}`，支持分享与收藏 |

#### 3.3.2 Workshop App Builder（FR-APP-006 ~ FR-APP-008）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-APP-006 | 拖拽式应用构建器（基于 XYFlow） | 左侧组件面板（Object Table / Filter / Chart / Action Button / Link Navigator），画布拖拽布局 |
| FR-APP-007 | 组件自动绑定 Ontology 数据 | 拖拽 Object Type 后自动生成默认查询，组件间支持数据联动（如 Filter → Table → Chart） |
| FR-APP-008 | 应用支持发布与权限分配 | 发布后的应用可被指定租户/角色访问，支持版本管理与回滚 |

---

### 3.4 Foundry 数据层（P3）

#### 3.4.1 数据集成管道（FR-FDR-001 ~ FR-FDR-003）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-FDR-001 | 集成 SeaTunnel 作为数据集成引擎 | 支持 MySQL/PostgreSQL/Oracle/MongoDB/Kafka → PostgreSQL/Neo4j 的数据同步 |
| FR-FDR-002 | 支持可视化管道配置（YAML 生成器） | 前端表单配置源/目标/转换规则，自动生成 SeaTunnel conf 文件 |
| FR-FDR-003 | 支持管道运行监控与告警 | 展示同步速率、延迟、错误数，异常时通过 RabbitMQ 发送告警通知 |

#### 3.4.2 CDC 实时同步（FR-FDR-004 ~ FR-FDR-005）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-FDR-004 | 集成 Debezium 实现 CDC 实时捕获 | 支持 MySQL/PostgreSQL binlog 捕获，延迟 < 5s |
| FR-FDR-005 | CDC 事件自动转换为 Ontology 对象变更 | 捕获的变更经转换规则映射为 Object/Link 的创建/更新/删除，写入 Neo4j |

#### 3.4.3 数据血缘（FR-FDR-006 ~ FR-FDR-007）

| 需求编号 | 需求描述 | 验收标准 |
|:---------|:---------|:---------|
| FR-FDR-006 | 集成 Apache Atlas 作为元数据中心 | 自动采集 PostgreSQL/Neo4j/MinIO 的元数据，支持按租户隔离 |
| FR-FDR-007 | 支持端到端数据血缘查询 | 从原始数据源 → ETL 管道 → Ontology Object → App 的全链路追溯 |

---

## 4. 非功能需求（NFR）

| 需求编号 | 类别 | 需求描述 | 指标 |
|:---------|:-----|:---------|:-----|
| NFR-001 | 性能 | Ontology 编译器全量编译耗时 | < 30s（100 个 Object Type） |
| NFR-002 | 性能 | Action 执行延迟（Direct） | P99 < 500ms |
| NFR-003 | 性能 | 语义搜索延迟（混合检索+重排） | P99 < 500ms |
| NFR-004 | 性能 | LLM Gateway 首 Token 延迟 | P99 < 2s（国内模型）/ < 5s（海外模型） |
| NFR-005 | 可用性 | 平台整体可用性 | > 99.9%（单实例），支持降级启动 |
| NFR-006 | 安全 | 所有数据库查询参数化 | 0 Cypher/SQL 注入漏洞 |
| NFR-007 | 安全 | 敏感数据加密存储 | AES-256-GCM，密钥通过环境变量注入 |
| NFR-008 | 扩展性 | 新 Object Type 上线无需代码发布 | 纯配置化，编译后即时生效 |
| NFR-009 | 可观测性 | 全链路追踪覆盖率 | 100% API 调用，100% Action 执行，100% LLM 调用 |
| NFR-010 | 合规 | 审计日志保留期 | ≥ 180 天，支持导出为 CSV/JSON |

---

## 5. 技术方案概要

### 5.1 新增服务清单

| 服务 | 技术选型 | 用途 | 端口 |
|:-----|:---------|:-----|:-----|
| Ontology Compiler | Python (FastAPI) | 本体编译与校验 | 8000（复用后端） |
| Action Executor | Python + OPA | Action 执行与规则校验 | 8000（复用后端） |
| Semantic Search | Python + BGE-M3 | Embedding + 混合检索 | 8000（复用后端） |
| LLM Gateway | One API | 多模型统一接入 | 3005 |
| Vector DB | Milvus v2.4 | 向量存储与检索 | 19530 |
| Agent Orchestrator | Python + LangGraph | 多 Agent 工作流 | 8000（复用后端） |
| RAG Engine | LlamaIndex | 本体感知检索 | 8000（复用后端） |
| Data Integration | SeaTunnel 2.3.8 | 数据管道 | — |
| CDC | Debezium 2.5 | 实时变更捕获 | — |
| Data Lineage | Apache Atlas 2.3 | 元数据与血缘 | 21000 |

### 5.2 关键架构决策

1. **Ontology 定义存储在 PostgreSQL，实例存储在 Neo4j** —— 定义层需要复杂事务与版本控制，实例层需要图遍历性能。
2. **Milvus 作为独立向量库，不与 Neo4j 图向量混用** —— Milvus 在十亿级向量检索上有明显优势，Neo4j 仅保留图遍历。
3. **LLM Gateway 独立部署（One API）** —— 解耦模型管理与业务逻辑，支持热切换模型后端。
4. **Action 执行采用异步 + Writeback 模式** —— Function-backed Action 可能耗时较长，异步执行避免阻塞 API。
5. **沙箱使用 Firecracker / gVisor（后期）** —— Phase 1 先用进程级隔离（subprocess + timeout），Phase 2 升级为轻量级 VM 隔离。

---

## 6. 数据模型概要

### 6.1 Ontology 核心表（PostgreSQL）

```
otology_object_types      -- Object Type 定义
ontology_link_types        -- Link Type 定义
ontology_interfaces        -- Interface 定义
ontology_action_types      -- Action Type 定义
ontology_functions         -- Function 定义
ontology_value_types       -- Value Type 定义
ontology_objects           -- 对象实例（Writeback）
ontology_links             -- 关系实例（Writeback）
ontology_compile_logs      -- 编译历史与错误
action_execution_logs      -- Action 执行记录
function_versions          -- Function 版本历史
```

### 6.2 AIP 核心表（PostgreSQL）

```
aip_llm_calls              -- LLM 调用日志
aip_agent_sessions         -- Agent 会话上下文
aip_rag_queries            -- RAG 查询记录
aip_guardrails_logs        -- Guardrails 校验记录
```

---

## 7. API 设计概要

### 7.1 Ontology API（前缀 `/api/v1/ontology`）

```
POST   /object-types              # 创建 Object Type
GET    /object-types              # 列出 Object Type
PUT    /object-types/{id}         # 更新 Object Type
DELETE /object-types/{id}         # 归档 Object Type
POST   /object-types/{id}/compile # 编译 Object Type

POST   /link-types                # 创建 Link Type
GET    /link-types                # 列出 Link Type

POST   /interfaces                # 创建 Interface
GET    /interfaces/{id}/validate  # 校验 Interface 实现

POST   /action-types              # 创建 Action Type
POST   /actions/{id}/execute      # 执行 Action

POST   /functions                 # 注册 Function
POST   /functions/{id}/test       # 测试 Function

POST   /search                    # 语义搜索
POST   /compile                   # 全量编译
GET    /export                    # 导出 Ontology
POST   /import                    # 导入 Ontology
```

### 7.2 AIP API（前缀 `/api/v1/aip`）

```
POST   /chat                      # 通用对话（经 LLM Gateway）
POST   /chat/stream               # 流式对话
POST   /rag/query                # 本体感知 RAG 查询
POST   /agents/{id}/run          # 运行 Agent
GET    /agents/{id}/status       # 查询 Agent 状态
POST   /agents/{id}/interrupt    # 中断 Agent
```

---

## 8. 验收标准（Definition of Done）

每条功能需求必须满足以下标准才算完成：

1. **代码**：已提交 PR 并通过 Code Review
2. **测试**：单元测试覆盖率 ≥ 80%，集成测试覆盖核心链路
3. **文档**：API 文档（OpenAPI）已更新，用户操作手册已补充
4. **部署**：Docker Compose 配置已更新，本地 `scripts/dev-start.sh` 可一键启动
5. **性能**：满足对应 NFR 指标
6. **安全**：通过 SAST 扫描（bandit / semgrep），无高危漏洞

---

## 9. 实施计划

### 9.1 Phase 1：核心语义层 + AIP 基础（Week 1-8）

| 周次 | 任务 | 产出 | 负责人 |
|:-----|:-----|:-----|:-------|
| W1-2 | Ontology 数据模型 + CRUD API | 6 张表 + REST API + 前端管理页 | Backend + Frontend |
| W3-4 | Ontology 编译器 + Interface 校验 | Compiler Service + GraphQL Schema 生成 | Backend |
| W5-6 | Action 引擎 + OPA 集成 + Writeback | Action Executor + Rules 校验 + 审计日志 | Backend |
| W7-8 | 语义搜索 + AIP LLM Gateway + RAG | Milvus 集成 + One API + RAG Pipeline | Backend + MLOps |

### 9.2 Phase 2：应用层 + 数据层 + 打磨（Week 9-16）

| 周次 | 任务 | 产出 | 负责人 |
|:-----|:-----|:-----|:-------|
| W9-10 | Object View + Workshop Builder | 对象详情页 + 拖拽应用构建器 | Frontend |
| W11-12 | Agent Orchestrator + Guardrails | LangGraph 工作流 + 安全校验 | Backend + MLOps |
| W13-14 | Foundry 数据管道 + CDC + 血缘 | SeaTunnel + Debezium + Atlas | Data Engineer |
| W15-16 | 集成测试 + 性能优化 + 文档 | 测试报告 + 优化清单 + 用户手册 | QA + All |

### 9.3 最小可行验证（Week 1-2 MVP）

如果资源受限，**2 周内**可先交付最小 Ontology MVP：

1. Object Type CRUD + 对象实例创建（写入 Neo4j）
2. Link Type CRUD + 关系实例创建（写入 Neo4j）
3. 对象子图查询 API（供前端可视化）
4. 混合搜索 API（关键词 + 语义）

---

## 10. 风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|:-----|:-----|:-----|:---------|
| OPA Rego 规则编写门槛高 | 用户难以自定义 Action Rules | 中 | 提供可视化规则编辑器 + 常用模板 |
| Milvus 资源占用大 | 小内存机器无法运行 | 中 | 提供 `docker-compose.light.yml`（无 Milvus，降级为纯 Neo4j 检索） |
| LLM API 成本不可控 | 租户超额使用 | 中 | 严格限流 + 预算告警 + 支持本地模型 fallback |
| Ontology 编译性能差 | 大规模本体编译超时 | 低 | 增量编译 + 异步编译任务 + 缓存 |
| SeaTunnel 学习曲线陡 | 数据工程师上手慢 | 中 | 提供可视化管道配置器 + 常见模板 |

---

## 11. 附录

### 11.1 术语表

| 术语 | 说明 |
|:-----|:-----|
| **Ontology** | 本体，对业务领域实体、关系、规则、行为的语义化建模 |
| **Object Type** | 对象类型，如 Employee、Department |
| **Link Type** | 链接类型，对象间关系定义，如 belongs_to、manages |
| **Interface** | 接口，对象类型的语义契约，如 Identifiable |
| **Action** | 动作，修改本体的操作，如 AssignManager |
| **Writeback** | 写回，Action 执行后将变更写入数据层 |
| **OPA** | Open Policy Agent，规则引擎 |
| **RAG** | Retrieval-Augmented Generation，检索增强生成 |
| **RRF** | Reciprocal Rank Fusion，混合检索重排算法 |

### 11.2 参考文档

- `Meatapivot架构补充方案：完美复刻Palantir五层架构.md`
- `Palantir本体架构：中国企业落地指南与开源替代方案`
- `企业AI决策核心引擎：Palantir Ontology系统从入门到精通`

---

> **文档维护**：本 PRD 由产品经理维护，开发评审后锁定。需求变更需提交 RFC 并通过评审后方可更新。
