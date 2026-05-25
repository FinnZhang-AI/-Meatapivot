# Meatapivot 开发计划 v2.1

> **版本**：2.1  
> **日期**：2026-05-25  
> **基于**：PRD-v2.1.md + ARCHITECTURE-REVIEW.md + ONTOLOGY-DESIGN-v1.0.md

---

## Sprint 总览

| Sprint | 周期 | 优先级 | 任务数 | 预估工时 | 里程碑 |
|--------|------|--------|--------|----------|--------|
| **S1** | Week 1 | P0 | 3 | 28h | 安全基线通过 |
| **S2** | Week 2 | P1 | 3 | 32h | 基础设施就绪 |
| **S3** | Week 3-4 | P1 | 4 | 64h | 架构重构 |
| **S4** | Week 5-6 | P1 | 5 | 80h | 编译器 v2.1 |
| **S5** | Week 7-8 | P1/P2 | 5 | 72h | 性能达标 |

**总计**：20 个任务 / 276h / 8周

---

## Sprint 1：安全修复（P0）

| 编号 | 任务 | 负责人 | 工时 | DoD |
|------|------|--------|------|-----|
| S1-1 | **移除 .env 并轮换密码** | DevOps | 4h | `.gitignore` 含 `.env`；所有密码已更换 |
| S1-2 | **Cypher 白名单注入防护** | Backend B | 8h | 白名单约束（MATCH/WITH/RETURN/CALL/UNWIND）；参数化；单元测试覆盖注入场景 |
| S1-3 | **RestrictedPython 沙箱** | Backend B | 16h | `os.system/__import__/subprocess` 被拦截；超时 5s 执行；内存 256MB 限制 |

**S1 验收**：安全扫描 0 Critical + 沙箱恶意代码测试通过

### Sprint 1 验收清单

- [ ] `grep -r 'latest' docker-compose*.yml` 返回空（FIX-008 同步完成）
- [ ] `CREATE (n:Test) RETURN n` 被拒绝，返回 403
- [ ] `import os; os.system('whoami')` 被 RestrictedPython 拦截
- [ ] `.env` 不在 `git ls-files` 中

---

## Sprint 2：基础设施（P1）

| 编号 | 任务 | 负责人 | 工时 | DoD |
|------|------|--------|------|-----|
| S2-1 | **Alembic 迁移配置** | Backend A | 8h | `alembic init` + `revision --autogenerate` + CI 集成 |
| S2-2 | **实现真实 Auth 存储** | Backend A | 16h | 注册写入 PostgreSQL；登录返回 JWT；bcrypt 加密；过期返回 401 |
| S2-3 | **Celery Worker 服务** | Backend B | 24h | Worker 消费 RabbitMQ；任务状态可查询；失败自动重试 |

**S2 验收**：`alembic upgrade head` + 注册/登录端到端 + Worker 消费任务

### Sprint 2 验收清单

- [ ] `alembic upgrade head && alembic downgrade base` 全流程通过
- [ ] POST /register → DB 中可查到用户，密码 bcrypt 哈希
- [ ] POST /login → 返回有效 JWT，过期 token → 401
- [ ] Worker 从 RabbitMQ 消费测试任务，状态 PENDING→STARTED→SUCCESS

---

## Sprint 3：架构重构（P1）

| 编号 | 任务 | 负责人 | 工时 | DoD |
|------|------|--------|------|-----|
| S3-1 | **Router/Service/Repository 三层分离** | Backend A + B | 40h | Router 不含 SQLAlchemy 查询；Service 可独立测试；现有测试通过 |
| S3-2 | **TenantMiddleware 注入** | Backend A | 8h | request.state.tenant_id 自动注入；跨租户测试通过 |
| S3-3 | **修复 Document 查询 Mock** | Backend A | 16h | get/search/download 查真实 PostgreSQL + MinIO |
| S3-4 | **修复 Dashboard Mock 数据** | Frontend A | 16h | 仪表盘接入真实 API（ObjectType 统计/Action 执行数/LLM 成本） |

### Sprint 3 验收清单

- [ ] Router 文件无 `select()` / `session.execute()` 等直接数据库操作
- [ ] 跨租户测试：租户 A token 无法访问租户 B 数据
- [ ] `GET /documents/{id}` 返回真实 PostgreSQL 数据
- [ ] Dashboard 数据来自 API（非硬编码）

---

## Sprint 4：Ontology 编译器 v2.1（P1）

| 编号 | 任务 | 负责人 | 工时 | DoD |
|------|------|--------|------|-----|
| S4-1 | **DAG 依赖图** | Backend B | 16h | `dag.py` 实现 Kahn 拓扑排序 + BFS 影响集 + 循环检测 |
| S4-2 | **编译器五模块拆分** | Backend B | 24h | `neo4j_emitter.py` + `schema_emitter.py` + `incremental.py` + `compiler.py` |
| S4-3 | **双阶段验证器** | Backend B | 16h | `static_validator.py`（编译时）+ `runtime_validator.py`（运行时）+ `SchemaRegistry` |
| S4-4 | **版本管理与回滚** | Backend B | 16h | `versioning.py`（semver）+ `ontology_current_version` 表 + rollback 端点 |
| S4-5 | **新增 API 端点** | Backend B | 8h | PATCH ObjectType / compile/logs / compile/rollback / compile/validate |

**S4 验收**：全量编译 < 8s + 增量编译 < 1.5s + DAG 循环检测 + 回滚验证

### Sprint 4 验收清单

- [ ] 循环依赖：A→B→A 编译返回循环路径（非 500）
- [ ] Interface 缺失属性：编译返回 detail 字段
- [ ] 增量编译：修改 1 个 ObjectType，仅重编译受影响节点，affected_count 正确
- [ ] 回滚：`POST /compile/rollback` → Neo4j 约束恢复到目标版本
- [ ] 编译失败：PostgreSQL 数据不变（事务回滚验证）
- [ ] Keycloak 仅用于 IAM（不负责 JWT），二选一

---

## Sprint 5：性能与收尾（P1/P2）

| 编号 | 任务 | 负责人 | 工时 | DoD |
|------|------|--------|------|-----|
| S5-1 | **Prometheus 自定义指标** | Backend B | 8h | `ontology_compile_duration_seconds` 等 5 个 histogram |
| S5-2 | **前端 Vitest 测试** | Frontend B | 16h | 核心组件测试（PropertyTable/RelatedObjects/ActionDialog/Chat） |
| S5-3 | **AIP Guardrails 基础版** | Backend C | 16h | 输入 Prompt Injection 检测 + 输出 PII 脱敏 |
| S5-4 | **Workshop App Builder 骨架** | Frontend A | 16h | XYFlow 画布 + 组件面板（Object Table/Filter/Chart） |
| S5-5 | **性能压测与优化** | All | 16h | k6 压测：P50 < 100ms, P95 < 500ms, 100并发 0 5xx |

**S5 验收**：全部 NFR 达标 + E2E 测试通过

---

## 人员分配

| 角色 | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 | Sprint 5 |
|------|----------|----------|----------|----------|----------|
| Backend A | — | S2-1, S2-2 | S3-1, S3-2, S3-3 | — | S5-5 |
| Backend B | S1-2, S1-3 | S2-3 | S3-1 | S4-1~S4-5 | S5-1, S5-5 |
| Backend C | — | — | — | — | S5-3, S5-5 |
| Frontend A | — | — | S3-4 | — | S5-4, S5-5 |
| Frontend B | — | — | — | — | S5-2, S5-5 |
| DevOps | S1-1 | S2-3（环境） | — | — | — |

---

## 里程碑时间线

```
Week 0  Week 1  Week 2  Week 3  Week 4  Week 5  Week 6  Week 7  Week 8
  |       |       |       |       |       |       |       |       |
  ├─ S1 ──┤                                                       │
  | 安全修复                                                        │
  |       ├─ S2 ─┤                                                 │
  |       |基础设施                                                  │
  |       |       ├────── S3 ──────────┤                           │
  |       |       |   架构重构                                       │
  |       |       |                   ├─────── S4 ────────┤         │
  |       |       |                   |    编译器 v2.1               │
  |       |       |                   |                   ├── S5 ──┤
  |       |       |                   |                   |性能收尾 │
  ▼       ▼       ▼                   ▼                   ▼         ▼
 M0      M1      M2                  M3                  M4        M5
安全   基础    架构                 编译器              性能     v2.1
就绪   就绪    重构                  v2.1               达标     Release
```

---

## 风险管理

| 风险 | 概率 | 应对 |
|------|------|------|
| S3 三层重构工作量超预期 | 中 | 先重构 Object Type 模块验证方案，再推及其他 |
| DAG 算法复杂度高 | 低 | 使用 `networkx` 库作为后备，避免重复造轮子 |
| Celery 与 AsyncPG 兼容性 | 中 | 提前做 PoC，必要时用 `arq` 替代 |
| RestrictedPython 限制过严 | 低 | 维护白名单可扩展，业务代码需调整时快速响应 |

---

> **更新**：每个 Sprint 结束后更新本文件。已完成的 Sprint 标记 ✅ 并记录实际工时。
