# Meatapivot 今日开发任务清单 — 2026-05-08

> **生成日期**：2026-05-08（周五）  
> **基准文档**：`docs/TASKS.md`、`docs/PROGRESS.md`、`docs/ITERATION-2026-05-06.md`、`docs/CODE-REVIEW-2026-05-06.md`  
> **目标**：完成 Week 2 收尾，修复联调 BUG，为 M3（引擎就绪）扫清障碍。

---

## 一、进度比对摘要

### 1.1 整体进度

| 指标 | 数值 |
|:-----|:-----|
| 总任务数 | 40 项（TASKS.md） |
| 已完成/部分完成 | 约 15 项 |
| 整体进度 | **~30%**（Iteration 2026-05-07 基准） |

### 1.2 模块完成度

| 模块 | 任务数 | 已完成 | 部分完成 | 未开始 | 进度 |
|:-----|:-------|:-------|:---------|:-------|:-----|
| INF（基础设施） | 4 | 1（Milvus） | 2（PG/Redis） | 1（CI/CD） | ~50% |
| ONT（语义层 Backend） | 12 | 3（模型+Object CRUD+前端管理） | 6（Link/Interface/Compiler/Action/Function/搜索） | 3（语义搜索前端/Action前端/导入导出冲突处理） | ~50% |
| AIP（智能层 Backend） | 10 | 0 | 4（LLM Gateway/基础RAG/Chat API/Chat前端） | 6（Agent/Guardrails/RAG前端/Agent可视化/Prompt管理/成本分析） | ~20% |
| APP-F（应用层 Frontend） | 8 | 2（ObjectView/管理后台导航） | 3（PropertyTable/RelatedObjects/Chat） | 3（ActionButton/Workshop Builder/全局搜索/仪表盘） | ~63% |
| FDR（数据层） | 6 | 0 | 0 | 6 | 0% |

### 1.3 里程碑状态

| 里程碑 | 计划 | 当前状态 | 阻塞项 |
|:-------|:-----|:---------|:-------|
| M1 模型就绪 | Week 2 | **✅ 完成** | 无 |
| M2 API 就绪 | Week 4 | **🟡 进行中** | 待补充测试覆盖 |
| M3 引擎就绪 | Week 6 | **🟡 进行中** | Compiler 性能验证 / Action 沙箱待完善 |
| M4 搜索就绪 | Week 8 | **🟡 进行中** | RRF 重排 / 端到端验证 |
| M5 前端就绪 | Week 10 | **🟡 进行中** | APP-002/003/004 待完善 |
| M6 智能就绪 | Week 12 | ⬜ 未开始 | 依赖 M4 + M5 |
| M7 数据就绪 | Week 14 | ⬜ 未开始 | 依赖 M6 |
| M8 发布就绪 | Week 16 | ⬜ 未开始 | 全量集成测试 |

---

## 二、上一迭代遗留与新增发现

### 2.1 Iteration 2026-05-07 已完成（确认）

- [x] FE-FEAT-07：ObjectTypeList 编辑 Modal
- [x] FE-FEAT-08：ActionTypeList 新建/编辑/删除
- [x] FE-FEAT-09：FunctionList 新建/编辑/删除 + 代码编辑 Modal
- [x] FE-FEAT-10：InterfaceList 新建/编辑/删除
- [x] FE-FEAT-11：LinkTypeList 新建/编辑/删除
- [x] CR-FIX-01：代码审查修复验证（db.commit / tenant隔离 / Milvus连接复用 / tsconfig）
- [x] TEST-02：补充 test_ontology_integration.py（20+ 用例）

### 2.2 代码审查发现但待验证的问题

| 编号 | 问题 | 位置 | 风险等级 |
|:-----|:-----|:-----|:---------|
| FE-FIX-03 | **RAG API 路径不匹配**：前端 `useRAGQuery` 调用 `/aip/rag`，后端端点为 `/aip/rag/query` | `frontend/src/hooks/useAIP.ts` | 🔴 高（功能不可用） |
| FE-FIX-04 | **Chat.tsx 整页刷新导航**：`handleNodeClick` 使用 `window.location.href` 而非 `useNavigate` | `frontend/src/pages/objects/ObjectView.tsx` | 🟡 中（SPA 体验差） |
| FE-DEBT-01 | **tsconfig 严格检查降级**：`noUnusedLocals` / `noUnusedParameters` 仍为 `false` | `frontend/tsconfig.json` | 🟢 低（技术债） |

### 2.3 PROGRESS.md 中标记的“下一迭代重点”（Week 2 剩余）

- [ ] FE-FEAT-05：Chat.tsx SSE 流式对话联调
- [ ] FE-FEAT-06：RAGSearch.tsx 接入真实 RAG 查询
- [ ] AIP-FEAT-01：对话历史持久化（本地存储 + 后端 session API）
- [ ] BE-FEAT-05：编写 pytest 集成测试（≥ 15 条用例通过）
- [ ] OPS-01：提供 docker-compose.light.yml（无 Milvus 轻量版）
- [ ] OPS-04：编写 scripts/demo-seed.py 一键生成演示数据

---

## 三、今日开发任务清单

> **策略**：先修 BUG（ unblock 功能），再补基础设施（提升开发效率），最后增强体验（持久化/演示数据）。

---

### 🔴 P0：BUG 修复（必须今日完成）

#### TASK-01：修复 RAG API 路径不匹配（FE-FIX-03）
- **问题描述**：`frontend/src/hooks/useAIP.ts` 第 139 行调用 `${API_BASE_URL}/aip/rag`，但 `backend/app/routers/aip.py` 注册的端点是 `@router.post("/rag/query")`，导致 RAG 查询 404。
- **修改内容**：将前端路径修正为 `/aip/rag/query`。
- **关联需求**：AIP-005（AIP API 端点）/ AIP-007（RAG 查询前端界面）
- **预估工时**：15 分钟
- **验收标准**：
  1. `npx tsc --noEmit` 无类型错误
  2. `npm run build` 通过
  3.（联调时）Network 面板请求 `/api/v1/aip/rag/query` 返回 200

---

#### TASK-02：提供 docker-compose.light.yml 轻量开发环境（OPS-01）
- **问题描述**：当前 `docker-compose.yml` 包含 Milvus（etcd + minio-milvus + milvus-standalone）和完整的可观测性栈（Prometheus/Grafana/Loki/Tempo），本地开发启动极慢、资源占用高。
- **修改内容**：
  1. 新建 `docker-compose.light.yml`，仅保留：postgres、neo4j、redis、backend、frontend
  2. backend 环境变量中 `MILVUS_URI` 置空或指向本地 mock
  3. 添加注释说明何时使用完整版 / 轻量版
- **关联需求**：INF 基础设施 / 全员开发效率
- **预估工时**：30 分钟
- **验收标准**：
  1. `docker-compose -f docker-compose.light.yml config` 通过（无语法错误）
  2. `docker-compose -f docker-compose.light.yml up -d` 可在 60 秒内启动核心服务

---

### 🟡 P1：功能补齐与体验增强（建议今日完成）

#### TASK-03：Chat 对话历史本地持久化（AIP-FEAT-01 前端部分）
- **问题描述**：当前 `aipStore` 使用纯内存存储 `messages`，刷新页面后对话丢失。后端 session API 尚未就绪，先以 `localStorage` 兜底。
- **修改内容**：
  1. 在 `frontend/src/stores/aipStore.ts` 中集成 `localStorage` 持久化：
     - key: `meatapivot_chat_session`
     - 初始化时从 localStorage 读取
     - `addMessage` / `clearMessages` 时同步写入
  2. 添加 `sessionId` 管理（简单 UUID），为后续对接后端 session API 预留字段
- **关联需求**：AIP-006（LLM 对话前端界面）
- **预估工时**：45 分钟
- **验收标准**：
  1. 发送多条消息后刷新浏览器，对话记录仍然存在
  2. 点击"+ 新对话"按钮后清空记录且 localStorage 被清除
  3. `npx tsc --noEmit` 通过

---

#### TASK-04：Chat SSE 流式联调验证（FE-FEAT-05）
- **问题描述**：Chat.tsx 代码层面已完成 SSE 接入，但尚未确认与后端 `/aip/chat/stream` 的端到端可用性。
- **修改内容**：
  1. 本地启动后端（`uvicorn app.main:app --reload`）
  2. 验证 SSE 流式输出首 Token < 2s
  3. 如发现问题，记录并创建最小修复（不扩大范围）
- **关联需求**：AIP-005 / AIP-006
- **预估工时**：1 小时
- **验收标准**：
  1. 前端发送消息后，SSE 连接建立成功（Status 200，Content-Type: text/event-stream）
  2. 可看到逐字输出效果
  3. 点击"停止"按钮可中断 SSE 连接

---

#### TASK-05：RAGSearch 接入真实 RAG 查询联调（FE-FEAT-06）
- **问题描述**：RAGSearch.tsx 界面已完成，但依赖 TASK-01 的路径修复。修复后需验证端到端。
- **修改内容**：
  1. 在 TASK-01 修复后，验证 RAG 查询流程
  2. 如后端 `/rag/query` 返回空结果或异常，记录具体问题
- **关联需求**：AIP-002 / AIP-007
- **预估工时**：45 分钟
- **验收标准**：
  1. 输入问题后，前端正确显示 answer + sources 列表
  2. sources 中显示 objectType / objectKey / score

---

### 🟢 P2：基础设施与测试（今日有余力时完成）

#### TASK-06：scripts/demo-seed.py 一键演示数据（OPS-04）
- **问题描述**：新开发者或演示环境缺少快速生成数据的手段。
- **修改内容**：
  1. 新建 `scripts/demo-seed.py`，使用 `httpx` 或 `requests` 调用后端 API：
     - 创建 2-3 个 ObjectType（Customer、Order、Product）
     - 为每个类型创建 3-5 个 Object 实例
     - 创建 LinkType（如 `placed_by`、`contains`）
     - 创建若干 Link 实例
  2. 支持命令行参数：`--base-url`、`--token`（可选）
- **关联需求**：M2 API 就绪 / 演示准备
- **预估工时**：1 小时
- **验收标准**：
  1. `python scripts/demo-seed.py` 成功执行，无报错
  2. 执行后前端 ObjectTypeList 可见 Customer/Order/Product
  3. ObjectView 中可看到关联对象和子图

---

#### TASK-07：补充 pytest 集成测试 — CRUD 流程（BE-FEAT-05）
- **问题描述**：当前 `test_ontology_integration.py` 以静态路由检查为主，缺少真正的 CRUD 流程测试。
- **修改内容**：
  1. 补充至少 3 条使用 `AsyncClient` + `AsyncSession` 或内存 mock 的流程测试：
     - ObjectType 创建 → 查询 → 更新 → 删除
     - Object 实例创建 → 属性更新
     - Link 创建 → 子图查询
  2. 测试不依赖真实 Neo4j / Milvus（使用 mock 或 skip）
- **关联需求**：M2 API 就绪
- **预估工时**：1.5 小时
- **验收标准**：
  1. `pytest backend/tests/test_ontology_integration.py -v` 全部通过
  2. 新增用例 ≥ 3 条，且覆盖 POST/GET/PUT/DELETE 流程

---

## 四、任务优先级矩阵

| 优先级 | 任务编号 | 任务名称 | 预估工时 | 阻塞后续 |
|:-------|:---------|:---------|:---------|:---------|
| 🔴 P0 | TASK-01 | 修复 RAG API 路径 | 15min | TASK-05（RAG 联调） |
| 🔴 P0 | TASK-02 | docker-compose.light.yml | 30min | 全员开发效率 |
| 🟡 P1 | TASK-03 | Chat 对话历史 localStorage 持久化 | 45min | AIP-FEAT-01 后端对接 |
| 🟡 P1 | TASK-04 | Chat SSE 联调验证 | 1h | AIP-006 体验验收 |
| 🟡 P1 | TASK-05 | RAGSearch 真实查询联调 | 45min | AIP-007 前端验收 |
| 🟢 P2 | TASK-06 | demo-seed.py 演示数据 | 1h | M2 演示准备 |
| 🟢 P2 | TASK-07 | pytest CRUD 流程测试 | 1.5h | M2 质量门禁 |

**今日总预估工时**：~5.5 小时（P0+P1 约 3 小时，P2 约 2.5 小时）

---

## 五、与 TASKS.md 的映射关系

| 今日任务 | 对应 TASKS.md 任务 | 模块 |
|:---------|:-------------------|:-----|
| TASK-01 | AIP-005（API 端点）/ AIP-007（RAG 前端） | AIP |
| TASK-02 | INF 基础设施（新增支撑任务） | INF |
| TASK-03 | AIP-006（LLM 对话前端） | AIP |
| TASK-04 | AIP-005 / AIP-006 | AIP |
| TASK-05 | AIP-002（RAG Pipeline）/ AIP-007 | AIP |
| TASK-06 | M2 里程碑支撑 | ONT+AIP |
| TASK-07 | M2 里程碑支撑 | ONT |

---

## 六、风险与备注

1. **RAG 路径不匹配**是今日最高优先级 BUG，它直接导致 RAGSearch 页面功能不可用。
2. **docker-compose.light.yml** 将显著提升后续开发迭代速度，建议在上午完成。
3. 后端 session API（对话历史后端持久化）不在今日范围，先用 localStorage 兜底，后续迭代替换为后端 API + 多端同步。
4. 若 TASK-04/TASK-05 联调中发现后端 SSE 或 RAG 逻辑存在深层问题，**不要扩大修复范围**，仅记录问题并创建独立任务。
5. 所有前端修改需保持 `npx tsc --noEmit` + `npm run build` 通过；所有后端修改需保持 `python -m py_compile` + `pytest` 通过。

---

> **状态**：待执行  
> **下次更新**：2026-05-08 日终更新完成状态与实际工时
