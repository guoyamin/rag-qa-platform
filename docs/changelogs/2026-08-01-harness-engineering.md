# 变更清单：建立工程门禁体系（Harness Engineering）

**需求/任务:** 为项目建立 Harness Engineering，把「自检清单」从自觉行为变为强制门禁
**模块:** 全仓库（工程基础设施）
**AI生成:** 是
**生成日期:** 2026-08-01
**预计Review时间:** 15 分钟
**分支:** `claude/harness-engineering`

---

## 背景

上一迭代最大教训是「代码写完没自检」——71 文件代码未跑 mypy/ruff/pytest 就进 Review，
导致 216 mypy 错、登录 500、创建 503 等。根因：自检是**自觉行为**，不是**强制门禁**。
本次建立 Harness，把 CODING_STANDARD / AI_COLLABORATION_RULES §6 自检清单机械化执行。

## 新增

- `.pre-commit-config.yaml`：commit 时自动跑 ruff/black/isort/bandit/detect-secrets（后端）
  + prettier/eslint（前端），只查暂存文件，秒级反馈。采用 `repo:local + language:system`，
  不依赖 GitHub 网络（适配国内环境）。mypy/pytest 为慢检查，放 `make check` 不进 commit 钩子。
- `backend/requirements-dev.txt`：固定 ruff/black/isort/mypy/bandit/detect-secrets/pip-audit/
  pre-commit 版本，消除「每次自检临时装工具」的脆弱性。
- `backend/.bandit` + `.secrets.baseline`：补全 SECURITY_BASELINE 附录A 写明但仓库缺失的配置；
  基线从 git 跟踪文件生成，detect-secrets 只拦**新增**密钥。
- `.gitattributes`：`* text=auto eol=lf`，统一行尾，覆盖 Windows git autocrlf 转 CRLF 的行为
  （与 prettier `endOfLine: lf` 一致，避免 prettier 反复报错）。

## 修改

- `Makefile`：新增 `make check`（完整门禁，与 CI 一致）、`make setup-dev`（装工具）；
  后端 lint/test/security 目标改在容器内执行（本机无 3.11 环境）；修 `make test` 漏集成测试。
- `deployment/docker-compose.dev.yml`：补全 tests/pytest.ini/requirements-dev/.bandit 挂载
  （原仅挂 app/，容器内 tests 与配置文件为镜像旧版本）。
- `.gitignore`：取消对 `.secrets.baseline` 的错误忽略（基线须提交共享）。
- 一次性格式化基线：black+isort 后端 52 文件、prettier 前端 26 文件（纯格式，不改逻辑）。

## 修复（门禁暴露的问题）

- `backend/tests/conftest.py`：路径计算 off-by-one（`parent.parent.parent` 在容器内解析为 `/`，
  导致 `/app` 被当成命名空间包遮蔽真正的 `app` 包，pytest 收集报 `No module named app.core`）。
  改为 `parent.parent`。**这是 pytest 在容器内一直跑不通的根因。**
- `backend/app/core/config.py`：`# nosec B104` 挂在 Field() 闭括号行，bandit 实际标记的是
  `default="0.0.0.0"` 所在行，注释未生效。移到 default 行。
- `backend/tests/unit/test_health.py`：ruff F401 未用导入 / N806 变量遮蔽导入枚举 /
  UP041 `asyncio.TimeoutError->TimeoutError`（tests/ 此前未纳入 ruff 检查）。

## 自检结果（全部在 main 当前代码上验证通过）

- [x] ruff check（app + tests）通过
- [x] black --check 通过
- [x] isort --check 通过
- [x] mypy --strict app 通过（59 文件，0 错误）
- [x] bandit 通过（0 issue，4 个 nosec 正确跳过）
- [x] detect-secrets 通过（基于基线）
- [x] eslint 通过
- [x] prettier --check 通过
- [x] pytest 通过：**729 passed，覆盖率 92%**（396s）
- [x] pre-commit run --all-files：7 钩子全绿
- [x] 真实 commit 触发钩子验证通过

## 待确认事项

1. **dev 容器挂载了旧 worktree**：`rag_qa_platform-backend` 容器的 `/app/app` 挂载自
   `suspicious-allen-c54d83`（上一迭代 worktree），非 main。故 `make check` 在该容器内
   跑的是旧代码。**建议**重建容器使其挂载 main 的 backend（也修复 dev 服务器跑旧代码的问题）。
   本次验证用一次性容器挂载 main 代码完成，未改动运行中的 dev 容器。
2. **配远程 + PR**（既有待办）：CI（`.github/workflows/ci.yml`）存在但无 git remote，从未运行。
   配远程后 CI 才真正生效。CI 本身有 5 个 bug（bandit `|| true` 非阻断、`npm ci` 缺 lockfile 等），
   属 P1 范围，本次未改。

## Review 建议

- 重点关注：`.pre-commit-config.yaml`（钩子选型与 monorepo 路径处理）、
  `Makefile` 的 `make check`（容器执行方式）、`conftest.py` 路径修复。
- 可快速浏览：格式化基线提交（`dd32d90`，纯格式）、`.gitattributes`。

## 使用方式

```bash
# 首次启用（本机装工具 + 装 git 钩子）
make setup-dev

# 之后每次 commit 自动触发门禁（秒级）
git commit ...

# 提交前跑完整门禁（与 CI 一致，含 mypy + pytest）
make check
```
