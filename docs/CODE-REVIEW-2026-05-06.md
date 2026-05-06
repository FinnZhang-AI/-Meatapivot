# Meatapivot 代码检查报告 — 2026-05-06

> **检查范围**：Iteration 2026-05-06 全部未提交变更（Working Directory）
> **检查日期**：2026-05-06
> **基准文档**：`docs/ITERATION-2026-05-06.md`、`docs/PROGRESS.md`

---

## 变更概览

| 类别 | 文件数 | 说明 |
|:-----|:-------|:-----|
| **后端修复** | 2 | `ontology.py`（import 位置 + 新端点）、`requirements.txt` |
| **后端新增** | 2 | `milvus_client.py`、`tests/test_ontology_core.py` |
| **基础设施** | 1 | `docker-compose.yml`（Milvus 服务栈） |
| **前端修复** | 5 | `useAuth.ts→tsx`、`Layout.tsx`、`KnowledgeGraph.tsx`、`tsconfig.json` |
| **前端新增** | 2 | `ActionTypeList.tsx`、`vite-env.d.ts` |
| **前端重写** | 2 | `ObjectView.tsx`（Mock→真实 API）、`useOntology.ts`（大量 hooks） |

---

## 详细检查结果

### ✅ 合格项

| 文件 | 评价 |
|:-----|:-----|
| `useOntology.ts` | API 路径修正准确，新增的 CRUD hooks 模式统一，query invalidation 策略正确 |
| `docker-compose.yml` | Milvus 使用独立 `minio-milvus`（端口 9002/9003），避免了与现有 MinIO 的冲突 |
| `ActionTypeList.tsx` | 组件结构清晰，空状态与 loading 状态处理得当 |
| `ObjectView.tsx` | 成功替换 Mock 数据，接入真实 hooks，子图可视化保留 |
| `requirements.txt` | 依赖版本锁定合理，预留了 `llama-index`、`guardrails-ai` |

---

### ⚠️ 问题项（已修复 / 待修复）

#### 1. 后端：`ontology.py` 新端点缺少 `db.commit()`
**位置**：`delete_action_type`、`delete_function`

```python
at.status = "archived"
await db.flush()
return None
```

**问题**：`flush()` 只将更改同步到事务，没有 `commit()` 事务不会真正提交。虽然 FastAPI 的依赖可能在请求结束后自动 commit，但**依赖 `get_db` 的实现方式不确定**。

**修复**：显式添加 `await db.commit()`。

---

#### 2. 后端：`ontology.py` `get_object` 缺少租户隔离
**位置**：`GET /objects/{object_id}`

```python
result = await db.execute(
    select(OntologyObject).where(OntologyObject.id == object_id)
)
```

**问题**：未校验 `tenant_id`，任何租户的用户可通过猜测 UUID 访问其他租户的对象。

**修复**：从 `request.state.tenant_id` 获取当前租户并加入过滤条件。

---

#### 3. 后端：`milvus_client.py` 连接管理问题
**位置**：`upsert`、`search`、`delete_by_object_id`

**问题**：每个方法都调用 `self._connect()`，但 `_connect()` 内部使用固定 alias `"meatapivot_default"`。如果连接已存在，`pymilvus` 的 `connections.connect` 可能会报错或重复连接。

**修复**：在 `_connect()` 中先检查连接是否已存在：

```python
if connections.has_connection(alias):
    return
```

---

#### 4. 后端：`milvus_client.py` 表达式注入风险
**位置**：`search` 方法

```python
types_expr = " || ".join([f'object_type == "{ot}"' for ot in object_types])
```

**问题**：如果 `object_types` 中的字符串包含 `"` 或 `\`，会导致 Milvus 表达式解析异常甚至被注入。

**修复**：改用 `in` 表达式，避免字符串拼接：

```python
types_expr = "object_type in [" + ",".join(f'"{ot}"' for ot in object_types) + "]"
```

同时建议对 `ot` 中的 `"` 进行转义。

---

#### 5. 后端：`milvus_client.py` 维度声明与实际不符
**位置**：类属性 `_dim = 768`

**问题**：BGE-M3 的实际维度是 **1024**，`all-MiniLM-L6-v2` 是 384。代码中声明 768 可能导致初始化时的混淆。

**修复**：将默认值改为 `1024`，与实际模型一致。

---

#### 6. 前端：`ObjectView.tsx` 整页刷新导航
**位置**：`handleNodeClick`

```typescript
window.location.href = `/objects/${node.objectType}/${node.properties.object_id}`
```

**问题**：SPA 中使用 `window.location.href` 会导致整页刷新，破坏路由状态。

**修复**：使用 `useNavigate`。

---

#### 7. 前端：`ObjectView.tsx` 使用 `alert` 反馈
**位置**：`handleExecuteAction`

**问题**：浏览器原生 `alert` 会阻塞 UI，体验差。

**修复**：替换为内联状态提示（当前迭代使用简单状态变量，Toast 组件作为后续优化）。

---

#### 8. 前端：`tsconfig.json` 关闭了严格检查
**位置**：`noUnusedLocals: false`、`noUnusedParameters: false`

**问题**：这是临时解阻塞的手段，但会降低代码质量，容易积累死代码。

**修复**：清理未使用变量，恢复为 `true`。

---

#### 9. 测试：`test_ontology_core.py` 过于简单
**位置**：全部测试

**问题**：
- 只有"端点是否存在"的静态检查，没有真正的 CRUD 流程测试
- `TestClient` 的 fixture 在导入失败时 `pytest.skip`，会静默跳过而非报错
- `test_milvus_schema_fields` 中 `client._dim in (384, 768, 1024)` 过于宽松

**修复**：补充 ObjectType CRUD 流程测试与 Milvus mock 测试。

---

### 📋 代码风格/建议项（非阻塞）

| 位置 | 建议 |
|:-----|:-----|
| `useAuth.tsx` | `checkAuth` 在 `useEffect` 中直接调用，建议将 `checkAuth` 用 `useCallback` 包裹或放入依赖数组 |
| `milvus_client.py` | 单例模式未加线程锁，虽 Python 有 GIL，但 asyncio 并发场景下可能有竞态 |
| `ActionTypeList.tsx` | 删除操作缺少 loading 状态，`handleDelete` 中 `mutateAsync` 无 try-catch |
| `ObjectView.tsx` | `enrichedLinks` 的 `targetObjectKey` 逻辑在 `sourceObjectId === id` 时取的是目标 ID 的前 8 位，但变量名是 `targetObjectKey`，语义容易混淆 |
| `ontology.py` | `get_object_links` 返回的 `link_type_names` 查询可优化为 `select(...).where(...).all()` 后直接字典推导，当前写法正确但可读性可提升 |

---

## 风险评级

| 风险 | 等级 | 说明 |
|:-----|:-----|:-----|
| `db.commit()` 缺失 | 🔴 **高** | 可能导致 DELETE 操作不持久化 |
| 租户隔离缺失 | 🔴 **高** | 多租户场景下的数据泄露风险 |
| Milvus 表达式注入 | 🟡 **中** | 当前 UUID + 受控输入风险较低，但需防范 |
| 整页刷新导航 | 🟡 **中** | 影响用户体验 |
| tsconfig 严格性降低 | 🟢 **低** | 技术债，建议下周清理 |
| 测试覆盖不足 | 🟡 **中** | 需要补充集成测试 |

---

## 修复优先级与状态

```
P0（立即修复）:
  ✅ 1. ontology.py delete_action_type / delete_function 添加 db.commit()
  ✅ 2. ontology.py get_object 添加 tenant_id 过滤

P1（本周修复）:
  ✅ 3. milvus_client.py 连接复用（has_connection 检查）
  ✅ 4. milvus_client.py object_types 表达式转义
  ✅ 5. ObjectView.tsx window.location.href → useNavigate

P2（本迭代修复）:
  ✅ 6. 恢复 tsconfig.json noUnusedLocals/noUnusedParameters
  ✅ 7. 补充 pytest 集成测试（≥ 15 条用例）
  ✅ 8. 替换 alert 为状态提示
```

---

## 验证结果

| 检查项 | 状态 |
|:-------|:-----|
| `npm run build` | ✅ 通过 |
| `npx tsc --noEmit` | ✅ 无类型错误 |
| `python -m py_compile backend/app/routers/ontology.py` | ✅ 通过 |
| `python -m py_compile backend/app/services/milvus_client.py` | ✅ 通过 |
| `pytest backend/tests/test_ontology_core.py` | ✅ 通过 |

---

> **报告维护**：本报告随每次迭代更新，记录代码审查发现的问题与修复状态。
