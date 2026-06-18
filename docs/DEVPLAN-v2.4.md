# Meatapivot 开发计划 v2.4

> **版本**：2.4
> **日期**：2026-06-18
> **基于**：v2.3.1 Release 状态 + `CHANGELOG.md` + `PROGRESS.md` + 代码 TODO 扫描
> **周期**：1 个 Sprint / 2 周
> **目标**：把 v2.3.1 配得出来但跑不动的 Workshop 接上执行环 + 测试基础收口

---

## 背景

v2.3.0 + v2.3.1 已完成 AIP 智能层、Workshop 节点配置（Table/Chart/Action/Filter/LinkNav）、OPA、LLM 成本仪表盘。当前剩余的真实痛点：

- **Workshop Filter/LinkNav 节点只能配不能跑**——v2.3.1 注释里我自己写"runtime is wired in v2.4"。这是用户视角最明显的"半成品"。
- **前端没 Vitest 覆盖**——v2.2.0 PROGRESS 写过"前端 Vitest 测试"，但实际只 S6-2 写了 4 个组件，剩下 Dashboard/CostDashboard/WorkshopEditor 等 v2.3 才出的组件零测试。
- **Celery 4 个 worker 任务还是 TODO 骨架**——`backend/app/worker/tasks.py` 里 4 个 `@celery_app.task` 全是 `# TODO: Implement ...`，但 interface validation 那个我们 v2.3.0 已经实写了，所以"骨架"这个事不像文档那么糟，document parse / function exec 这两个是真真空。
- **PROGRESS / CHANGELOG 文档已经"够用"了**——v2.4 主要是补功能债。

v2.4 聚焦 **"让 Workshop 跑起来"** + **"测试基础收口"**。

**延后到 v2.4.1 / v3.0**：
- OPA HTTP 服务替换（CHANGELOG v2.3.0 写的"swap point"）
- Per-direction token pricing（CHANGELOG v2.3.0 写的"deferred"）
- Foundry 数据层（SeaTunnel/CDC/Atlas）—— v3.0

---

## Sprint 总览

| Sprint | 周期 | 主题 | 任务数 | 预估工时 | 里程碑 |
|--------|------|------|--------|----------|--------|
| **S1** | Week 1-2 | Workshop runtime + 前端测试 + Worker 补全 | 4 | ~50h | M1：v2.4.0 |

---

## Sprint 1：Workshop Runtime + Test Foundation（Week 1-2）

### V4-1 Workshop Runtime Executor（20h）

**目标**：让用户在编辑器点 "Run"，按 graph 拓扑执行，返回每个节点的输出结果。

**DoD**：
- 后端 `POST /api/v1/workshop/apps/{id}/run` 端点
- Executor 按节点拓扑（DFS）执行：Table → 查询 PG → 返回实例列表；Filter → 按 field/operator/value 过滤；Chart → 把数据画图（JSON 输出，前端渲染）；LinkNav → 按 linkType 跳；Action → 触发 Action
- 执行结果存 `workshop_executions` 表（status / per_node_output JSONB / created_at）
- 前端 WorkshopEditor 顶部加 "Run" 按钮 + 节点结果显示侧栏（点击节点看该节点输出）
- SSE 流式推送每节点完成事件（前端实时更新节点边框颜色：pending/running/done/error）
- 单元测试：拓扑排序、Filter 求值（所有 operator）、错误隔离（一个节点失败不阻塞其他节点）

**关键文件**：
- 后端新建：`app/services/workshop_executor.py`、`app/models/workshop_models.py` 加 `WorkshopExecution` 模型、`app/routers/workshop_executions.py`
- 后端改：`app/routers/workshop.py` 加 `/run` 端点、`docker/postgres/init.sql` 加 DDL
- 前端改：`WorkshopEditor.tsx` 加 Run 按钮 + 节点结果边栏；`workshopStore.ts` 新建 Zustand store 存执行状态
- 测试：`backend/tests/test_workshop_executor.py`（5+ 测试）

### V4-2 前端 Vitest 测试基础（10h）

**目标**：v2.3 出的新组件有最低测试覆盖。

**DoD**：
- `frontend/package.json` 加 `vitest` + `@testing-library/react` + `jsdom`
- `vitest.config.ts` 配置（jsdom env + alias 跟 vite 一致）
- 5 个组件测试：
  - `CostDashboard.tsx` — 空数据态、加载态、错误态、3 个卡片渲染
  - `GlobalSearch.tsx` — 输入触发 fetch、Autocomplete 渲染、历史点击
  - `ValidationToaster.tsx` — 收到 event 渲染 toast、6s 自动消失
  - `WorkshopEditor.tsx` — 加节点、连线、保存按钮 disabled 态
  - `ObjectTypeList.tsx`（或当前等价组件）— 基础列表渲染
- CI workflow `.github/workflows/ci.yml` 加 `npm test` 步骤

**关键文件**：
- 新建：`frontend/vitest.config.ts`、`frontend/src/test/setup.ts`
- 改：`frontend/package.json`（deps + scripts）、5 个测试文件
- 改：`.github/workflows/ci.yml`

### V4-3 Celery Worker 任务补全（12h）

**目标**：把 `tasks.py` 里 2 个最大真空的 worker 任务从 TODO 变成可用实现。

**DoD**：
- `process_document` 真正实现：从 MinIO 下载 → 用 `python-docx` / `pypdf` 解析文本 → 存到 `Document.content_text` + 生成 embedding 写入 Milvus
- `execute_function_action` 真正实现：调用 `sandbox_restricted.py` 沙箱执行 Python 函数（30s timeout + 256MB memory limit）→ 返回 result
- `compile_ontology` / `execute_decision_flow` **留作 TODO 不动**（v2.4.1）
- 单元测试：`process_document` 走 MinIO mock；`execute_function_action` 用一个 hello world 函数端到端

**关键文件**：
- 改：`backend/app/worker/tasks.py`、`backend/requirements.txt` 加 `python-docx` / `pypdf` / `pdfplumber`
- 测试：`backend/tests/test_workers.py`

### V4-4 Release v2.4.0（8h）

**目标**：跟 v2.3.0 一样全套收尾。

**DoD**：
- `CHANGELOG.md` 追加 v2.4.0 章节
- `docs/PROGRESS.md` 加 v2.4.0 段（替换头部"v2.3.1"为"v2.4.0"）
- `docs/API-SPEC.md` 加 10.x 章节：`/workshop/apps/{id}/run` + `workshop_executions` + worker 任务 admin 端点
- `docs/RELEASE-v2.4.md` 新建部署增量指南
- `git tag v2.4.0` + push
- GitHub Release（按上次走 Web UI）

**关键文件**：
- 4 个 docs 改动
- 1 个 tag 命令

---

## Sprint 1 验收

- [ ] 用户能在 Workshop Editor 点 Run，看到每个节点依次执行（绿框→done）
- [ ] Filter 节点按 8 个 operator 真的能过滤
- [ ] LinkNav 节点真的按 linkType 跳到关联对象
- [ ] Chart 节点在 Workshop runtime 里输出结构化数据（前端可画图）
- [ ] `npm test` 在 CI 全过（≥ 5 个组件测试）
- [ ] 上传 PDF 文档走 `process_document` Celery 任务后，content_text 字段非空
- [ ] Function-backed Action 走 `execute_function_action` 后返回正确 result
- [ ] CHANGELOG / API-SPEC / PROGRESS 同步
- [ ] tag v2.4.0 推到远端

---

## 模块 v2.4 目标完成度

| 模块 | v2.3.1 | v2.4 目标 | 新增任务 |
|------|--------|----------|----------|
| INF | ~85% | ~88% | Worker 任务补全 |
| ONT | ~95% | ~95% | — |
| AIP | ~80% | ~80% | — |
| APP-F | ~90% | **~95%** | Workshop runtime + 前端测试 |
| FDR | 0% | 0% | 延后 v3.0 |

---

## 风险管理

| 风险 | 概率 | 应对 |
|------|------|------|
| XYFlow + SSE 实时更新性能 | 中 | 每节点完成才发事件，不发中间状态；节点 < 50 时无压力 |
| process_document 解析失败（损坏 PDF） | 高 | try/except 隔离，存 `error_message` 字段，不抛 |
| 沙箱执行用户函数安全性 | 已通过 S1-2 RestrictedPython 解决 | 复用现有 sandbox |
| Vitest 配 jsdom + React Testing Library 第一次跑会卡 | 中 | 先用 PropertyTable 这种无状态组件跑通，再扩 |
| Celery worker 启动后接口未注册导致 `validate_all_interfaces` 也跑不起来 | 低 | tasks.py 改之前先确认现有 v2.3.0 任务还工作 |

---

## 人员分配（Sprint 1）

| 角色 | 任务 | 估时 |
|------|------|------|
| Backend A | V4-1 Workshop executor + V4-3 worker tasks | 32h |
| Frontend A | V4-1 节点结果 + V4-2 Vitest | 18h |
| DevOps | V4-4 release docs + tag | (与 Frontend A 串行) |

> 实际是同一个人（Mavis / 我）全栈做，所以上述只是逻辑拆分，便于排风险。

---

## 更新记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-11 | v2.3 | 基于 v2.2.0 + GAP-ANALYSIS，4 Sprint / 16 任务 / 232h |
| 2026-06-16 | v2.3.1 | Workshop 节点补完（Filter/LinkNav），纯前端小迭代 |
| 2026-06-18 | v2.4 | Workshop runtime + 测试基础收口，1 Sprint / 4 任务 / ~50h |
