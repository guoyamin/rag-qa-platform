# API 契约规范

> 前后端接口的单一真相。后端 FastAPI 产出 OpenAPI（`docs/api-contracts/api-schema.json`），前端类型由 `openapi-typescript` 生成。
> 本规范由原 `API_DESIGN.md` + `API.md` 合并而来。

## 1. 基础约定

- HTTPS（生产强制）· JSON（`application/json`）· UTF-8 · 时间 ISO 8601 · 日期 `YYYY-MM-DD`
- 基础 URL：`/api/v1`
- HTTP 方法语义：GET（查，幂等）/ POST（建，非幂等）/ PUT（全量改，幂等）/ PATCH（部分改）/ DELETE（删，幂等）
- **禁止**：GET 带 body；POST 做幂等读取（列表查询用 GET）

## 2. URL 设计

- 全小写 · 复数名词 · 连字符分隔（`/knowledge-bases`）· **禁止下划线** · **禁止动词**（动词放 HTTP 方法）
- 模板：`/api/v1/{集合}` · `/{集合}/{id}` · `/{集合}/{id}/{子集合}` · `/{集合}/{id}/actions/{操作}`（非 CRUD）

### 端点清单

| 模块 | URL | 方法 | 说明 |
|------|-----|------|------|
| **认证** | `/auth/login` | POST | 登录 |
| | `/auth/refresh` | POST | 刷新 Token |
| | `/auth/me` | GET | 当前用户 |
| | `/auth/logout` | POST | 登出 |
| | `/auth/password/change` | POST | 改密码 |
| **用户** | `/users` | GET/POST | 列表/创建 |
| | `/users/{id}` | GET/PUT/DELETE | 详情/更新/删除（软删除） |
| | `/users/{id}/status` | PUT | 改状态 |
| **问答** | `/chat/completions` | POST | 智能问答（非流式） |
| | `/chat/completions/stream` | POST | 流式问答（SSE） |
| | `/chat/sessions` | GET | 会话列表 |
| | `/chat/sessions/{id}` | DELETE | 删除会话 |
| | `/chat/feedback` | POST | 提交反馈 |
| **知识库** | `/knowledge/bases` | GET/POST | 列表/创建 |
| | `/knowledge/bases/{id}` | GET/PUT/DELETE | 详情/更新/删除 |
| **文档** | `/documents` | GET | 列表 |
| | `/documents/upload` | POST | 上传（multipart/form-data） |
| | `/documents/{id}` | GET/DELETE | 详情/删除 |
| | `/documents/{id}/reindex` | POST | 重新索引 |

> 模型管理、模板、统计、健康检查路由另见 `api/v1/{model,template,stats,health}.py`。

## 3. 请求

- **头**：`Content-Type: application/json`（POST/PUT/PATCH）· `Authorization: Bearer {token}`（除登录/健康检查）· `X-Request-ID`（可选追踪）
- **体**：JSON · snake_case · 必填字段不可 `null` · `""` 与 `null` 区分
- **路径参数**：`{id}` 为 UUID
- **查询**：分页 `?page=1&page_size=20` · 过滤 `?status=active` · 排序 `?sort=-created_at`（`-` 降序）· 搜索 `?q=` · 多值 `,` 分隔

## 4. 响应

统一格式（成功/错误均用）：
```json
{ "code": "SUCCESS", "message": "操作成功", "data": { ... } }
```
- 列表加分页字段：`total` / `page` / `page_size`
- HTTP 状态码：200/201/204 成功；400 参数；401 未认证；403 无权限；404 不存在；409 冲突；422 业务校验；429 限流；500 系统
- **原则：HTTP 码表达协议层，业务错误用 `code` 字段**

## 5. 错误码

错误响应：`{ "code": "...", "message": "...", "detail": "可选" }`

**分类前缀**：`SUCCESS` / `VALIDATION_` / `AUTHENTICATION_` / `AUTHORIZATION_` / `NOT_FOUND_` / `CONFLICT_` / `SYSTEM_` / `LLM_` / `RAG_`

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `SUCCESS` | 200 | 操作成功 |
| `VALIDATION_ERROR` | 400 | 参数校验失败 |
| `AUTHENTICATION_ERROR` | 401 | 用户名或密码错误 |
| `AUTHORIZATION_ERROR` | 403 | 权限不足 |
| `NOT_FOUND` / `NOT_FOUND_USER` | 404 | 资源/用户不存在 |
| `CONFLICT_USERNAME` | 409 | 用户名已存在 |
| `RATE_LIMIT_EXCEEDED` | 429 | 请求过于频繁 |
| `SYSTEM_ERROR` | 500 | 系统内部错误 |
| `LLM_ERROR` / `RAG_ERROR` / `SERVICE_UNAVAILABLE` | 503 | AI 服务/检索/服务不可用 |

> 错误码与 `app/core/exceptions.py` 的 `BaseAppException` 子类一一对应。

## 6. 认证

- `Authorization: Bearer {access_token}`
- Access Token 过期 → 401，用 Refresh Token 换新；Refresh Token 过期 → 401 重登
- 无需认证：`POST /auth/login` · `POST /auth/refresh` · `GET /health` · `GET /`

## 7. 分页

- 请求：`page`（默认 1）· `page_size`（默认 20，最大 100）
- 响应：`data`(array) + `total` + `page` + `page_size`

## 8. 流式（SSE / WebSocket）

- **SSE**：`Content-Type: text/event-stream`，事件 `{type: chunk|sources|done|error, ...}`
- **WebSocket**：发送 `{message, session_id?, kb_ids?}`；接收同 SSE 事件类型

## 9. 版本控制

- URL 路径版本化：`/api/v1` → `/api/v2`
- 主版本：破坏性变更，旧版保留 ≥ 6 个月；次版本：兼容新增字段不升 URL 版本
- 弃用：响应头 `Deprecation: true` + `Sunset: <date>`
