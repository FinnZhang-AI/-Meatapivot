# Meatapivot 项目需求文档（PRD）v2.1

> **版本**：2.1  
> **日期**：2026-05-25  
> **状态**：需求评审中  
> **变更**：合并架构审查修复需求 + Ontology 模块详细设计 + 验收标准

---

## v2.0 → v2.1 变更摘要

| 变更类型 | 内容 | 来源 |
|----------|------|------|
| **新增模块** | FIX：架构审查修复（8个 P0/P1 任务） | `ARCHITECTURE-REVIEW.md` |
| **架构升级** | Ontology 编译器五模块拆分 + DAG 依赖图 + 双阶段验证 | `ONTOLOGY-DESIGN-v1.0.md` |
| **架构升级** | Nginx API Gateway + Celery Worker + TenantMiddleware | `ARCHITECTURE-REVIEW.md` |
| **安全加固** | RestrictedPython 沙箱 + Cypher 白名单 + JWT 安全基线 | `ARCHITECTURE-REVIEW.md` |
| **新增端点** | PATCH ObjectType / compile/logs / compile/rollback / compile/validate | `ONTOLOGY-DESIGN-v1.0.md` |
| **数据模型** | ontology_current_version 表 + compile_logs 扩展字段 | `ONTOLOGY-DESIGN-v1.0.md` |
| **验收标准** | 功能/性能/安全/工程质量四维验收 + 测试用例模板 | `ACCEPTANCE.md` |

---

## 1. 项目背景与目标

Meatapivot 是 Palantir 的开源替代方案，面向企业级知识管理与决策支持平台。v2.1 的核心目标是：

1. **补齐架构缺陷**：Nginx Gateway、Celery Worker、TenantMiddleware、Alembic 迁移
2. **安全加固**：RestrictedPython 沙箱、Cypher 白名单、真实 Auth 存储
3. **Ontology 编译器升级**：DAG 依赖图、六阶段流水线、双阶段验证器、版本回滚
4. **完善验收体系**：四维验收标准 + 测试用例模板

---

## 2. 模块完成度评估

| 模块 | v2.0 完成度 | v2.1 目标 |
|------|-----------|----------|
| FIX（架构修复） | —（新增） | 0% → 100% |
| ONT（Ontology 语义层） | ~75% | 75% → 90%（编译器拆分 + 验证器） |
| AIP（AI 平台） | ~20% | 20% → 40%（Agent + Guardrails） |
| APP-F（前端） | ~63% | 63% → 75%（Workshop Builder） |
| FDR（数据层） | 0% | 0%（延后至 v3.0） |
| INF（基础设施） | ~50% | 50% → 80%（Alembic + CI 完善） |

---

## 3. 新增模块：FIX（架构审查修复）

| 编号 | 任务 | 优先级 | 预估 | 验收标准 |
|------|------|--------|------|----------|
| FIX-001 | 移除 `.env` 并轮换密码 | **P0** | 0.5d | `.gitignore` 含 `.env`，密码已更换 |
| FIX-002 | Cypher 白名单注入防护 | **P0** | 1d | `CREATE/DELETE/MERGE` 被拒绝 |
| FIX-003 | RestrictedPython 沙箱 | **P0** | 2d | `os.system/__import__/subprocess` 被拦截 |
| FIX-004 | Alembic 迁移配置 | P1 | 1d | `alembic upgrade head` 成功 |
| FIX-005 | Router/Service/Repository 三层分离 | P1 | 5d | Router 无 SQLAlchemy 查询 |
| FIX-006 | Celery Worker 异步任务服务 | P1 | 3d | Worker 消费 RabbitMQ 任务 |
| FIX-007 | 实现真实 Auth 存储 | P1 | 2d | 注册登录写入 PostgreSQL |
| FIX-008 | 固定 Docker 镜像版本 | P1 | 0.5d | 无 `latest` 标签 |

---

## 4. Ontology 编译器架构升级（ONT-005 扩展）

### 4.1 当前 vs 目标

| 维度 | 当前（v2.0） | 目标（v2.1） |
|------|-------------|-------------|
| 代码结构 | 单文件 `ontology_compiler.py`（378行） | 五模块拆分（dag/neo4j_emitter/schema_emitter/incremental/compiler） |
| 依赖处理 | 平面遍历 | DAG 拓扑排序 + BFS 影响集 |
| 循环检测 | 无 | Kahn 算法 |
| 编译流水线 | 方法离散调用 | 六阶段编排（加载→DAG→验证→生成→Schema→提交） |
| 验证 | Interface 单点校验 | 双阶段验证器（static + runtime）+ SchemaRegistry 缓存 |
| 版本管理 | 无 | 语义版本（major.minor.patch）+ 回滚 |
| 性能 | 全量编译无时间约束 | 全量 < 8s / 增量 < 1.5s |

### 4.2 新增 API 端点

| Method | Path | 功能 |
|--------|------|------|
| PATCH | `/ontology/object-types/{id}` | 增量更新 ObjectType |
| GET | `/ontology/compile/logs` | 编译历史查询 |
| POST | `/ontology/compile/rollback` | 回滚到指定版本 |
| GET | `/ontology/compile/validate` | 干跑验证（不提交） |

### 4.3 新增数据模型

| 表 | 字段 | 用途 |
|----|------|------|
| `ontology_compile_logs` | +`version`, `parent_version`, `diff_snapshot`, `neo4j_stmts` | 版本链 + 审计 |
| `ontology_current_version` | `tenant_id`, `version`, `log_id` | 当前活跃版本 |

---

## 5. 架构基础设施升级（INF 扩展）

### 5.1 API Gateway

```
用户 → Nginx（限流/SSL/路由） → FastAPI
```
- `docker-compose.deploy.yml` 增加独立 Nginx 服务
- 配置限流、SSL 终止、静态文件服务

### 5.2 Celery Worker

```
FastAPI → RabbitMQ → Celery Worker
                        ├── 文档解析
                        ├── 本体编译
                        └── 决策流执行
```
- 新服务：`docker-compose.yml` 添加 worker 服务
- 任务状态可查询（PENDING/STARTED/SUCCESS/FAILURE）
- 自动重试（最多 3 次）

### 5.3 TenantMiddleware

```python
class TenantMiddleware:
    async def __call__(self, request, call_next):
        tenant_id = extract_tenant_from_jwt(request)
        request.state.tenant_id = tenant_id
        return await call_next(request)
```
- 所有资源查询强制携带 tenant_id
- Router 层不再手动提取

---

## 6. 安全加固

| 项目 | v2.0 状态 | v2.1 目标 |
|------|----------|----------|
| Cypher 查询 | 黑名单（过滤写操作关键字） | 白名单（仅允许 MATCH/WITH/RETURN/CALL/UNWIND） |
| Function 沙箱 | `subprocess.run()` 进程隔离 | Phase 1: RestrictedPython |
| Auth 认证 | Mock（硬编码 `user-123`） | 真实 PostgreSQL 存储 + bcrypt |
| JWT Secret | 可能为默认值 | 强制 ≥ 32 字符 |
| 依赖安全 | 部分扫描 | `pip audit` + `npm audit` 0 Critical |

---

## 7. 非功能需求（NFR）更新

| 编号 | 类别 | 需求 | 目标 | 测量方式 |
|------|------|------|------|----------|
| NFR-001 | 性能 | Ontology 全量编译 | < 8s（100类型） | Prometheus histogram |
| NFR-002 | 性能 | Ontology 增量编译 | < 1.5s | P95 |
| NFR-003 | 性能 | 运行时验证 | < 50ms（缓存） | P95 |
| NFR-004 | 性能 | DAG 循环检测 | < 100ms | 100节点 |
| NFR-005 | 安全 | Cypher 注入 | 0 漏洞 | 安全测试 |
| NFR-006 | 安全 | Function 沙箱 | 0 危险调用 | CI lint |
| NFR-007 | 可用性 | 健康检查 | `/health` 含依赖状态 | API |
| NFR-008 | 工程 | 后端测试覆盖率 | ≥ 70% | pytest-cov |

---

## 8. 验收标准（Definition of Done）

### 8.1 功能验收（按模块）

详见 [`ACCEPTANCE.md`](ACCEPTANCE.md)，关键验收项：

| 模块 | 验收项 | 通过标准 |
|------|--------|----------|
| Ontology | Object Type CRUD | 全流程无报错，Neo4j 约束自动生成 |
| | Interface 验证 | 未实现时返回明确错误 |
| | 编译器 DAG | 循环依赖返回完整路径 |
| | 版本回滚 | Neo4j 约束恢复到目标版本 |
| | Function 沙箱 | `os.system()` 被拦截 |
| Auth | JWT 认证 | 过期 token 返回 401 |
| | 用户存储 | bcrypt 加密存储 |
| Security | Cypher 查询 | 写操作返回 403 |
| | 跨租户 | 租户A不能访问租户B数据 |

### 8.2 性能验收

| 指标 | 目标 | 测量 |
|------|------|------|
| API P95 | < 500ms | k6 |
| 并发 100 | 0 5xx | k6 |
| 知识图谱 5跳 | < 3s | 专项 |
| 全量编译 | < 8s | Prometheus |

### 8.3 安全验收

| 检查项 | 标准 |
|--------|------|
| `.env` 不在 Git | `git ls-files` 返回空 |
| JWT Secret ≥ 32 字符 | 配置检查 |
| 依赖 0 Critical | `pip audit` |
| Cypher 白名单 | 参数化 + 关键字校验 |

### 8.4 工程质量验收

| 检查项 | 目标 |
|--------|------|
| 后端测试覆盖率 | ≥ 70% |
| API 文档完整性 | 所有端点有描述 |
| CI 全部通过 | lint + test + build + security |
| Alembic 迁移 | `upgrade head` 成功 |

---

## 9. 实施计划

### 9.1 Sprint 划分

| Sprint | 优先级 | 任务 | 预估 | 里程碑 |
|--------|--------|------|------|--------|
| **S1** | P0 | FIX-001~003（.env + Cypher + 沙箱） | 3.5d | 安全基线通过 |
| **S2** | P0/P1 | FIX-004,007（Alembic + Auth） | 3d | 数据库迁移 + 真实认证 |
| **S3** | P1 | FIX-005,006（三层分离 + Celery）+ ONT-DAG | 8d | 架构重构里程碑 |
| **S4** | P1 | ONT-Compiler 拆分 + 双阶段验证器 + 版本回滚 | 10d | 编译器重构完成 |
| **S5** | P1/P2 | ONT-增量编译 + FIX-008 + AIP Agent + Guardrails | 10d | 增量编译 + AI 基础 |

### 9.2 里程碑

| 里程碑 | Sprint | 验收方式 |
|--------|--------|----------|
| M0：安全修复就绪 | S1 | 安全扫描 0 Critical |
| M1：基础设施就绪 | S2 | Alembic + Auth + Celery |
| M2：架构重构 | S3-S4 | 三层分离 + 编译器拆分 |
| M3：编译器 v2.1 | S4 | DAG + 验证器 + 回滚 |
| M4：性能达标 | S5 | 全量 < 8s / 增量 < 1.5s |
| M5：v2.1 Release | S5+ | 全部验收通过 |

---

## 10. 参考文档

| 文档 | 用途 |
|------|------|
| [`ARCHITECTURE-REVIEW.md`](ARCHITECTURE-REVIEW.md) | 架构审查报告与修复清单 |
| [`ONTOLOGY-DESIGN-v1.0.md`](ONTOLOGY-DESIGN-v1.0.md) | Ontology 模块详细设计 |
| [`ACCEPTANCE.md`](ACCEPTANCE.md) | 验收标准与测试用例 |
| [`TASKS.md`](TASKS.md) | 任务拆分与跟踪 |
| [`PROGRESS.md`](PROGRESS.md) | 进度报告 |

---

> **维护**：本 PRD 由产品经理维护。v2.1 新增内容来自架构审查和 Ontology 详细设计两个文档。所有 P0 安全修复应在正式发版前完成。
