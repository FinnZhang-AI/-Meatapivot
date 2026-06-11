# Meatapivot 开发计划 v2.3

> **版本**：2.3
> **日期**：2026-06-11
> **基于**：v2.2.0 Release 状态 + `TASKS.md` + `CHANGELOG.md`
> **周期**：4 个 Sprint / 8 周
> **目标**：AIP 智能层完成 + ONT 打磨 + APP-F 补全

---

## 背景

v2.2.0 已完成全部 14 个 P0 项闭合，6 个 Sprint 交付。当前剩余：
- **AIP**：Agent Orchestrator、Guardrails、Prompt 管理等核心 AI 能力未实现
- **ONT**：Interface 异步校验、OPA 集成、BGE-Reranker 未完成
- **APP-F**：Workshop Builder、全局搜索、Dashboard 升级未启动
- **FDR**：数据层未启动（延后至 v3.0）

v2.3 聚焦 **"AI-Native"** 方向：补齐 AIP 智能层，形成完整的 Agent + Guardrails + RAG 链路。

---

## Sprint 总览

| Sprint | 周期 | 主题 | 任务数 | 预估工时 | 里程碑 |
|--------|------|------|--------|----------|--------|
| **S1** | Week 1-2 | AIP：Agent Orchestrator | 3 | 56h | M1：Agent 可用 |
| **S2** | Week 3-4 | AIP：Guardrails + RAG 完善 | 4 | 64h | M2：安全 AI |
| **S3** | Week 5-6 | ONT 打磨 + APP-F 补全 | 5 | 64h | M3：产品完整 |
| **S4** | Week 7-8 | 性能 + 测试 + Release | 4 | 48h | M4：v2.3.0 |

**总计**：16 任务 / 232h / 8 周

---

## Sprint 1：AIP Agent Orchestrator（Week 1-2）

| 编号 | 任务 | 工时 | DoD |
|------|------|------|-----|
| **S1-1** | LangGraph Agent 引擎 | 24h | Agent 定义（角色+工具集绑定）；工作流节点：LLM/Action/Search/Human/Condition/End；多 Agent 协作（顺序/分支/循环）；会话状态持久化（Redis） |
| **S1-2** | Agent API 端点 | 16h | `POST /agents/{id}/run` 异步执行；`GET /agents/{id}/status` 状态查询；`POST /agents/{id}/interrupt` 人工中断；SSE 流式事件推送 |
| **S1-3** | Agent 前端可视化 | 16h | Agent 执行过程时序图（Step-by-step）；Thought/Action/Observation 展示；Human-in-the-loop 中断/恢复按钮；重新执行某一步 |

### Sprint 1 验收

- [ ] 支持至少 3 种工作流模式（顺序/分支/循环）
- [ ] Human-in-the-loop 节点可暂停并等待用户输入
- [ ] Agent 执行可视化实时更新
- [ ] 前端时序图展示完整执行链路

---

## Sprint 2：AIP Guardrails + RAG 完善（Week 3-4）

| 编号 | 任务 | 工时 | DoD |
|------|------|------|-----|
| **S2-1** | Guardrails 输入安全 | 16h | Prompt Injection 检测（guardrails-ai）；Toxicity 过滤；禁止话题拦截；审计日志写入 `aip_guardrails_logs` |
| **S2-2** | Guardrails 输出安全 | 12h | 幻觉检测（Ontology 反查数值/实体/时间）；PII 识别与脱敏（presidio 或正则+实体识别）；输出格式校验 |
| **S2-3** | RAG BGE-Reranker 集成 | 16h | BGE-Reranker-v2-m3 重排；查询时实体识别（LLM 提取 Ontology Object Types）；llama-index 集成替换自研逻辑；可解释性输出（来源标注） |
| **S2-4** | Prompt 管理后台 | 20h | Prompt 模板 CRUD；版本管理；A/B 测试标记；使用统计（调用次数、平均 Token）；模板变量注入 |

### Sprint 2 验收

- [ ] 已知攻击模式拒绝率 > 95%
- [ ] PII 脱敏后不可逆
- [ ] RAG 回答附带 ≥ 3 个来源引用
- [ ] Prompt 模板支持变量 + 版本回滚

---

## Sprint 3：ONT 打磨 + APP-F 补全（Week 5-6）

| 编号 | 任务 | 工时 | DoD |
|------|------|------|-----|
| **S3-1** | Interface 异步全量校验 | 12h | Celery 异步校验任务；变更 Interface 后 5 分钟内完成全量重校验；WebSocket 推送校验结果 |
| **S3-2** | Action OPA 集成 | 12h | OPA 服务集成（opa-python 或 HTTP）；Rules 校验在 Action 执行前调用；违反规则返回明确拒绝原因 |
| **S3-3** | Workshop App Builder | 20h | 左侧组件面板（Object Table/Filter/Chart/Action Button/Link Navigator）；画布拖拽布局（XYFlow）；组件属性配置面板（右侧）；组件间数据联动；应用发布与权限分配 |
| **S3-4** | 全局搜索升级 | 12h | 搜索模式切换：Keyword/Semantic/RAG；结果分类：Objects/Documents/LLM Answer；搜索建议（Autocomplete）；搜索历史 |
| **S3-5** | Dashboard 接入真实 API | 8h | Ontology 统计卡片；最近执行 Action 列表；LLM 成本趋势图；30s 自动刷新 |

### Sprint 3 验收

- [ ] Interface 校验结果通过 WebSocket 实时推送
- [ ] OPA Rules 拒绝违规 Action
- [ ] Workshop 拖拽体验 60fps
- [ ] 全局搜索结果页加载 < 1s
- [ ] Dashboard 数据来自真实 API（非 Mock）

---

## Sprint 4：性能 + 测试 + Release v2.3.0（Week 7-8）

| 编号 | 任务 | 工时 | DoD |
|------|------|------|-----|
| **S4-1** | LLM 成本仪表盘 | 12h | 按模型/租户/时间段 Token 消耗统计；成本估算（自定义单价）；预算告警阈值配置；导出 CSV |
| **S4-2** | E2E 集成测试 | 16h | Agent 端到端场景；Guardrails 安全场景；Workshop Builder 场景；Dashboard 数据一致性 |
| **S4-3** | 性能压测与优化 | 12h | k6: Agent API P95 < 2s；RAG 查询 P95 < 2s；Workshop 加载 < 1s；100 并发 0 5xx |
| **S4-4** | 文档 + Release v2.3.0 | 8h | CHANGELOG 更新；API 文档更新（Agent/Guardrails）；部署文档更新；v2.3.0 版本发布 |

### Sprint 4 验收

- [ ] E2E 测试全部通过
- [ ] 性能 NFR 全部达标
- [ ] CI 流水线全部通过
- [ ] v2.3.0 Release 就绪

---

## 里程碑时间线

```
Week 1    Week 2    Week 3    Week 4    Week 5    Week 6    Week 7    Week 8
  |         |         |         |         |         |         |         |
  ├─── S1 ───────────┤         |         |         |         |         |
  | Agent Orchestrator          |         |         |         |         |
  |         |         ├─── S2 ───────────┤         |         |         |
  |         |         | Guardrails + RAG  |         |         |         |
  |         |         |         |         ├─── S3 ───────────┤         |
  |         |         |         |         | ONT + APP-F       |         |
  |         |         |         |         |         |         ├── S4 ───┤
  |         |         |         |         |         |         | Release  |
  ▼         ▼         ▼         ▼         ▼         ▼         ▼         ▼
 M1        M1完成     M2       M2完成     M3       M3完成     M4      v2.3.0
 Agent可用           安全AI              产品完整            性能     Release
```

---

## 模块 v2.3 目标完成度

| 模块 | v2.2 进度 | v2.3 目标 | 新增任务 |
|------|----------|----------|----------|
| FIX | 100% | 100% | — |
| ONT | ~90% | **100%** | Interface 异步校验、OPA 集成 |
| AIP | ~35% | **85%** | Agent、Guardrails、Prompt 管理、RAG 完善 |
| APP-F | ~80% | **100%** | Workshop Builder、搜索升级、Dashboard |
| FDR | 0% | 0% | 延后至 v3.0 |
| INF | ~80% | ~85% | — |

---

## 风险管理

| 风险 | 概率 | 应对 |
|------|------|------|
| LangGraph API 不兼容 FastAPI async | 低 | S1 提前 PoC，必要时 `langchain` 替代 |
| guardrails-ai 依赖冲突 | 中 | 使用自研规则引擎作为后备 |
| XYFlow Workshop 性能不达标 | 低 | 虚拟化长列表，懒加载组件面板 |
| OPA 服务部署复杂度 | 低 | 使用 `opa-python` 库内嵌，不依赖外部 OPA 服务 |

---

## 人员分配

| 角色 | S1 | S2 | S3 | S4 |
|------|----|----|----|----|
| Backend A | S1-1,2 (Agent) | S2-1,2 (Guardrails) | S3-1,2 (ONT) | S4-2 (E2E) |
| Backend B | — | S2-3 (RAG) | — | S4-3 (性能) |
| Frontend A | S1-3 (可视化) | S2-4 (Prompt) | S3-3 (Workshop) | S4-1 (成本) |
| Frontend B | — | — | S3-4,5 (搜索+仪表盘) | S4-2 (E2E) |
| DevOps | — | — | — | S4-3,4 (Release) |

---

> **更新**：每个 Sprint 结束后更新本文件。目标：Week 8 发布 v2.3.0。