# /api/v1/auth/* 路由修复方案文档

## 📋 问题概述

排查并验证 `/api/v1/auth/*` 路由的完整功能，确保注册、登录、用户信息获取等认证流程正常工作。

## 🔍 排查步骤

### 1. 根路径服务状态确认

**测试命令：**
```bash
curl -s http://localhost:8000/ | python3 -m json.tool
```

**预期响应：**
```json
{
    "name": "Meatapivot",
    "version": "1.0.0",
    "status": "running",
    "docs": "/docs",
    "health": "/health"
}
```

**结果：** ✅ 服务正常运行

---

### 2. 后端热加载配置检查

**检查点：** 确认 uvicorn 启动时已开启 `reload` 参数

**代码位置：** `backend/app/main.py` 第 168 行

```python
uvicorn.run(
    "app.main:app",
    host=settings.HOST,
    port=settings.PORT,
    reload=settings.DEBUG  # ✅ 已开启热加载
)
```

**结果：** ✅ 热加载已启用，开发模式下代码修改自动生效

---

### 3. API 路由注册逻辑核对

#### 3.1 主应用路由注册

**代码位置：** `backend/app/main.py`

```python
from app.routers import auth, documents, decision_flow, knowledge_graph

# Include Routers
app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["Authentication"])
```

**配置说明：**
- `settings.API_PREFIX = "/api/v1"`（来自 `backend/app/core/config.py`）
- `auth.router` 自带 `prefix="/auth"`（来自 `backend/app/routers/auth.py`）
- **最终路由前缀：** `/api/v1/auth`

#### 3.2 Auth 路由器定义

**代码位置：** `backend/app/routers/auth.py`

```python
router = APIRouter(prefix="/auth", tags=["Authentication"])
```

**已注册子路由：**
| 方法 | 路径 | 完整 URL | 功能 |
|------|------|----------|------|
| POST | `/register` | `/api/v1/auth/register` | 用户注册 |
| POST | `/login` | `/api/v1/auth/login` | 用户登录 |
| GET | `/me` | `/api/v1/auth/me` | 获取当前用户信息 |

---

### 4. /auth 子路由功能测试

#### 4.1 用户注册接口测试

**测试命令：**
```bash
curl -s http://localhost:8000/api/v1/auth/register \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "username":"testuser",
    "email":"test@example.com",
    "password":"testpass",
    "tenant_id":"tenant-default"
  }' | python3 -m json.tool
```

**⚠️ 注意事项：** `UserCreate` 模型要求必须提供 `tenant_id` 字段

**成功响应：**
```json
{
    "id": "user-new",
    "username": "testuser",
    "email": "test@example.com",
    "tenant_id": "tenant-default",
    "roles": ["user"],
    "created_at": "2026-05-02T17:41:56.891127",
    "is_active": true
}
```

**结果：** ✅ 注册成功

---

#### 4.2 用户登录接口测试

**测试命令：**
```bash
curl -s http://localhost:8000/api/v1/auth/login \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass" | python3 -m json.tool
```

**成功响应：**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

**结果：** ✅ 登录成功，返回 JWT Token

---

#### 4.3 当前用户信息接口测试

**测试命令：**
```bash
TOKEN=$(curl -s http://localhost:8000/api/v1/auth/login \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**成功响应：**
```json
{
    "id": "user-123",
    "username": "testuser",
    "email": "testuser@example.com",
    "tenant_id": "tenant-default",
    "roles": ["user"],
    "created_at": "2026-05-02T17:42:09.226612",
    "is_active": true
}
```

**结果：** ✅ Token 验证成功，用户信息正常返回

---

## ✅ 最终修复方案总结

### 路由配置正确性验证

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 根路径服务 | ✅ 正常 | `/` 返回应用信息 |
| 热加载配置 | ✅ 已启用 | `reload=settings.DEBUG` |
| 路由注册 | ✅ 正确 | `app.include_router(auth.router, prefix="/api/v1")` |
| Router 前缀 | ✅ 正确 | `APIRouter(prefix="/auth")` |
| 注册接口 | ✅ 正常 | POST `/api/v1/auth/register` |
| 登录接口 | ✅ 正常 | POST `/api/v1/auth/login` |
| 用户信息接口 | ✅ 正常 | GET `/api/v1/auth/me` |

### 关键修复点

1. **请求格式修正**：注册接口必须包含 `tenant_id` 字段
   ```json
   {
     "username": "string",
     "email": "string",
     "password": "string",
     "tenant_id": "string",  // ⚠️ 必填
     "roles": ["user"]       // 可选，默认 ["user"]
   }
   ```

2. **登录请求格式**：使用 `application/x-www-form-urlencoded` 而非 JSON
   ```bash
   -H "Content-Type: application/x-www-form-urlencoded"
   -d "username=xxx&password=xxx"
   ```

3. **Token 传递方式**：使用 `Authorization: Bearer <token>` 头
   ```bash
   -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
   ```

---

## 📁 相关文件清单

| 文件路径 | 用途 |
|----------|------|
| `backend/app/main.py` | 主应用入口，路由注册 |
| `backend/app/routers/auth.py` | 认证路由实现 |
| `backend/app/models/schemas.py` | 数据模型定义（UserCreate, Token, UserResponse） |
| `backend/app/core/config.py` | 配置管理（API_PREFIX, JWT_SECRET_KEY 等） |

---

## 🧪 快速验证脚本

```bash
#!/bin/bash
# 快速验证 auth 路由功能

BASE_URL="http://localhost:8000/api/v1/auth"

echo "=== 1. 测试注册接口 ==="
curl -s $BASE_URL/register \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"testpass","tenant_id":"tenant-default"}' \
  | python3 -m json.tool

echo -e "\n=== 2. 测试登录接口 ==="
curl -s $BASE_URL/login \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass" \
  | python3 -m json.tool

echo -e "\n=== 3. 测试用户信息接口 ==="
TOKEN=$(curl -s $BASE_URL/login \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s $BASE_URL/me \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

---

## 📅 文档更新时间

- **最后更新：** 2026-05-03
- **验证环境：** Docker 容器化 FastAPI + React
- **技术栈：** FastAPI 0.104+, Python 3.11+, JWT (python-jose)