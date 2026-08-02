# API 契约（OpenAPI）

本目录存放从后端 FastAPI 应用派生的 OpenAPI schema，是前后端契约的**单一真相源**。

## 生成

```bash
python tools/export-openapi.py
```

脚本导入 `app.main:app` 调用 `app.openapi()`，输出 `api-schema.json`。导入前无条件注入 mock env（见 `tools/export-openapi.py`），不依赖 `.env`。

## 一致性校验

CI 派生物一致性校验（见 HARNESS_ENGINEERING §5.3/§14.3）会重新生成并 `git diff --exit-code`：
- 后端改了路由/模型 -> 本地先跑 `python tools/export-openapi.py` 提交新的 `api-schema.json`，再推。
- 忘了跑 -> CI 重新生成发现 diff -> CI 红，并打印指引。

## 前端类型

`make gen-client` 用 `openapi-typescript` 从 `api-schema.json` 生成前端 TS 类型（仅类型，非运行时客户端）。
