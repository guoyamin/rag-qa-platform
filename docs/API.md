# API接口文档

## 认证模块 (/api/v1/auth)

### POST /login
用户登录

**请求体：**
```json
{
  "username": "string",
  "password": "string",
  "auth_type": "local | ldap"
}
```

**响应：**
```json
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": {
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "bearer",
    "expires_in": 28800
  }
}
```

### POST /refresh
刷新Token

### GET /me
获取当前用户信息

### POST /logout
用户登出

---

## 用户管理 (/api/v1/users) — 管理员权限

### GET /
获取用户列表（分页）

### POST /
创建用户

### GET /{user_id}
获取用户详情

### PUT /{user_id}
更新用户信息

### DELETE /{user_id}
删除用户（软删除）

---

## 智能问答 (/api/v1/chat)

### POST /completions
智能问答（非流式）

**请求体：**
```json
{
  "message": "请假流程是什么？",
  "session_id": "optional-session-id",
  "kb_ids": ["kb-id-1"],
  "stream": false
}
```

**响应：**
```json
{
  "code": "SUCCESS",
  "data": {
    "answer": "...",
    "sources": [...],
    "tokens_used": 1234,
    "latency_ms": 2345
  }
}
```

### POST /completions/stream
智能问答（流式，SSE格式）

### GET /sessions
获取会话列表

### DELETE /sessions/{session_id}
删除会话

### POST /feedback
提交反馈

---

## 知识库管理 (/api/v1/knowledge)

### GET /bases
获取知识库列表

### POST /bases
创建知识库

### GET /bases/{kb_id}
获取知识库详情

### PUT /bases/{kb_id}
更新知识库

### DELETE /bases/{kb_id}
删除知识库

---

## 文档管理 (/api/v1/documents)

### GET /
获取文档列表

### POST /upload
上传文档（multipart/form-data）

### GET /{doc_id}
获取文档详情

### DELETE /{doc_id}
删除文档

### POST /{doc_id}/reindex
重新索引文档
