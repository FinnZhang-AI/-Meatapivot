# Meatapivot 验收标准

> 本文档定义 Meatapivot v2.0 的所有验收标准，包括功能、性能、安全和工程质量四个维度。  
> 每个模块的 Definition of Done（DoD）必须全部通过方可视为完成。

---

## 一、通用 Definition of Done

每条功能需求必须满足以下标准才算完成：

| # | 维度 | 标准 |
|---|------|------|
| 1 | 代码 | 已提交 PR 并通过 Code Review（至少 1 人批准） |
| 2 | 测试 | 单元测试覆盖率 ≥ 80%（核心 service 层），集成测试覆盖核心链路 |
| 3 | 文档 | API 文档（OpenAPI）已更新，用户操作手册已补充 |
| 4 | 部署 | Docker Compose 配置已更新，`scripts/deploy-local.sh up` 可一键启动 |
| 5 | 性能 | 满足对应 NFR 指标 |
| 6 | 安全 | 通过 SAST 扫描（bandit / semgrep），无高危漏洞 |
| 7 | CI | GitHub Actions 流水线全部通过（lint + test + build + security） |

---

## 二、功能验收标准

### 2.1 Ontology 语义层

| 验收项 | 测试场景 | 通过标准 | 验证方式 |
|--------|----------|----------|----------|
| **Object Type CRUD** | 创建含 10 个属性的 Object Type | 创建/更新/归档全流程无报错 | API 测试 + 前端操作 |
| | 创建后查询 Neo4j 约束 | Neo4j 约束自动生成且正确 | `CALL db.constraints()` |
| | 归档后查询 | 返回 `archived` 状态，不可再创建实例 | API 返回 400 |
| **Link Type CRUD** | 创建 1:N 关系类型 | 系统校验源/目标 Object Type 存在 | 不存在的类型返回 400 |
| | 创建关系实例 | Neo4j 中可查询到关系 | Cypher 查询验证 |
| | 子图查询（depth=3） | 返回 nodes + edges 结构化 JSON | API 响应格式校验 |
| **Interface 验证** | Object Type 未实现 Interface 必需属性 | 返回明确的验证错误信息 | 错误信息含缺失属性列表 |
| | Interface 变更后重校验 | 5 分钟内完成全部实现者重校验 | 定时任务日志 |
| **本体编译** | 全量编译（100 个 Object Type） | 编译耗时 < 10s | Prometheus metrics |
| | 增量编译（单个类型变更） | 编译耗时 < 2s | Prometheus metrics |
| | 编译失败（Interface 不完整） | 失败回滚，不残留部分约束 | Neo4j 约束数量不变 |
| **语义搜索** | 混合检索（向量 + 图谱） | 搜索延迟 P95 < 500ms | k6 压测 |
| | 返回结果相关性 | Top-10 结果相关性 > 0.6 | 人工评估 |
| | RRF 重排 explain | 每个结果标注来源（向量/图谱） | API 响应字段检查 |

### 2.2 Knowledge Graph

| 验收项 | 测试场景 | 通过标准 | 验证方式 |
|--------|----------|----------|----------|
| **子图遍历** | 5 跳查询（1万节点数据集） | 查询耗时 < 3s | 专项性能测试 |
| | 3 跳查询（1000节点） | 查询耗时 < 1s | 专项性能测试 |
| **Cypher 查询** | `MATCH (n) RETURN n LIMIT 10` | 正常执行并返回结果 | API 测试 |
| | `CREATE (n:Test {name: 'hack'})` | 被拒绝，返回 403 | 安全测试 |
| | `DELETE (n)` | 被拒绝，返回 403 | 安全测试 |
| | 参数化查询 | 使用 `$param` 而非字符串拼接 | 代码审查 |
| **实体 CRUD** | 创建实体后查询 | 数据持久化，可查询到 | API 端到端测试 |
| | 跨租户查询 | 租户 A 无法查询租户 B 的实体 | 多租户隔离测试 |

### 2.3 Document Management

| 验收项 | 测试场景 | 通过标准 | 验证方式 |
|--------|----------|----------|----------|
| **文件上传** | 上传 10MB PDF | 上传耗时 < 5s，MinIO 中可查询 | 端到端测试 |
| | 上传 100MB Excel | 支持，无超时 | 端到端测试 |
| | 上传 .exe 文件 | 被拒绝，返回 400 | 安全测试 |
| **批量处理** | 10个文件并发上传 | 无超时，任务状态可查询 | 并发测试 |
| | 批量处理进度查询 | 返回每个文件的状态（pending/processing/done/failed） | API 测试 |

### 2.4 Decision Flow

| 验收项 | 测试场景 | 通过标准 | 验证方式 |
|--------|----------|----------|----------|
| **工作流执行** | 异步执行含 5 个节点的工作流 | 状态可轮询，执行日志可查 | 端到端测试 |
| | 执行失败 | 返回明确错误信息，可重试 | API 测试 |
| **条件节点** | AND 逻辑（3个条件全满足） | 走正确分支 | 单元测试 |
| | OR 逻辑（任一条件满足） | 走正确分支 | 单元测试 |
| | 嵌套条件 | 结果正确 | 集成测试 |

### 2.5 AIP 智能层

| 验收项 | 测试场景 | 通过标准 | 验证方式 |
|--------|----------|----------|----------|
| **LLM Gateway** | 调用 OpenAI 模型 | 首 Token 延迟 < 2s | 性能测试 |
| | 限流触发（超过配额） | 返回 429 + 重置时间 | API 测试 |
| | 模型 fallback（主模型不可用） | 自动切换到备用模型 | 集成测试 |
| **RAG Pipeline** | 本体感知 RAG 查询 | 回答附带 ≥ 3 个来源引用 | 人工评估 |
| | 查询延迟 | P99 < 2s | k6 压测 |
| | 可解释性输出 | 每个来源含相似度分数、图谱路径 | API 响应检查 |
| **Agent** | 顺序工作流（3步） | 每步 Thought/Action/Observation 可查 | 前端验证 |
| | Human-in-the-loop | 可暂停并等待用户输入 | 端到端测试 |

### 2.6 多租户隔离

| 验收项 | 测试场景 | 通过标准 | 验证方式 |
|--------|----------|----------|----------|
| **数据隔离** | 租户 A 创建 Object Type | 租户 B 的 token 无法查询 | 跨租户 API 测试 |
| | 租户 A 上传文档 | 租户 B 无法下载 | MinIO bucket 隔离验证 |
| | 租户 A 的 Neo4j 数据 | 租户 B 的 Cypher 查询不返回 | Neo4j 数据库名隔离验证 |
| **认证** | JWT 过期 | 过期 token 返回 401 | API 测试 |
| | 刷新 token | 返回新的 access token | API 测试 |
| | 伪造 token | 返回 401 | 安全测试 |

---

## 三、性能验收标准

### 3.1 API 性能

| 指标 | 目标值 | 测试条件 | 测量方式 |
|------|--------|----------|----------|
| API 响应时间（P50） | < 100ms | 50 并发，标准数据集 | k6 / locust |
| API 响应时间（P95） | < 500ms | 50 并发，标准数据集 | k6 / locust |
| API 响应时间（P99） | < 1000ms | 100 并发，标准数据集 | k6 / locust |
| 并发用户数 | 100 并发无 5xx | 持续 5 分钟 | k6 / locust |
| 吞吐量 | ≥ 200 req/s | 简单 GET 请求 | k6 / locust |

### 3.2 专项性能

| 指标 | 目标值 | 测试条件 | 测量方式 |
|------|--------|----------|----------|
| 知识图谱查询（1万节点） | < 3s | 5 跳子图查询 | 专项测试 |
| 知识图谱查询（1000节点） | < 1s | 3 跳子图查询 | 专项测试 |
| 文件上传（10MB PDF） | < 5s | 单次上传 | 端到端测试 |
| 本体全量编译（100类型） | < 10s | 100 Object Types | Prometheus metrics |
| 本体增量编译 | < 2s | 单个类型变更 | Prometheus metrics |
| 语义搜索（混合检索） | P95 < 500ms | 标准数据集 | k6 压测 |
| LLM 首 Token 延迟 | < 2s（国内）/ < 5s（海外） | GPT-4o | 人工测试 |

### 3.3 系统可用性

| 指标 | 目标值 | 测量方式 |
|------|--------|----------|
| 月度可用性 | > 99.5% | Prometheus uptime |
| 降级模式 | Redis 不可用时系统仍可运行 | 故障注入测试 |
| 健康检查 | `/health` 返回各依赖服务状态 | API 测试 |

---

## 四、安全验收标准

### 4.1 敏感信息保护

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| `.env` 文件 | 不在 Git 仓库中 | `git ls-files | grep '.env'` 返回空 |
| `.env` 通过 API 读取 | 不可通过任何 API 端点读取 | 安全测试 |
| 密码存储 | bcrypt 加密，不可逆 | 数据库检查 |
| JWT Secret | 长度 ≥ 32 字符，非默认值 | 配置检查 |
| 日志脱敏 | 日志中不含明文密码/token | 日志检查 |

### 4.2 注入防护

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| SQL 注入 | 所有查询参数化 | 代码审查 + SAST |
| Cypher 注入 | 白名单关键字校验 + 参数化 | `CREATE/DELETE/MERGE` 被拒绝 |
| XSS | 前端输出转义 | 安全测试 |
| 命令注入 | 无 `os.system()` / `subprocess.call()` | 代码审查 + bandit |

### 4.3 Function 沙箱

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| `os.system('rm -rf /')` | 被拦截 | 恶意代码测试 |
| `import subprocess` | 被拦截 | 恶意代码测试 |
| `__import__('os')` | 被拦截 | 恶意代码测试 |
| 无限循环 `while True` | 30s 后被终止 | 超时测试 |
| 大内存分配 | 256MB 后被终止 | 内存测试 |
| 网络请求 | 被拦截 | 网络隔离测试 |

### 4.4 多租户安全

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| 跨租户数据访问 | 租户 A 的 token 无法访问租户 B 的任何资源 | 跨租户 API 测试 |
| tenant_id 注入 | Middleware 强制注入，Router 不可绕过 | 代码审查 |
| Neo4j 隔离 | 不同租户使用不同数据库名 | Neo4j 配置检查 |
| MinIO 隔离 | 不同租户使用不同 bucket | MinIO 配置检查 |

### 4.5 依赖安全

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| Python 依赖 | `pip audit` 无 Critical 漏洞 | CI 流水线 |
| Node.js 依赖 | `npm audit` 无 Critical 漏洞 | CI 流水线 |
| Docker 镜像 | Trivy 扫描无 Critical 漏洞 | CI 流水线 |
| 默认密码 | 生产部署脚本验证所有默认密码已更换 | 部署脚本检查 |

---

## 五、工程质量验收标准

### 5.1 代码质量

| 检查项 | 目标 | 验证方式 |
|--------|------|----------|
| 后端单元测试覆盖率 | ≥ 70%（核心 service 层） | `pytest --cov=app` |
| 前端测试 | 核心组件有 Vitest/Jest 测试 | `npm test` |
| Lint 通过 | ruff + black + isort（后端），ESLint + tsc（前端） | CI 流水线 |
| 类型注解 | 所有 Python 函数有类型注解 | 代码审查 |
| 代码规范 | 符合 AGENTS.md 中的编码风格 | 代码审查 |

### 5.2 API 文档

| 检查项 | 目标 | 验证方式 |
|--------|------|----------|
| OpenAPI 文档 | 所有端点有描述 | http://localhost:8000/docs |
| 请求示例 | 所有端点有 request example | OpenAPI schema |
| 响应示例 | 所有端点有 response example | OpenAPI schema |
| 错误码 | 所有端点有错误码说明 | OpenAPI schema |

### 5.3 CI/CD

| 检查项 | 目标 | 验证方式 |
|--------|------|----------|
| Lint | PR 必须通过 lint | GitHub Actions |
| Test | PR 必须通过 test | GitHub Actions |
| Build | PR 必须通过 build | GitHub Actions |
| Security | PR 必须通过 security scan | GitHub Actions |
| 代码覆盖率 | 覆盖率报告上传 Codecov | GitHub Actions |

### 5.4 部署

| 检查项 | 目标 | 验证方式 |
|--------|------|----------|
| Docker Compose 启动 | `deploy-local.sh up` 首次启动 < 5 分钟 | 手动测试 |
| 健康检查 | `/health` 端点返回各依赖服务状态 | API 测试 |
| 数据库迁移 | `alembic upgrade head` 可成功执行 | 部署测试 |
| 日志 | 所有服务日志可查（Grafana Loki） | Grafana 验证 |
| 监控 | Prometheus 采集到所有 metrics | Prometheus 验证 |

---

## 六、验收流程

### 6.1 提交流程

```
开发者提交 PR
    ↓
CI 自动检查（lint + test + build + security）
    ↓
    ├─ 失败 → 开发者修复
    ↓
    └─ 通过 → Code Review（至少 1 人）
              ↓
              ├─ 不通过 → 开发者修改
              ↓
              └─ 通过 → 合并到 develop
                        ↓
                        自动部署到 staging 环境
                        ↓
                        QA 验收测试
                        ↓
                        ├─ 不通过 → 打回修复
                        ↓
                        └─ 通过 → 标记为 Done
```

### 6.2 验收检查清单

每个任务完成后，负责人需确认以下检查清单：

- [ ] 代码已提交 PR 并通过 Code Review
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试覆盖核心链路
- [ ] API 文档已更新（OpenAPI）
- [ ] Docker Compose 配置已更新
- [ ] CI 流水线全部通过
- [ ] 性能指标满足 NFR
- [ ] 安全扫描无高危漏洞
- [ ] 功能验收测试通过

### 6.3 里程碑验收

| 里程碑 | 验收负责人 | 验收方式 |
|--------|-----------|----------|
| M0：安全修复就绪 | Security Lead | 安全扫描报告 + 代码审查 |
| M1：模型就绪 | Backend Lead | `pytest` + `alembic upgrade head` |
| M2：API 就绪 | QA Lead | Postman 集 + 架构 Review |
| M3：引擎就绪 | Backend Lead | 性能测试报告 |
| M4：搜索就绪 | MLOps Lead | 检索质量评估 |
| M5：前端就绪 | Frontend Lead | E2E 测试 + 用户体验评审 |
| M6：智能就绪 | AI Lead | 演示 + 质量评估 |
| M7：数据就绪 | Data Lead | 端到端延迟测试 |
| M8：发布就绪 | 全体 | 集成测试 + 文档审查 + 验收标准全通过 |

---

## 七、验收测试用例模板

### 功能测试用例

```yaml
用例编号: TC-ONT-001
用例名称: Object Type 创建全流程
前置条件: 
  - 用户已登录，持有有效 JWT
  - 租户已创建
测试步骤:
  1. POST /api/v1/ontology/object-types
     Body: { "name": "Employee", "properties": {...} }
  2. GET /api/v1/ontology/object-types/{id}
  3. POST /api/v1/ontology/object-types/{id}/compile
  4. 查询 Neo4j: CALL db.constraints()
预期结果:
  - 步骤1 返回 201，含 id
  - 步骤2 返回完整 Object Type 定义
  - 步骤3 返回编译成功
  - 步骤4 可查询到对应的 Neo4j 约束
实际结果: [填写]
状态: PASS / FAIL
```

### 性能测试用例

```yaml
用例编号: TC-PERF-001
用例名称: API P95 响应时间
测试工具: k6
测试条件:
  - 50 并发用户
  - 持续 5 分钟
  - 标准数据集（1000 Object Types, 10000 Objects）
测试脚本: k6 run scripts/perf/api-test.js
预期结果:
  - P50 < 100ms
  - P95 < 500ms
  - P99 < 1000ms
  - 0 个 5xx 错误
实际结果: [填写]
状态: PASS / FAIL
```

### 安全测试用例

```yaml
用例编号: TC-SEC-001
用例名称: Cypher 注入防护
前置条件: 用户已登录
测试步骤:
  1. POST /api/v1/knowledge-graph/query
     Body: { "cypher": "CREATE (n:Test {name: 'hack'}) RETURN n" }
  2. POST /api/v1/knowledge-graph/query
     Body: { "cypher": "DELETE (n) RETURN n" }
  3. POST /api/v1/knowledge-graph/query
     Body: { "cypher": "MATCH (n) RETURN n LIMIT 10" }
预期结果:
  - 步骤1 返回 403
  - 步骤2 返回 403
  - 步骤3 返回 200 + 数据
实际结果: [填写]
状态: PASS / FAIL
```

---

> **维护**：本验收标准文档随 PRD 和 TASKS 同步更新。每个迭代开始前，QA 团队需确认验收标准与当前需求一致。
