# 智能问答平台

# 接口设计规范

**文档编号：** RAG-QA-STD-005  
**版本号：** V1.0  
**编制部门：** 信息技术部  
**发布日期：** 2026年07月30日  
**密级：** 内部公开  

---

**修订记录**

| 版本号 | 修订日期 | 修订内容 | 作者 | 审核人 |
|--------|----------|----------|------|--------|
| V1.0 | 2026-07-30 | 初始版本 | AI辅助 | 待确认 |

---

**分发范围：** 项目开发团队  
**引用规范：** Microsoft REST API Guidelines  

---

## 目录

1. [基础约定](#1-基础约定)
2. [URL设计规范](#2-url设计规范)
3. [请求规范](#3-请求规范)
4. [响应规范](#4-响应规范)
5. [错误码规范](#5-错误码规范)
6. [认证规范](#6-认证规范)
7. [分页规范](#7-分页规范)
8. [流式响应规范](#8-流式响应规范)
9. [版本控制](#9-版本控制)
10. [附录](#10-附录)

---

## 1. 基础约定

### 1.1 通信协议

- **传输协议：** HTTPS（生产环境强制）
- **数据格式：** JSON（`Content-Type: application/json`）
- **字符编码：** UTF-8
- **时间格式：** ISO 8601（`2026-07-30T14:30:00+08:00`）
- **日期格式：** `YYYY-MM-DD`

### 1.2 基础URL

```
https://api.example.com/api/v1
```

开发环境：
```
http://localhost:8000/api/v1
```

### 1.3 HTTP方法语义

| 方法 | 用途 | 幂等性 |
|------|------|--------|
| GET | 获取资源 | 是 |
| POST | 创建资源 / 执行操作 | 否 |
| PUT | 全量更新资源 | 是 |
| PATCH | 部分更新资源 | 否 |
| DELETE | 删除资源 | 是 |

**禁止使用：**
- GET 请求带请求体
- POST 用于幂等读取操作（如列表查询用 GET）

---

## 2. URL设计规范

### 2.1 命名规则

| 规则 | 要求 | 示例 |
|------|------|------|
| 全小写 | 统一小写 | `/chat-sessions` |
| 复数名词 | 资源集合用复数 | `/users`、`/documents` |
| 连字符分隔 | 多单词用 `-` 连接 | `/knowledge-bases` |
| 禁止下划线 | URL中不出现 `_` | `/chat-sessions` ✅ `/chat_sessions` ❌ |
| 禁止动词 | URL中不出现动词，动词放HTTP方法 | `POST /sessions` ✅ `POST /createSession` ❌ |
| 层级关系 | 用 `/` 表达嵌套关系 | `/knowledge-bases/{id}/documents` |

### 2.2 URL结构模板

```
/api/v1/{资源集合}
/api/v1/{资源集合}/{资源ID}
/api/v1/{资源集合}/{资源ID}/{子资源集合}
/api/v1/{资源集合}/{资源ID}/actions/{操作名}   ← 非CRUD操作
```

### 2.3 本项目URL清单

| 模块 | URL | 方法 | 说明 |
|------|-----|------|------|
| **认证** | `/auth/login` | POST | 登录 |
| | `/auth/refresh` | POST | 刷新Token |
| | `/auth/me` | GET | 获取当前用户 |
| | `/auth/logout` | POST | 登出 |
| | `/auth/password/change` | POST | 修改密码 |
| **用户** | `/users` | GET | 用户列表 |
| | `/users` | POST | 创建用户 |
| | `/users/{id}` | GET | 用户详情 |
| | `/users/{id}` | PUT | 更新用户 |
| | `/users/{id}` | DELETE | 删除用户 |
| | `/users/{id}/status` | PUT | 更新用户状态 |
| **问答** | `/chat/completions` | POST | 智能问答 |
| | `/chat/completions/stream` | POST | 流式问答 |
| | `/chat/sessions` | GET | 会话列表 |
| | `/chat/sessions/{id}` | DELETE | 删除会话 |
| | `/chat/feedback` | POST | 提交反馈 |
| **知识库** | `/knowledge/bases` | GET | 知识库列表 |
| | `/knowledge/bases` | POST | 创建知识库 |
| | `/knowledge/bases/{id}` | GET | 知识库详情 |
| | `/knowledge/bases/{id}` | PUT | 更新知识库 |
| | `/knowledge/bases/{id}` | DELETE | 删除知识库 |
| **文档** | `/documents` | GET | 文档列表 |
| | `/documents/upload` | POST | 上传文档 |
| | `/documents/{id}` | GET | 文档详情 |
| | `/documents/{id}` | DELETE | 删除文档 |
| | `/documents/{id}/reindex` | POST | 重新索引 |

---

## 3. 请求规范

### 3.1 请求头

| 头部 | 必填 | 说明 |
|------|------|------|
| `Content-Type` | 是（POST/PUT/PATCH） | `application/json` |
| `Authorization` | 是（除登录/注册/健康检查） | `Bearer {access_token}` |
| `Accept` | 否 | `application/json` |
| `X-Request-ID` | 否 | 请求追踪ID（UUID） |

### 3.2 请求体

- 必须使用 JSON 格式
- 字段命名：snake_case（小写下划线）
- 必填字段：必须有值，不能为 `null`
- 可选字段：可省略或为 `null`
- 空字符串：与 `null` 区分，`""` 表示空值，`null` 表示未设置

```json
{
  "username": "zhangsan",
  "email": null,
  "phone": ""
}
```

### 3.3 路径参数

- 使用 `{id}` 表示资源唯一标识
- ID 类型：UUID 字符串（36位）
- 示例：`/users/550e8400-e29b-41d4-a716-446655440000`

### 3.4 查询参数

- 分页：`?page=1&page_size=20`
- 过滤：`?status=active&role=admin`
- 排序：`?sort=-created_at`（`-` 表示降序）
- 搜索：`?q=关键词`
- 多值：`,` 分隔 `?status=active,locked`

---

## 4. 响应规范

### 4.1 统一响应格式

所有 API 响应（包括错误）使用统一结构：

```json
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": { ... }
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 业务状态码，`SUCCESS` 表示成功 |
| `message` | string | 是 | 人类可读的状态描述 |
| `data` | any | 否 | 业务数据，失败时可能为 `null` |

### 4.2 成功响应

**单条数据：**
```json
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "zhangsan",
    "display_name": "张三"
  }
}
```

**列表数据：**
```json
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": [
    { "id": "1", "name": "知识库A" },
    { "id": "2", "name": "知识库B" }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

**空数据：**
```json
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": null
}
```

### 4.3 HTTP状态码

| 状态码 | 使用场景 | 说明 |
|--------|----------|------|
| 200 | GET / PUT / PATCH / DELETE 成功 | 标准成功 |
| 201 | POST 创建成功 | 资源已创建 |
| 204 | DELETE 成功且无需返回数据 | 无内容 |
| 400 | 请求参数错误 | 校验失败 |
| 401 | 未认证 | Token缺失或无效 |
| 403 | 权限不足 | 已认证但无权访问 |
| 404 | 资源不存在 | URL或ID错误 |
| 409 | 资源冲突 | 如用户名已存在 |
| 422 | 业务逻辑校验失败 | 参数格式正确但业务不允许 |
| 429 | 请求过于频繁 | 限流触发 |
| 500 | 服务器内部错误 | 系统异常 |

**原则：** HTTP 状态码只表达协议层结果，业务错误用 `code` 字段表达。

---

## 5. 错误码规范

### 5.1 错误响应格式

```json
{
  "code": "AUTHENTICATION_ERROR",
  "message": "用户名或密码错误",
  "detail": "可选的详细错误信息"
}
```

### 5.2 错误码分类

| 前缀 | 类别 | 示例 |
|------|------|------|
| `SUCCESS` | 成功 | `SUCCESS` |
| `VALIDATION_` | 参数校验错误 | `VALIDATION_ERROR` |
| `AUTHENTICATION_` | 认证错误 | `AUTHENTICATION_ERROR` |
| `AUTHORIZATION_` | 授权错误 | `AUTHORIZATION_ERROR` |
| `NOT_FOUND_` | 资源不存在 | `NOT_FOUND_USER` |
| `CONFLICT_` | 资源冲突 | `CONFLICT_USERNAME` |
| `SYSTEM_` | 系统错误 | `SYSTEM_ERROR` |
| `LLM_` | LLM调用错误 | `LLM_ERROR` |
| `RAG_` | RAG流程错误 | `RAG_ERROR` |

### 5.3 错误码清单

| 错误码 | HTTP状态码 | 说明 |
|--------|-----------|------|
| `SUCCESS` | 200 | 操作成功 |
| `VALIDATION_ERROR` | 400 | 请求参数校验失败 |
| `AUTHENTICATION_ERROR` | 401 | 用户名或密码错误 |
| `AUTHORIZATION_ERROR` | 403 | 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `NOT_FOUND_USER` | 404 | 用户不存在 |
| `CONFLICT_USERNAME` | 409 | 用户名已存在 |
| `SYSTEM_ERROR` | 500 | 系统内部错误 |
| `LLM_ERROR` | 500 | AI服务调用失败 |
| `RAG_ERROR` | 500 | 知识检索失败 |

---

## 6. 认证规范

### 6.1 Token传递

```
Authorization: Bearer {access_token}
```

### 6.2 Token过期处理

- Access Token 过期：返回 401，客户端用 Refresh Token 换取新的 Access Token
- Refresh Token 过期：返回 401，要求重新登录

### 6.3 认证接口例外

以下接口无需认证：
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /health`
- `GET /`

---

## 7. 分页规范

### 7.1 请求参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码，从1开始 |
| `page_size` | int | 20 | 每页条数，最大100 |

### 7.2 响应格式

```json
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": [ ... ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### 7.3 分页响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `data` | array | 当前页数据列表 |
| `total` | int | 总记录数 |
| `page` | int | 当前页码 |
| `page_size` | int | 每页条数 |

---

## 8. 流式响应规范

### 8.1 SSE格式

智能问答流式输出使用 Server-Sent Events：

```
Content-Type: text/event-stream
```

**数据格式：**
```
data: {"type": "chunk", "content": "这是"}

data: {"type": "chunk", "content": "回答"}

data: {"type": "sources", "data": [...]}

data: {"type": "done", "tokens_used": 123}

```

### 8.2 WebSocket格式

WebSocket 聊天接口：

**发送：**
```json
{
  "message": "问题内容",
  "session_id": "可选",
  "kb_ids": ["kb-1"]
}
```

**接收：**
```json
{"type": "chunk", "content": "内容片段"}
{"type": "sources", "data": [...]}
{"type": "done", "tokens_used": 123}
{"type": "error", "message": "错误信息"}
```

---

## 9. 版本控制

### 9.1 URL版本化

采用 URL 路径版本化：
```
/api/v1/...
/api/v2/...
```

### 9.2 版本策略

- **主版本（v1 → v2）：** 破坏性变更，需提前通知，保留旧版本至少6个月
- **次版本：** 向后兼容的新增字段，不升级URL版本
- **当前版本：** v1

### 9.3 弃用通知

API 弃用时，响应头增加：
```
Deprecation: true
Sunset: Sat, 31 Dec 2026 23:59:59 GMT
```

---

## 10. 附录

### 附录A：完整请求示例

**登录：**
```http
POST /api/v1/auth/login HTTP/1.1
Host: api.example.com
Content-Type: application/json

{
  "username": "zhangsan",
  "password": "Password123!",
  "auth_type": "local"
}
```

**响应：**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "code": "SUCCESS",
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 28800
  }
}
```

### 附录B：错误响应示例

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "code": "AUTHENTICATION_ERROR",
  "message": "用户名或密码错误"
}
```

### 附录C：分页请求示例

```http
GET /api/v1/users?page=1&page_size=20&status=active HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

**文档结束**

---

*本文档为《编码规范》配套专项规范，与之共同构成项目规范体系。*
