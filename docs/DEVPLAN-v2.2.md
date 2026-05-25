# Meatapivot 开发计划 v2.2

> **版本**：2.2  
> **日期**：2026-05-25  
> **基于**：`PRD-v2.2.md` + `GAP-ANALYSIS.md`（30 项差异）  
> **周期**：6 个 Sprint / 8 周

---

## Sprint 总览

| Sprint | 周期 | 优先级 | P0 闭合 | 任务数 | 预估工时 | 里程碑 |
|--------|------|--------|---------|--------|----------|--------|
| **S1** | Week 1 | P0 | 2/14 | 4 | 38h | M0a 安全基线 |
| **S2** | Week 2 | P0 | 8/14 | 6 | 56h | M0b 数据模型 |
| **S3** | Week 3-4 | P1 | 14/14 | 7 | 96h | M1 编译器 v2.2 |
| **S4** | Week 5 | P1 | — | 4 | 64h | M2 三层分离 |
| **S5** | Week 6-7 | P1/P2 | — | 5 | 64h | 架构 + API 补全 |
| **S6** | Week 8 | P2 | — | 4 | 40h | M3 性能 + Release |

**总计**：30 任务 / 358h / 8 周 / 14 P0 项闭合

---

## Sprint 1：安全修复（P0 — 4 项）

| 编号 | 任务 | 负责人 | 工时 | DoD | P0 编号 |
|------|------|--------|------|-----|---------|
| S1-1 | **Cypher 白名单注入防护** | Backend B | 8h | 白名单约束（MATCH/WITH/RETURN/CALL/UNWIND）；子查询注入被拒绝；单测覆盖 | P0-SEC-01 |
| S1-2 | **RestrictedPython 沙箱** | Backend B | 16h | `os.system/__import__/subprocess/open/eval` 被拦截；超时 5s；内存 256MB | P0-SEC-02 |
| S1-3 | **移除 .env + 轮换密码** | DevOps | 4h | `.gitignore` 含 `.env`；所有密码已更换 | — |
| S1-4 | **固定 Docker 镜像版本** | DevOps | 4h | `grep -r 'latest' docker-compose*.yml` 返回空 | P2-01 |

### Sprint 1 验收

- [ ] `CREATE (n:Test) RETURN n` → 403
- [ ] `MATCH (n) WHERE n.name = $name RETURN n` → 200（参数化）
- [ ] `import os; os.system('whoami')` → SecurityError
- [ ] `while True: pass` → TimeoutError（5s）
- [ ] `.env` 不在 `git ls-files` 中
- [ ] `grep latest docker-compose*.yml` 返回空

---

## Sprint 2：基础设施 + 数据模型（P0 — 6 项）

| 编号 | 任务 | 负责人 | 工时 | DoD | P0 编号 |
|------|------|--------|------|-----|---------|
| S2-1 | **实现真实 Auth 存储** | Backend A | 16h | 注册写入 PostgreSQL + bcrypt；登录返回 JWT；过期 → 401 | P0-SEC-03 |
| S2-2 | **修复 Document 查询 Mock** | Backend A | 8h | get/search/download 查真实 PostgreSQL + MinIO | P0-SEC-04 |
| S2-3 | **Alembic 迁移配置** | Backend A | 8h | `alembic init` + `revision --autogenerate` + upgrade/downgrade | P0-ARCH-01 |
| S2-4 | **Ontology 编译日志表补字段** | Backend B | 8h | +`version`, `parent_version`, `diff_snapshot`, `neo4j_stmts`, `rolled_back_at` | P0-ONT-03 |
| S2-5 | **Ontology current_version 表** | Backend B | 4h | 每租户一行，`tenant_id PK → version → log_id` | P0-ONT-04 |
| S2-6 | **Celery Worker 服务** | Backend B | 16h | Worker 消费 RabbitMQ；状态可查询；失败重试（3次） | P0-ARCH-02 |

### Sprint 2 验收

- [ ] POST /register → DB 中可查到 bcrypt 哈希密码
- [ ] POST /login → 有效 JWT；过期 token → 401
- [ ] GET /documents/{id} → 返回真实 PostgreSQL 数据
- [ ] `alembic upgrade head && alembic downgrade base` 全流程通过
- [ ] `ontology_compile_logs` 表含 5 个新字段
- [ ] `ontology_current_version` 表存在，CRUD 正常
- [ ] Worker 消费测试任务：PENDING→STARTED→SUCCESS

---

## Sprint 3：Ontology 编译器 v2.2（P1 — 7 项）

| 编号 | 任务 | 负责人 | 工时 | DoD | 关联 P0 |
|------|------|--------|------|-----|---------|
| S3-1 | **DAG 依赖图 + 循环检测** | Backend B | 16h | `dag.py` — Kahn 拓扑排序 + BFS 影响集 + `_find_cycle()` | P0-ONT-01 |
| S3-2 | **编译器五模块拆分** | Backend B | 24h | `neo4j_emitter.py` + `schema_emitter.py` + `incremental.py` + `compiler.py` | P1-01 |
| S3-3 | **双阶段验证器** | Backend B | 16h | `static_validator.py`（编译时）+ `runtime_validator.py`（Pydantic 动态模型） | P0-ONT-02 |
| S3-4 | **SchemaRegistry 缓存** | Backend B | 8h | Redis-backed Pydantic 模型缓存；编译后失效 | P0-ONT-06 |
| S3-5 | **版本管理与回滚端点** | Backend B | 16h | `versioning.py`（semver）+ `POST /compile/rollback` | P0-ONT-05 |
| S3-6 | **编译失败事务回滚** | Backend B | 8h | PostgreSQL 数据不变（Neo4j 失败时回滚） | P0-ONT-07 |
| S3-7 | **编译流水线编排** | Backend B | 8h | 6 阶段流程编译，阶段失败正确阻断 | P1-03 |

### Sprint 3 验收

- [ ] 循环依赖 A→B→A 返回循环路径（非 500）
- [ ] Interface 缺失属性返回 `error_kind="missing_property"` + detail
- [ ] 增量编译 affected_count 正确
- [ ] `POST /compile/rollback` → Neo4j 约束恢复
- [ ] 编译失败 → PostgreSQL 数据不变
- [ ] SchemaRegistry 缓存命中率 > 95%
- [ ] 全量编译 < 8s / 增量 < 1.5s

---

## Sprint 4：三层架构分离（P1 — 4 项）

| 编号 | 任务 | 负责人 | 工时 | DoD | 关联 P0 |
|------|------|--------|------|-----|---------|
| S4-1 | **Object Type 模块三层分离** | Backend A | 16h | `routers/object_types.py` → 仅 HTTP；`services/ontology_service.py` → 业务；`repositories/ontology_repo.py` → DB | P0-ARCH-03 |
| S4-2 | **Link Type + Interface 模块分离** | Backend A | 16h | 同 S4-1 模式，覆盖 link_types + interfaces | P0-ARCH-03 |
| S4-3 | **Action + Function 模块分离** | Backend A | 16h | 同 S4-1 模式，覆盖 actions + functions | P0-ARCH-03 |
| S4-4 | **TenantMiddleware 注入** | Backend A | 8h | `request.state.tenant_id` 自动注入；跨租户测试通过 | P1-11 |

### Sprint 4 验收

- [ ] Router 文件无 `select()` / `session.execute()` 等直接数据库操作
- [ ] Service 层可独立测试（Mock Repository）
- [ ] 跨租户测试：租户 A token 无法访问租户 B 数据
- [ ] 所有现有 API 测试通过

---

## Sprint 5：架构 + API 补全（P1 — 5 项）

| 编号 | 任务 | 负责人 | 工时 | DoD |
|------|------|--------|------|-----|
| S5-1 | **新增 4 个 API 端点** | Backend B | 8h | PATCH ObjectType / GET compile/logs / POST compile/rollback / GET compile/validate |
| S5-2 | **Prometheus 自定义指标** | Backend B | 8h | 5 个 histogram：compile_full, compile_incr, validation, dag_detect, function_exec |
| S5-3 | **Nginx API Gateway** | DevOps | 16h | 独立 Nginx 服务（限流/SSL/路由） |
| S5-4 | **Keycloak OIDC 集成** | Backend A | 16h | SSO 登录流程 + python-keycloak |
| S5-5 | **Dashboard 接入真实 API** | Frontend A | 16h | ObjectType 统计/Action 执行数/LLM 成本 |

### Sprint 5 验收

- [ ] `PATCH /object-types/{id}` 增量更新正确
- [ ] `GET /compile/logs` 分页正确
- [ ] Prometheus 5 个 histogram ALL 有数据
- [ ] Nginx 代理全部 /api 请求
- [ ] Keycloak SSO 登录成功

---

## Sprint 6：性能 + Release（P2 — 4 项）

| 编号 | 任务 | 负责人 | 工时 | DoD |
|------|------|--------|------|-----|
| S6-1 | **性能压测与优化** | All | 16h | k6: P50 < 100ms, P95 < 500ms, 100并发 0 5xx |
| S6-2 | **前端 Vitest 测试** | Frontend B | 16h | PropertyTable/RelatedObjects/ActionDialog/Chat 核心组件 |
| S6-3 | **CI/CD 安全扫描补充** | DevOps | 8h | bandit + semgrep + Trivy + npm/pip audit |
| S6-4 | **文档 + 发布** | All | 8h | API 文档、部署文档更新；v2.2 changelog |

### Sprint 6 验收

- [ ] 性能 NFR 全部达标
- [ ] 前端核心组件单测覆盖率 ≥ 70%
- [ ] CI 流水线全部通过（lint + test + build + security + coverage）
- [ ] 14 项 P0 全部闭合

---

## 人员分配

| 角色 | S1 | S2 | S3 | S4 | S5 | S6 |
|------|----|----|----|----|----|----|
| Backend A | — | S2-1,2,3 | — | S4-1~4 | S5-4 | S6-1 |
| Backend B | S1-1,2 | S2-4,5,6 | S3-1~7 | — | S5-1,2 | S6-1 |
| Backend C | — | — | — | — | — | S6-1 |
| Frontend A | — | — | — | — | S5-5 | S6-1 |
| Frontend B | — | — | — | — | — | S6-2 |
| DevOps | S1-3,4 | S2-6（env） | — | — | S5-3 | S6-3 |

---

## 里程碑时间线

```
Week 0  Week 1  Week 2  Week 3  Week 4  Week 5  Week 6  Week 7  Week 8
  |       |       |       |       |       |       |       |       |
  ├─ S1 ──┤                                                       │
  |安全修复 (4 P0)                                                  │
  |       ├─ S2 ─┤                                                 │
  |       |基础设施 (6 P0)                                           │
  |       |       ├─────── S3 ───────────────┤                     │
  |       |       |  编译器 v2.2 (4 P0闭合)                          │
  |       |       |                       ├─ S4 ──┤                │
  |       |       |                       |三层分离 │                │
  |       |       |                       |       ├─── S5 ────┤     │
  |       |       |                       |       |架构+API 补全│   │
  |       |       |                       |       |           ├ S6 ┤
  |       |       |                       |       |           |Release
  ▼       ▼       ▼                       ▼       ▼           ▼    ▼
 M0a     M0b     M0b完成                  M1      M2          M3  M4
安全   数据模型  12/14 P0闭合            编译器   架构      性能  v2.2
```

---

## P0 闭合追踪

| P0 编号 | 需求 | 目标 Sprint | 状态 |
|---------|------|------------|------|
| P0-SEC-01 | Cypher 白名单 | S1 | ⬜ |
| P0-SEC-02 | RestrictedPython 沙箱 | S1 | ⬜ |
| P0-SEC-03 | 真实 Auth 存储 | S2 | ⬜ |
| P0-SEC-04 | Document 查询真实化 | S2 | ⬜ |
| P0-ARCH-01 | Alembic 迁移 | S2 | ⬜ |
| P0-ARCH-02 | Celery Worker | S2 | ⬜ |
| P0-ARCH-03 | 三层分离 | S4 | ⬜ |
| P0-ONT-01 | DAG 依赖图 | S3 | ⬜ |
| P0-ONT-02 | 双阶段验证器 | S3 | ⬜ |
| P0-ONT-03 | 编译日志字段 | S2 | ⬜ |
| P0-ONT-04 | current_version 表 | S2 | ⬜ |
| P0-ONT-05 | 回滚端点 | S3 | ⬜ |
| P0-ONT-06 | SchemaRegistry | S3 | ⬜ |
| P0-ONT-07 | 编译失败回滚 | S3 | ⬜ |

---

## 风险管理

| 风险 | 概率 | 应对 |
|------|------|------|
| S4 三层重构工作量超预期（40h→可能 60h） | 中 | 先重构 Object Type 验证方案（2d），一致后批量复制 |
| RestrictedPython 限制过严导致业务代码无法运行 | 低 | 维护白名单列表，必要时快速扩充 `ALLOWED_BUILTINS` |
| Celery + AsyncPG 兼容性问题 | 中 | S2 提前做 PoC，必要时 `arq` 替代 |
| DAG 算法性能（100节点）不达标 | 低 | 使用 `networkx` 库作为后备（已在 requirements.txt） |
| Nginx Gateway 与前端 `Dockerfile.prod` nginx 冲突 | 中 | 独立 Nginx 服务替换 frontend 内置 nginx |

---

> **更新**：每个 Sprint 结束后更新本文件。已完成 Sprint 标记 ✅。P0 闭合进度每周汇报。
