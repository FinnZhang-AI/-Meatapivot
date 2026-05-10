# Meatapivot 今日开发任务清单 — 2026-05-09

> **生成日期**：2026-05-09（周六）  
> **基准文档**：`docs/TASKS.md`、`docs/PROGRESS.md`、`docs/DAILY-TASKS-2026-05-08.md`  
> **目标**：补齐 ObjectView 核心交互缺陷，完成 AIP 端到端验证，为 M5（前端就绪）扫清障碍。

---

## 一、代码库真实完成状态核查

### 1.1 已确认完成的（代码存在且功能可用）

| 模块 | 任务 | 状态 | 验证依据 |
|:-----|:-----|:-----|:---------|
| INF-003 | Milvus 部署 + MilvusClient 封装 | ✅ | `docker-compose.yml` 完整栈 + `milvus_client.py` |
| ONT-001 | Ontology 数据模型（PostgreSQL） | ✅ | `ontology_models.py` 全部模型定义完整 |
| ONT-002 | Object Type CRUD API | ✅ | `routers/ontology/object_types.py` + Postman 验证 |
| ONT-010 | Ontology 前端管理界面（5 页 CRUD） | ✅ | ObjectType/LinkType/Interface/ActionType/Function List 全部支持 Modal |
| APP-001 | Object View 对象详情页 | ✅ | `ObjectView.tsx` 接入真实 API，子图可视化保留 |
| APP-006 | Ontology 管理后台导航与布局 | ✅ | `Layout.tsx` 导航 + 路由已就绪 |
| AIP-005 | AIP API 端点（chat/chat_stream/rag） | 🟡 | 端点已注册，`/chat/stream` SSE 实现完整，`/rag/query` 已实现 |
| AIP-006 | LLM 对话前端界面 | 🟡 | Chat.tsx + SSE + 模型选择 + localStorage 持久化已完成 |
| AIP-007 | RAG 查询前端界面 | 🟡 | RAGSearch.tsx 界面完成，API 路径已修复为 `/aip/rag/query` |

### 1.2 骨架完成但核心功能待完善的

| 模块 | 任务 | 问题描述 | 风险等级 |
|:-----|:-----|:---------|:---------|
| APP-002 | PropertyTable 动态渲染 + 编辑 | **代码层面有编辑 UI，但 `onChange` 只是 `console.log`，未调用 API 保存属性** | 🔴 高（假功能） |
| APP-003 | RelatedObjects 分组展示 | **只能展示，无增删关系交互** | 🔴 高（功能不完整） |
| ONT-006 | Action 执行引擎 | direct 模式完整，function_backed 有沙箱，workflow 为 placeholder | 🟡 中 |
| ONT-005 | Ontology 编译器 | full_compile + incremental_compile + GraphQL Schema 生成已实现，未做性能验证 | 🟡 中 |
| ONT-008 | 语义搜索引擎 | Milvus 向量搜索 + Neo4j 图谱搜索 + RRF 重排已实现，但重排逻辑简单，异步索引更新未实现 | 🟡 中 |

### 1.3 完全未开始的

| 模块 | 任务 | 说明 |
|:-----|:-----|:-----|
| ONT-011 | 语义搜索前端界面 | 无搜索框/结果列表/详情页 |
| ONT-012 | Action 执行前端界面 | ObjectView 中只有简单按钮，无 ActionDialog 动态表单 |
| APP-004 | ActionButton + ActionDialog 组件 | Action 参数表单弹窗缺失 |
| APP-005 | Workshop App Builder | XYFlow 扩展，未开始 |
| APP-007 | 全局搜索升级 | 未开始 |
| APP-008 | 仪表盘首页升级 | 未开始 |
| AIP-003 | Agent Orchestrator | LangGraph 未集成 |
| AIP-004 | Guardrails 安全校验 | 未开始 |
| AIP-008 | Agent 工作流可视化 | 未开始 |
| AIP-009 | Prompt 管理后台 | 未开始 |
| AIP-010 | LLM 成本分析仪表盘 | 未开始 |
| INF-004 | CI/CD 流水线 | 未开始 |
| FDR-001~006 | Foundry 数据层全部 | 未开始 |

---

## 二、关键发现：ObjectView 存在"假功能"

### 2.1 PropertyTable 编辑未真正保存

**位置**：`frontend/src/pages/objects/ObjectView.tsx` 第 130 行

```tsx
<PropertyTable
  properties={obj.properties || {}}
  editable={true}
  onChange={(props) => console.log('Updated props:', props)}  // ← 仅打印，未调用 API
/>
```

**影响**：用户点击"编辑属性"、修改值、点击"保存"后，UI 会退出编辑模式，但**数据并未持久化到后端**。刷新页面后修改丢失。

**根因**：缺少 `useUpdateObjectProperties` hook 和对应的 API 调用。

### 2.2 RelatedObjects 无增删关系

**位置**：`frontend/src/components/ontology/RelatedObjects.tsx`

**影响**：只能查看关联对象，无法通过 UI 添加新关系或删除现有关系。用户必须直接操作 Neo4j 或后端 API。

### 2.3 Action 执行无参数表单

**位置**：`frontend/src/pages/objects/ObjectView.tsx` 第 188~210 行

**影响**：Action 只有简单按钮，点击后直接执行。对于需要参数的 Action（如"发送邮件"需要收件人地址），无法输入参数。

---

## 三、5月9日开发任务清单

> **策略**：先消灭 ObjectView "假功能"（让用户能真正编辑属性、增删关系），再补齐 ActionDialog，最后验证 AIP 端到端。这是让 M5 里程碑真正达标的最短路径。

---

### 🔴 P0：消灭 ObjectView "假功能"（必须今日完成）

#### TASK-01：PropertyTable 属性编辑真正保存（APP-002 补完）

**问题**：PropertyTable 的 `onChange` 回调在 ObjectView.tsx 中只是 `console.log`，未调用后端 API。

**修改内容**：
1. 在 `frontend/src/hooks/useOntology.ts` 中新增 `useUpdateObjectProperties` hook：
   - 调用 `PUT /ontology/object-types/{typeId}/objects/{objectId}`（如后端无此端点，需补充）
2. 在 `ObjectView.tsx` 中替换 `console.log` 为真实的 `mutateAsync` 调用
3. 保存成功后显示成功提示，失败时回滚并显示错误

**关联需求**：APP-002、ONT-002
**预估工时**：1 小时
**验收标准**：
1. 在 ObjectView 中编辑属性值 → 点击保存 → 刷新页面 → 修改仍然存在
2. 网络面板可见 `PUT` 请求返回 200
3. `npm run build` 通过

---

#### TASK-02：RelatedObjects 支持增删关系（APP-003 补完）

**问题**：RelatedObjects 组件只有展示，无添加/删除关系的交互。

**修改内容**：
1. 在 `RelatedObjects.tsx` 中新增：
   - "添加关系"按钮（有权限时显示）
   - 点击后弹出选择目标对象的搜索框
   - 每个关联对象右侧显示删除按钮
2. 在 `useOntology.ts` 中新增 `useCreateLink` / `useDeleteLink` hooks：
   - `POST /ontology/links`
   - `DELETE /ontology/links/{id}`
3. 操作成功后刷新 `useObjectLinks` query

**关联需求**：APP-003、ONT-003
**预估工时**：1.5 小时
**验收标准**：
1. ObjectView 中可见"添加关系"按钮
2. 添加关系后关联对象列表实时刷新
3. 删除关系后关联对象消失
4. `npm run build` 通过

---

### 🟡 P1：补齐核心交互组件（建议今日完成）

#### TASK-03：ActionDialog 动态参数表单（APP-004 / ONT-012）

**问题**：ObjectView 中的 Action 只有简单按钮，无参数输入弹窗。

**修改内容**：
1. 新建 `frontend/src/components/ontology/ActionDialog.tsx`：
   - 接收 `actionType`（含 `parameters` 定义数组）
   - 根据 parameter 的 `type` 动态渲染表单字段：string/number/date/select/boolean
   - 支持 `required` 校验
   - 提交时调用 `useExecuteAction` 并传入参数
2. 在 `ObjectView.tsx` 中：
   - 点击 Action 按钮时，如 Action 有 parameters，先弹出 ActionDialog
   - 如 Action 无 parameters，直接执行（保持现有行为）

**关联需求**：APP-004、ONT-012
**预估工时**：1.5 小时
**验收标准**：
1. 有参数的 Action 点击后弹出表单弹窗
2. 必填字段未填时阻止提交
3. 提交后显示执行结果（成功/失败）
4. 执行成功后自动刷新 ObjectView 数据
5. `npm run build` 通过

---

#### TASK-04：Chat SSE 流式端到端验证（FE-FEAT-05）

**问题**：Chat.tsx 代码层面已完成 SSE 接入，但尚未确认与后端 `/aip/chat/stream` 的端到端可用性。

**验证步骤**：
1. 使用 `docker-compose.light.yml` 启动后端
2. 确保 `llm_gateway.py` 中 `ONE_API_URL` 指向可用的 One API / OpenAI 代理
3. 在前端 Chat 页面发送消息，观察：
   - SSE 连接是否成功建立（Status 200，Content-Type: text/event-stream）
   - 首 Token 是否在 2s 内到达
   - 逐字输出是否流畅
   - 停止按钮是否能中断 SSE
4. 如发现问题，记录并做最小修复

**关联需求**：AIP-005、AIP-006
**预估工时**：45 分钟
**验收标准**：
1. SSE 连接建立成功
2. 可见逐字输出效果
3. 点击"停止"可中断连接
4. 异常时前端显示错误信息而非白屏

---

#### TASK-05：RAGSearch 真实查询端到端验证（FE-FEAT-06）

**问题**：RAGSearch.tsx 界面已完成且 API 路径已修复，但未验证端到端。

**验证步骤**：
1. 确保后端有至少一个 Ontology Object（可用 `scripts/demo-seed.py` 生成）
2. 在 RAG 搜索页输入问题（如"查询所有VIP客户"）
3. 观察：
   - `/aip/rag/query` 是否返回 200
   - `answer` 是否正确显示
   - `sources` 列表是否正确展示 objectType / objectKey / score
4. 如后端 SemanticSearchService 返回空结果，检查 Milvus 是否可用（light 模式下会降级为 graph-only）

**关联需求**：AIP-002、AIP-007
**预估工时**：45 分钟
**验收标准**：
1. 输入问题后，前端正确显示 answer + sources 列表
2. sources 中显示 objectType / objectKey / score
3. 空结果时显示友好提示
4. 加载中显示 loading 状态

---

### 🟢 P2：体验增强与测试（今日有余力时完成）

#### TASK-06：语义搜索前端界面（ONT-011）

**问题**：当前全局无统一的语义搜索入口。Ontology 管理后台和 ObjectView 都缺少搜索能力。

**修改内容**：
1. 新建 `frontend/src/pages/ontology/SemanticSearch.tsx`：
   - 搜索框（支持按 Object Type 过滤下拉）
   - 结果列表：显示 objectKey、objectType、score、来源标签（向量/图谱）
   - 点击结果跳转 ObjectView
2. 在 `App.tsx` 路由中注册 `/ontology/search`
3. 在 `Layout.tsx` 导航中添加"语义搜索"入口（或集成到顶部全局搜索框）

**关联需求**：ONT-011、ONT-008
**预估工时**：1.5 小时
**验收标准**：
1. 搜索页面可访问
2. 输入关键词返回结果列表
3. 点击结果正确跳转到 ObjectView
4. `npm run build` 通过

---

#### TASK-07：补充 ObjectView E2E 测试脚本

**问题**：缺少自动化验证 ObjectView 核心链路（查看对象 → 编辑属性 → 执行 Action）的手段。

**修改内容**：
1. 新建 `scripts/e2e-object-view.py`（基于 `httpx` + `pytest`）：
   - 使用 demo-seed 数据创建测试对象
   - 验证 GET /objects/{id} 返回正确属性
   - 验证 PUT /object-types/{typeId}/objects/{id} 可更新属性
   - 验证 GET /objects/{id}/links 返回关联对象
   - 验证 POST /action-types/{id}/execute 可执行 Action
2. 测试不依赖前端，纯后端 API 验证

**关联需求**：M2 API 就绪、M5 前端就绪
**预估工时**：1 小时
**验收标准**：
1. `python scripts/e2e-object-view.py` 成功执行
2. 所有断言通过
3. 脚本在 CI 环境中可运行

---

## 四、任务优先级矩阵

| 优先级 | 任务编号 | 任务名称 | 预估工时 | 阻塞后续 | 对应 TASKS.md |
|:-------|:---------|:---------|:---------|:---------|:--------------|
| 🔴 P0 | TASK-01 | PropertyTable 属性编辑真正保存 | 1h | M5 验收 | APP-002 |
| 🔴 P0 | TASK-02 | RelatedObjects 支持增删关系 | 1.5h | M5 验收 | APP-003 |
| 🟡 P1 | TASK-03 | ActionDialog 动态参数表单 | 1.5h | ONT-012 | APP-004 |
| 🟡 P1 | TASK-04 | Chat SSE 端到端验证 | 45min | AIP-006 验收 | AIP-005/006 |
| 🟡 P1 | TASK-05 | RAGSearch 端到端验证 | 45min | AIP-007 验收 | AIP-002/007 |
| 🟢 P2 | TASK-06 | 语义搜索前端界面 | 1.5h | ONT-011 | ONT-011 |
| 🟢 P2 | TASK-07 | ObjectView E2E 测试脚本 | 1h | 质量门禁 | M2+M5 |

**今日总预估工时**：~7.5 小时（P0+P1 约 5.5 小时，P2 约 2.5 小时）

---

## 五、与里程碑的映射

| 里程碑 | 当前状态 | 今日任务贡献 | 完成后状态 |
|:-------|:---------|:-------------|:-----------|
| M2 API 就绪 | 🟡 进行中 | TASK-01（可能需要新增后端 PUT 端点） | 更接近完成 |
| M3 引擎就绪 | 🟡 进行中 | TASK-03（Action 参数表单验证引擎能力） | 更接近完成 |
| M4 搜索就绪 | 🟡 进行中 | TASK-05（RAG 端到端验证）、TASK-06（语义搜索前端） | 更接近完成 |
| M5 前端就绪 | 🟡 进行中 | **TASK-01/02/03 是核心**，消灭假功能 | **可标记为完成** |

> **关键判断**：如果 TASK-01、TASK-02、TASK-03 全部完成，M5（前端就绪）可以真正标记为完成。当前 M5 被标记为"进行中"的根本原因是 ObjectView 的核心交互（编辑属性、增删关系、Action 参数）尚未闭环。

---

## 六、风险与备注

1. **TASK-01 可能触发后端 API 补充**：如果后端缺少 `PUT /ontology/object-types/{typeId}/objects/{objectId}` 端点，需要按 FastAPI 现有风格补充。预估额外 20 分钟。
2. **TASK-02 需要后端 Link 删除端点**：确认 `DELETE /ontology/links/{id}` 是否已注册，如无则需补充。
3. **TASK-04 依赖外部 LLM 服务**：如果本地无 One API / OpenAI 代理，SSE 验证可能无法进行。此时改为代码审查 + mock 测试，记录阻塞项。
4. **TASK-05 在 light 模式下**：`docker-compose.light.yml` 中 `MILVUS_URI=""`，语义搜索会降级为纯 graph 搜索。这是预期行为，不影响 RAG 基本功能验证。
5. **最小改动原则**：只修改与任务直接相关的代码，不重构相邻代码。PropertyTable、RelatedObjects 现有渲染逻辑保持不变，仅增加交互层。
6. **所有前端修改需通过**：`npx tsc --noEmit` + `npm run build`
7. **所有后端修改需通过**：`python -m py_compile` + `pytest backend/tests`

---

## 七、昨日任务完成状态对照

| 昨日任务 | 状态 | 备注 |
|:---------|:-----|:-----|
| FE-FIX-03 修复 RAG API 路径 | ✅ 已完成 | `useAIP.ts` 第 139 行已修正为 `/aip/rag/query` |
| OPS-01 docker-compose.light.yml | ✅ 已完成 | 文件已创建，仅核心服务 |
| AIP-FEAT-01 Chat localStorage 持久化 | ✅ 已完成 | `aipStore.ts` 已使用 zustand persist |
| OPS-04 demo-seed.py | ✅ 已完成 | 脚本可生成 Customer/Order/Product |
| TEST-03 test_ontology_crud.py | ✅ 已完成 | PROGRESS.md 已记录 |

> 昨日全部 P0/P1 任务已完成。今日进入新迭代。

---

> **状态**：待执行  
> **下次更新**：2026-05-09 日终更新完成状态与实际工时
