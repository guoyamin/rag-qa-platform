# AGENTS.md

本文件是 AI 编码代理（Claude / Cursor / Copilot 等）在本仓库工作的**单一真相源**。Claude 专有入口 `CLAUDE.md` 指向此处。

## 项目

**rag-qa-platform**：内部 RAG 智能问答平台。后端 FastAPI（Python 3.11），前端 Vue 3 + TypeScript，向量库 Milvus，编排 docker-compose。

## 关键命令

```bash
make setup-dev      # 首次启用：宿主机装 pre-commit 工具链 + 容器装 lint 工具 + 装 git 钩子 + npm ci
make check          # 提交前完整门禁（纯阻断，与 CI required check 一致）
make security-check # 依赖漏洞 advisory 预检（不阻断）
make gen-client     # 从 OpenAPI 重新生成前端 TS 类型
pre-commit run --all-files   # 全量跑提交钩子
python tools/export-openapi.py  # 后端改路由后，更新 OpenAPI 契约
```

## 门禁（两段式，见 docs/HARNESS_ENGINEERING.md §5）

- **提交时（秒级）**：pre-commit 钩子跑 ruff / black / isort / bandit / detect-secrets / prettier / eslint。`--no-verify` 能跳过，但别养成习惯。
- **提交前/CI（慢）**：`make check` = ruff + black + isort + mypy --strict + bandit + pytest（`--cov-fail-under`）。CI required check 集 = make check 全部阻断项。
- **强制层**：main 分支保护--必过 CI / 禁直推 / 必 review / linear history。所有改动走 PR。

## 约定

- **提交信息**：Conventional Commits（`feat:` / `fix:` / `docs:` / `chore:` ...），release-please 据此发版。
- **派生物**：OpenAPI schema、前端 TS 类型、package-lock 均为派生物，改了源必须重新生成并提交；CI 会 `git diff --exit-code` 校验。
- **配置位置**：CI 进 `.github/workflows/`，lint 进 `backend/pyproject.toml`，提交钩子进 `.pre-commit-config.yaml`。不发明平行目录。

## 目录结构（关键）

```
backend/         FastAPI app（app/）、测试（tests/）、pyproject.toml、requirements*.txt
frontend/        Vue 3 + TS（src/）、package.json + package-lock.json
tools/           export-openapi.py（契约导出）、hooks/（卫生钩子）、generate-api-client.sh
docs/            HARNESS_ENGINEERING.md（门禁体系）、api-contracts/、CONTRIBUTING.md
.github/         workflows/ci.yml、CODEOWNERS、dependabot.yml、PR/Issue 模板
```

## 技能

技能位于 `skills/`（跨厂商便携，根索引在本文件）。当前示例：`skills/onboard-endpoint/`（新增 API 端点的端到端流程）。新增技能在此索引登记。

## 重要文档

- `docs/HARNESS_ENGINEERING.md` --门禁体系完整方案（设计原则、目录、门禁、安全、契约、落地清单）。
- `docs/CONTRIBUTING.md` --端到端 onboarding。
- `backend/.env.example` --环境变量模板（真实 `.env` 被忽略，不进仓库）。
