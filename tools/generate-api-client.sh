#!/usr/bin/env bash
# 重新生成 OpenAPI 契约 + 前端 TS 类型。后端改路由/schema 后跑：make gen-client
#
# 前置：Python 3.11 + backend/requirements.txt（脚本导入 app 需完整依赖）。
#   - CI：直接 python tools/export-openapi.py（runner 有 Python 3.11 + deps）
#   - 本地宿主机 Python <3.11：用容器跑导出，例如：
#       docker run --rm --entrypoint python -v "$PWD:/repo" -w /repo deployment-backend:latest tools/export-openapi.py
#     再跑本脚本的第 2 步（openapi-typescript）
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# 1. 导出 OpenAPI schema（需 Python 3.11 + backend deps）
python tools/export-openapi.py

# 2. openapi-typescript 生成前端 TS 类型（仅类型，非运行时客户端）
cd frontend && npx --no-install openapi-typescript ../docs/api-contracts/api-schema.json -o src/api/types.d.ts
echo "✅ 生成完成：docs/api-contracts/api-schema.json + frontend/src/api/types.d.ts"
echo "   记得 git add 这两个派生物。"
