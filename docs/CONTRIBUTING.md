# 贡献指南

感谢参与 rag-qa-platform。本指南带你从零跑通本地开发到提交 PR。

## 前置

- Python 3.11+（`python --version`）
- Node 20+（见 `.nvmrc`；`nvm use`）
- Docker + docker-compose
- Windows 用户注意：仓库 `.gitattributes` 强制 LF 行尾，配合 `core.autocrlf` 无需额外操作

## 首次启用

```bash
git clone <repo> && cd rag-qa-platform
make setup-dev
```

`make setup-dev` 会：宿主机用 pipx 装 pre-commit 工具链（ruff/black/isort/bandit/detect-secrets，版本对齐 `backend/requirements-dev.txt`）+ 容器内装 lint 工具 + `pre-commit install` 装 git 钩子 + 前端 `npm ci`。

若提示缺 pipx/Python 3.11+，按提示安装后再跑。

## 日常开发循环

```bash
# 写代码...

# 提交前跑完整门禁（与 CI 一致，纯阻断）
make check

# 提交（钩子自动跑秒级检查：ruff/black/isort/bandit/detect-secrets/prettier/eslint）
git commit -m "feat(xxx): 简述"

# 推送（main 受保护，推到分支再开 PR）
git push origin <branch>
```

## 提交信息规范

**Conventional Commits**（release-please 据此自动发版 + changelog）：

| 前缀 | 用途 |
|---|---|
| `feat:` | 新功能 |
| `fix:` | bug 修复 |
| `docs:` | 文档 |
| `chore:` | 构建/工具/杂项 |
| `refactor:` | 重构（不改行为） |
| `test:` | 测试 |

示例：`feat(knowledge): 支持按标签过滤检索`、`fix(ci): 修 npm ci 失败`。

## 改了后端路由/模型

后端改了 API（路由、schema、响应模型），必须更新契约并重新生成前端类型，否则 CI 派生物一致性校验失败：

```bash
python tools/export-openapi.py   # 重新生成 docs/api-contracts/api-schema.json
make gen-client                  # 重新生成前端 TS 类型
git add docs/api-contracts/api-schema.json frontend/src/api/types.d.ts
```

## PR 流程

1. 从 main 切分支：`git checkout -b feat/xxx`
2. 提交并推送分支
3. 开 PR -> CI 必须全绿 -> 至少 1 个 review（Code Owner）-> squash merge
4. main 受保护：禁直推、禁 force-push、必过 6 个 required check、linear history

## 依赖漏洞

`make security-check` 跑 `pip-audit` + `npm audit`（**advisory，不阻断**）。主力靠 GitHub Dependabot 原生告警。

## 常见问题

- **commit 钩子 `command not found`**：宿主机没装工具，重跑 `make setup-dev`。
- **prettier/black 反复报格式**：行尾问题，确认 `.gitattributes` 在仓库根。
- **CI 红但本地绿**：跨平台差异（lockfile/detect-secrets baseline），见 [docs/HARNESS_ENGINEERING.md](HARNESS_ENGINEERING.md) 与 CI 修复记录。

详见 [AGENTS.md](AGENTS.md) 与 [docs/HARNESS_ENGINEERING.md](HARNESS_ENGINEERING.md)。
