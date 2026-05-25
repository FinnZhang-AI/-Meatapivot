# 代码审查报告 — Sprint 1-2 代码审查

> **审查日期**: 2026-05-25  
> **审查范围**: commit `4e60d1e` + `2d204ce`（Sprint 1-2 全部代码变更）  
> **审查准则**: `AGENTS.md` — Karpathy Guidelines + 项目特定指南  
> **审查人**: AI Coding Agent（自检）

---

## 一、Karpathy 准则审查

### 1. Think Before Coding（编码前思考）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 假设是否明确陈述 | ✅ 通过 | 每个任务开始前确认了目标架构 vs 实际代码的差异（通过 `GAP-ANALYSIS.md`） |
| 歧义时是否呈现多种解释 | ⚠️ 改进 | Cypher 白名单设计时直接选择了"白名单+黑名单"方案，未记录 "仅白名单" vs "白名单+黑名单" 的权衡。建议补充注释说明为何需要双重校验 |
| 困惑时是否停下来 | ✅ 通过 | Auth 实现时明确区分了 `OAuth2PasswordBearer` vs Keycloak OIDC 的路径，选择了先实现基础版 |
| 是否提出反对/更简单方案 | ✅ 通过 | RestrictedPython 替代 `subprocess.run()` 时，明确说明了为何选择 Phase 1 方案而非直接上 gVisor |

**建议**：在 `_validate_readonly_cypher` 函数注释中补充设计决策记录：
```python
# Design decision: Whitelist + Blacklist dual validation
# Whitelist prevents unknown query types; Blacklist catches write ops in comments/subqueries
# Tradeoff: slightly slower than whitelist-only, but defense-in-depth for security
```

---

### 2. Simplicity First（简洁优先）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 不添加超出需求的功能 | ⚠️ 改进 | `celery_app.py` 配置了 `timezone="Asia/Shanghai"`——虽然合理但属于"可配置性"超出当前 Sprint 范围。建议用 UTC 减少时区问题 |
| 不为一次性代码做抽象 | ✅ 通过 | `sandbox_restricted.py` 的 `FunctionResult` 类虽然简单但会被多处复用，抽象合理 |
| 不处理不可能场景的错误 | ⚠️ 问题 | `auth.py:87-88` 中 `if username is None: raise credentials_exception` 后紧跟 `except JWTError`，但 JWTError 已经包含了 `username is None` 的情况。`if username is None` 分支理论上不可达（jwt.decode 在 invalid 时会抛 JWTError）。建议保留（防御性编程）但加注释说明 |
| 如果 200 行可以写成 50 行 | ✅ 通过 | `auth.py` 从 89 行增至 177 行，但功能从 Mock 变为真实 Auth，行数增长合理 |

**问题发现**：

1. **`documents.py:97-98` 类型不匹配**：
   ```python
   Document.id == uuid.UUID(document_id),       # UUID 类型 ✅
   Document.uploaded_by == uuid.UUID(current_user.id)  # current_user.id 是 str
   ```
   `current_user.id` 是 `str` 类型（来自 `UserResponse.id: str`），但 `Document.uploaded_by` 是 `UUID` 类型。SQLAlchemy 可能会隐式转换，但这不是类型安全的做法。
   
   **修复建议**：
   ```python
   from uuid import UUID
   Document.uploaded_by == UUID(current_user.id)
   ```

2. **`sandbox_restricted.py:24` `safe_globals` 使用不当**：
   ```python
   **safe_globals.get("__builtins__", {}),
   ```
   `safe_globals` 本身是一个 dict，不是函数。`safe_globals.get(...)` 可能返回 `None` 或 `{}`，但 `safe_globals` 的结构是 `{"__builtins__": {...}, "_getattr_": ...}`。直接解包 `safe_globals` 可能混入非 builtin 的 guard 函数到 builtins 中。
   
   **修复建议**：
   ```python
   ALLOWED_BUILTINS = {
       "len": len, "range": range, ...  # 显式列出
   }
   ```
   或：
   ```python
   from RestrictedPython import safe_builtins
   ALLOWED_BUILTINS = {**safe_builtins, "len": len, ...}
   ```

---

### 3. Surgical Changes（精准修改）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 不改进相邻代码/注释 | ⚠️ 问题 | `knowledge_graph.py` 修改 `_validate_readonly_cypher` 时，保留了旧的 `_CYPHER_WRITE_KEYWORDS` 变量（第 293 行），但未删除旧的黑名单集合（仍作为防御保留）。这是设计意图，但应在注释中说明 |
| 不重构没有坏掉的代码 | ✅ 通过 | 仅修改了与任务直接相关的文件 |
| 匹配现有风格 | ⚠️ 改进 | `auth.py` 重写后完全改变了原有代码结构（从 Mock 变为真实实现），这是合理的，但应注意保留原有 router 的 `prefix` 和 `tags` 配置 |
| 删除改动导致的孤儿代码 | ⚠️ 问题 | `auth.py` 中的 `create_access_token` 函数保留了旧的实现（和原来一样），但新增了 `verify_password`/`get_password_hash`/`get_user_by_username`/`authenticate_user`。旧代码中直接 import 的 `UserResponse` 现在从 database_models 获取——需要确认没有循环导入 |
| 每行变更追溯到用户请求 | ✅ 通过 | 所有变更对应 `GAP-ANALYSIS.md` 中的 P0 项 |

**问题发现**：

3. **循环导入风险**：`auth.py:24` import `User` from `database_models`，而 `database_models.py` 中的 `User` 模型 import 了 `Base` from `database.py`。`auth.py` 通过 `get_db` 使用 `AsyncSession`。虽然当前没有循环，但如果未来 `database_models.py` 需要 import `auth.py` 中的某个类型，就会产生循环导入。

   **建议**：将 `User` 的 Pydantic schema（如 `UserInDB`）放在 `schemas.py` 中，而不是直接从 `database_models.py` import ORM 模型到 router。

4. **`ontology_models.py:315` `onupdate` 不生效**：
   ```python
   updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate="NOW()")
   ```
   SQLAlchemy 2.0 中 `onupdate` 是 client-side 的，但 `server_default` 和 `onupdate="NOW()"` 混用可能导致不一致。建议统一使用：
   ```python
   from sqlalchemy import func
   updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
   ```

---

### 4. Goal-Driven Execution（目标驱动执行）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 强成功标准 | ⚠️ 改进 | 代码实现后未运行测试验证。例如：auth.py 的 bcrypt 功能未验证，`sandbox_restricted.py` 未验证 `os.system` 拦截 |
| 循环验证 | ❌ 缺失 | 没有为新代码编写测试。每个 P0 项应该有至少一个测试 |
| 定义成功标准 | ✅ 通过 | `DEVPLAN-v2.2.md` 中每个 Sprint 都有验收清单 |

**必须补充的测试**（最小集合）：

```python
# tests/test_security.py

async def test_cypher_whitelist_rejects_create(client):
    response = await client.post("/api/v1/knowledge-graph/query", json={
        "cypher_query": "CREATE (n:Test) RETURN n"
    })
    assert response.status_code == 403

async def test_cypher_whitelist_allows_match(client):
    response = await client.post("/api/v1/knowledge-graph/query", json={
        "cypher_query": "MATCH (n) RETURN n LIMIT 10"
    })
    assert response.status_code == 200

async def test_sandbox_rejects_os_system():
    from app.services.sandbox_restricted import execute_restricted
    result = await execute_restricted("import os; os.system('whoami')", {})
    assert not result.success
    assert "SecurityError" in result.error

async def test_auth_register_and_login(client, db):
    # Register
    r = await client.post("/api/v1/auth/register", json={
        "username": "testuser", "email": "test@test.com",
        "password": "testpass123", "tenant_id": "tenant-test"
    })
    assert r.status_code == 201
    
    # Login
    r = await client.post("/api/v1/auth/login", data={
        "username": "testuser", "password": "testpass123"
    })
    assert r.status_code == 200
    assert "access_token" in r.json()
```

---

## 二、项目特定指南审查

### FastAPI lifespan 管理连接

| 检查项 | 状态 | 说明 |
|--------|------|------|
| lifespan 管理 | ⚠️ 改进 | `celery_app.py` 使用了全局变量 `celery_app`，但没有在 FastAPI lifespan 中初始化和关闭。应在 `main.py` lifespan 中添加 Celery 的启动/关闭 |

**建议修改 `main.py`**：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing code ...
    from app.worker.celery_app import celery_app
    # Celery is lazy-loaded, no explicit start needed for producer
    yield
    # cleanup
```

### SQLAlchemy 2.0 + asyncpg

| 检查项 | 状态 | 说明 |
|--------|------|------|
| DeclarativeBase | ✅ 通过 | `database_models.py` + `ontology_models.py` 都使用 `Base` from `database.py` |
| async session | ✅ 通过 | `get_db()` 使用 `async_session_maker` |
| 参数化查询 | ✅ 通过 | `auth.py` 的 `select(User).where(User.username == username)` 是参数化的 |

### Neo4j 参数化查询

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 参数化 Cypher | ✅ 通过 | `knowledge_graph.py:316` 使用了 `{**query_request.parameters, "tenant_id": ...}` |
| Cypher 注入防护 | ✅ 通过 | 新增白名单+黑名单双重校验 |

### 多租户隔离

| 检查项 | 状态 | 说明 |
|--------|------|------|
| tenant_id 过滤 | ⚠️ 改进 | `documents.py:96-98` 查询同时限制了 `uploaded_by == current_user.id`，但没有限制 `tenant_id`。虽然通过 `uploaded_by` 间接实现了隔离，但显式添加 `tenant_id` 更安全 |

**建议**：
```python
from app.models.database_models import User  # to join with tenant
# Or add tenant_id to Document model
```

---

## 三、严重问题清单

| 严重度 | 问题 | 位置 | 修复建议 |
|--------|------|------|----------|
| 🔴 **高** | `documents.py` `uuid.UUID(current_user.id)` 可能抛 `ValueError` | `documents.py:97-98` | 添加 try/except 或在前置校验中验证 UUID 格式 |
| 🔴 **高** | `sandbox_restricted.py` `safe_globals` 解包可能混入 guard 函数 | `sandbox_restricted.py:24` | 使用 `safe_builtins` 替代 `safe_globals` |
| 🟡 **中** | `auth.py` `tenant_id` 硬编码为 `"tenant-default"` | `auth.py:100,164` | 从 JWT payload 或数据库读取真实 tenant_id |
| 🟡 **中** | `OntologyCurrentVersion.updated_at` `onupdate` 不生效 | `ontology_models.py:315` | 使用 `func.now()` 替代字符串 |
| 🟡 **中** | 无测试覆盖 | 全部新代码 | 至少为每个 P0 项写一个单元测试 |
| 🟢 **低** | Celery timezone 硬编码为 `Asia/Shanghai` | `celery_app.py:32` | 使用 `UTC` 或从环境变量读取 |
| 🟢 **低** | `__init__.py` 中的 `if __name__ == "__main__": celery_app.start()` 在 worker 模式下不会被调用 | `worker/__init__.py:10-12` | 删除或改为 `celery -A app.worker worker` 的入口说明 |

---

## 四、代码质量评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **安全性** | 8/10 | 白名单+黑名单、RestrictedPython、bcrypt 都正确实现，但 sandbox 的 builtins 处理有小问题 |
| **正确性** | 7/10 | UUID 类型转换、onupdate、tenant_id 硬编码有瑕疵 |
| **可维护性** | 8/10 | 文档完善、结构清晰，但缺少测试 |
| **简洁性** | 8/10 | 没有过度设计，Celery 配置略冗余 |
| **一致性** | 9/10 | 匹配现有代码风格，使用 logging 而非 print |
| **总体** | **8/10** | 合格，需修复 2 个高严重度问题 + 补充测试 |

---

## 五、修复任务清单

| # | 任务 | 优先级 | 预估 |
|---|------|--------|------|
| 1 | 修复 `safe_globals` → `safe_builtins` | 🔴 P0 | 5min |
| 2 | 修复 `documents.py` UUID 转换错误处理 | 🔴 P0 | 10min |
| 3 | 修复 `ontology_models.py` `onupdate` | 🟡 P1 | 5min |
| 4 | 补充 `tests/test_security.py`（Cypher + Sandbox + Auth） | 🟡 P1 | 2h |
| 5 | 从 JWT payload 读取 tenant_id | 🟡 P1 | 30min |
| 6 | Celery timezone 改为 UTC | 🟢 P2 | 5min |

---

> **审查结论**：代码整体质量合格，符合 Karpathy "简洁优先" 和 "精准修改" 准则。发现 **2 个高严重度问题**（sandbox builtins 处理、UUID 类型转换）需立即修复，**建议补充测试**后再合并到 develop 分支。
