# Backend AGENTS — FastAPI 后端工作指令

> 本文件是 AI 在 `backend/` 下工作的**模块级指令**，叠加在根 `AGENTS.md` 之上。
> 架构与模块资产见 `docs/architecture/module-map.md` 与 `docs/modules/`。

## 技术栈

FastAPI · Python 3.11 · SQLAlchemy 2.0（async）· Alembic · PostgreSQL · structlog · **mypy --strict**

## 分层（依赖只准自上而下）

```
api/v1/   → HTTP 协议层：路由、参数校验、依赖注入、统一响应。不写业务逻辑
services/ → 业务层：业务逻辑、事务、编排。不返回协议对象
models/   → SQLAlchemy 持久层
core/     → 配置(config)、异常(exceptions)、安全(security)
```

**禁止**：api 直接调 models（不经 service）；service 返回 `DataResponse` 等协议对象。

## 异常处理（核心约定）

- **Service 层只抛 `BaseAppException` 子类，绝不抛 `HTTPException`**
- 每个异常带 `http_status`（协议码）+ `code`（业务码）+ `message`
- 已定义子类（`app.core.exceptions`）：`ValidationError`(400) / `AuthenticationError`(401) / `AuthorizationError`(403) / `NotFoundError`(404) / `RateLimitExceeded`(429) / `LLMError`·`RAGError`·`ServiceUnavailableError`(503)
- `main.py` 的 `@app.exception_handler(BaseAppException)` 统一转 `{code, message}` + 正确 HTTP 码
- 新增业务异常 → 继承 `BaseAppException` 设 `http_status` + `code`

## 响应格式

统一用 `app.schemas` 的 `DataResponse` / `ListResponse` / `ResponseBase`（`{code, message, data}`）。错误响应 `{code, message}`（无 data）。详见 `docs/standards/api-contract.md`。

## 依赖注入

统一从 `app.api.deps` 导入：`get_db`（AsyncSession）、`get_current_user` / `get_current_active_user`、`require_admin` / `require_operator` / `require_staff`（RoleChecker）、`get_ws_user`。

## 改路由/端点必做

1. 在 `api/v1/<域>.py` 加路由（`APIRouter(prefix, tags)` + `Depends`）
2. 业务进 `services/`，持久进 `models/`
3. 改了 schema → 跑 `make gen-client` 重新生成 OpenAPI + 前端 TS 类型（派生物，CI 校验一致性）
4. 改了 DB schema → 写 Alembic 迁移（`alembic revision --autogenerate`），`make check` 含 `alembic check`
5. 新路由要在 `main.py` `include_router` 注册（注意：`template` 必须先于 `model` 注册，静态路径避免被 `/models/{id}` 捕获）

## 门禁（提交前）

`make check`（容器内）：ruff + black + isort + **mypy --strict** + bandit + pytest（`--cov-fail-under`）+ alembic check。**mypy --strict 是强约束**——新代码必须类型完备。

## 约定

- 全异步（`async def` + `AsyncSession`）；同步阻塞调用（如 Milvus）必须 `asyncio.to_thread`
- 日志用 `structlog.get_logger(__name__)`，事件式命名（`xxx_created`），不打敏感信息
- 配置走 `app.core.config.settings`（环境变量注入），禁止硬编码
