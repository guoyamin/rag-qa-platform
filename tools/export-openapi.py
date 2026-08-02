#!/usr/bin/env python3
"""导出 OpenAPI schema 到 docs/api-contracts/api-schema.json。

派生物一致性校验（CI）与 `make gen-client` 依赖此脚本。
设计要点（见 HARNESS_ENGINEERING §7.1）：导入 app 前**无条件注入完整 mock env**，
不依赖 .env 存在或 config 默认值--防未来某开发新增无默认的必填配置项导致 CI 导出崩溃。

运行：python tools/export-openapi.py
"""
import json
import os
import sys
from pathlib import Path

# 无条件注入 mock env（setdefault：不覆盖已存在的真实 env）
_MOCK_ENV = {
    "ENV": "development",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "SECRET_KEY": "ci-export-mock-secret-not-real",  # nosec B105 -- 仅导出用，非真实密钥
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_API_KEY": "mock-llm-key",
    "EMBEDDING_API_KEY": "mock-embedding-key",
}
for _k, _v in _MOCK_ENV.items():
    os.environ.setdefault(_k, _v)

# 把 backend 加入 sys.path（app 包所在目录）
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))

from app.main import app  # noqa: E402

_SCHEMA = app.openapi()
_OUT = Path(__file__).resolve().parent.parent / "docs" / "api-contracts" / "api-schema.json"
_OUT.parent.mkdir(parents=True, exist_ok=True)
_OUT.write_text(json.dumps(_SCHEMA, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OpenAPI schema written to {_OUT} ({_OUT.stat().st_size} bytes)")
