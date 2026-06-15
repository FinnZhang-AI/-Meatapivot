# Agent 行为指南 – Meatapivot

> 本文档面向 AI 编码助手，包含项目背景、技术栈、编码风格以及基于 Andrej Karpathy 理念的行为准则。

---

## 项目背景

- **项目名称**：Meatapivot（Meatapivot）
- **定位**：Palantir 的开源替代方案，面向企业级知识管理与决策支持
- **技术栈**：FastAPI + PostgreSQL + Neo4j + Redis + RabbitMQ + MinIO + React + TypeScript + TailwindCSS + Vite
- **架构**：多租户 SaaS 架构，Polyglot Persistence（多态持久化）

详细技术架构请参考同目录下的 `TECH_ARCHITECTURE.md`。

---

## 技术栈速查

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11, FastAPI 0.109.2, SQLAlchemy 2.0.25 (async), Pydantic v2 |
| 前端 | React 18.2, TypeScript 5.3, Vite 5.0, TailwindCSS 3.4, TanStack Query, Zustand |
| 数据库 | PostgreSQL 15, Neo4j 5.15, Redis 7 |
| 中间件 | RabbitMQ 3.12, MinIO (S3), Keycloak 23 |
| 可观测性 | Prometheus, Grafana, Loki, Tempo, OpenTelemetry |
| 部署 | Docker Compose, Kubernetes Ready |

---

## 编码风格

- **Python**：PEP 8，类型注解，异步优先（`async`/`await`），使用 `logging` 而非 `print`
- **TypeScript**：严格模式，接口优先于类型别名，React 函数组件 + Hooks
- **通用**：最小改动原则，不修改与任务无关的代码，保持现有代码风格一致

---

## Karpathy 行为准则（Karpathy Guidelines）

> 以下准则源自 [Andrej Karpathy 对 LLM 编码陷阱的观察](https://x.com/karpathy/status/2015883857489522876)，用于减少常见 AI 编码错误。
>
> **Tradeoff**：这些准则偏向谨慎而非速度。对于简单任务（如明显的拼写错误、单行修复），请自行判断——并非每次修改都需要全套严谨流程。

### 1. Think Before Coding（编码前思考）

**不要假设。不要隐藏困惑。呈现权衡。**

在实现之前：
- **明确陈述你的假设**——如果不确定，提问而不是猜测
- **呈现多种解释**——当存在歧义时，不要默默选择
- **在适当时提出反对**——如果存在更简单的方法，说出来
- **困惑时停下来**——指出不清楚的地方，然后询问

### 2. Simplicity First（简洁优先）

**用最少代码解决问题。不做投机性设计。**

- 不添加超出需求的功能
- 不为一次性代码做抽象
- 不提供未被要求的"灵活性"或"可配置性"
- 不处理不可能场景的错误
- 如果 200 行可以写成 50 行，重写它

**自检**：一位资深工程师会觉得这过于复杂吗？如果是，简化。

### 3. Surgical Changes（精准修改）

**只碰必须碰的。只清理你自己制造的。**

编辑现有代码时：
- 不要"改进"相邻代码、注释或格式
- 不要重构没有坏掉的代码
- 匹配现有风格，即使你自己会做得不同
- 如果注意到无关的死代码，**提及它但不要删除**

当你的改动产生了孤儿代码时：
- 删除**你的改动**导致未使用的 import/变量/函数
- 不要删除预先存在的死代码，除非被要求

**测试标准**：每一行变更都应直接追溯到用户的请求。

### 4. Goal-Driven Execution（目标驱动执行）

**定义成功标准。循环直到验证通过。**

将任务转换为可验证的目标：

| 不要说... | 转换为... |
|-----------|-----------|
| "添加验证" | "为无效输入编写测试，然后让测试通过" |
| "修复 bug" | "编写一个能复现 bug 的测试，然后让测试通过" |
| "重构 X" | "确保重构前后测试都通过" |

对于多步骤任务，陈述一个简要计划：
```
1. [步骤] → 验证: [检查点]
2. [步骤] → 验证: [检查点]
3. [步骤] → 验证: [检查点]
```

**强成功标准**让你能独立循环验证。**弱标准**（如"让它工作"）需要不断澄清。

---

## 项目特定指南

- 后端使用 FastAPI 的 `lifespan` 管理连接，支持降级启动
- 数据库模型使用 SQLAlchemy 2.0 的 DeclarativeBase + asyncpg
- Neo4j 查询必须使用参数化（防止 Cypher 注入）
- 文件上传限制为 `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`, `.jpg`, `.png`
- 所有 API 返回统一 JSON 格式，全局异常处理器已注册
- 多租户隔离通过 `tenant_id` 字段实现
- **OPA / Rego 评估**：`opa-python` 在 PyPI 不存在（DEVPLAN-v2.3 S3-2 写错了）。Sprint 3 已落地内嵌求值器 `app/services/opa_client.py`（自研 Rego 子集解析 + 安全 AST 求值）。如需替换为真实 OPA 服务，只换 evaluator，调用层 (`ActionExecutor`) 不动 — 接口契约是 `OPAClient.evaluate(input_doc) -> PolicyDecision`

---

## 如何知道准则生效了

这些准则生效时，你会看到：

- **diff 中不必要变更更少**——只出现被请求的改动
- **因过度复杂导致的重写更少**——代码第一次就保持简洁
- **澄清问题出现在实现前**——而不是在犯错之后
- **干净、最小化的提交**——没有顺路重构或"改进"

---

*本文件基于 [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) (MIT License) 集成。*
