# Harness 平台设置 Runbook（B 类操作）

> **定位**：把「配置文件」变成「强制门禁」的**平台侧操作手册**。配置进了仓库只是「建议」；只有 GitHub 仓库设置（分支保护 / Dependabot / Actions 权限）才能让前面所有门禁真正生效（见 [HARNESS_ENGINEERING.md](HARNESS_ENGINEERING.md) §1.3 设计哲学）。
>
> **适用**：单人维护的内部项目（rag-qa-platform）。所有设置已按「单人硬门禁」调校：**0 approving reviews + enforce for administrators**，既强制必过 CI，又不卡住自己。
>
> **复现性**：本文记录的是**实际生效**的配置，按顺序操作即可在任意时刻复刻/复核。

---

## 0. 前置（一次性）

| 项 | 说明 |
|---|---|
| 仓库已建并设为 public | `guoyamin/rag-qa-platform`。public 后依赖漏洞匿名 API 可查 run/job 状态（日志仍需 token）。 |
| git remote 用 SSH-443 | `ssh://git@ssh.github.com:443/guoyamin/rag-qa-platform.git`。绕过 22 端口封锁（国内 GFW），push/clone 走 443。 |
| Conventional Commits 已强制 | `.pre-commit-config.yaml` 的 commit-msg 钩子（`tools/hooks/check_commit_msg.sh`）拦截非法格式。**这是 release-please 发版的前提**。 |

查看 remote：
```bash
git remote -v
# origin  ssh://git@ssh.github.com:443/guoyamin/rag-qa-platform.git
```

---

## 1. 分支保护（Ruleset —— 强制层核心）

### 1.1 为什么用 Ruleset 而非 classic branch protection

classic「Branch protection rules」对**单人项目是死局**：勾选「Require approvals」最少 1 人 + 「Require review from Code Owners」，**作者不能批准自己的 PR** → 永远无法合并。

**Rulesets**（Settings → Rules → Rulesets）可设 **required approving reviews = 0**，同时勾选 **enforce for administrators**——管理员（即你自己）也必须走 PR + CI，形成「单人硬门禁」：跳不过 CI，但不会被 review 卡死。

### 1.2 实际生效的 Ruleset 配置

在 **Settings → Rules → Rulesets → New ruleset → New branch ruleset** 创建：

**General**
- **Ruleset name**: `main-protection`
- **Enforcement status**: `Active`
- **Target branches**: `Include by wildcard` → `main`（如还用 master/develop 也一并加上）

**Bypass list**: **空**（谁都不能绕过，含管理员——靠 enforce for administrators 保证）

**Rule types / 勾选项**

| 规则 | 设置 | 作用 |
|---|---|---|
| **Require a pull request before merging** | required approvals = **0** | 禁止直推 main，必须开 PR；0 approvals 不卡自己 |
| ↳ **Require approval from Code Owners** | 不勾 | 单人无需他人批准（CODEOWNERS 文件仍在，留作多人时启用） |
| **Require status checks to pass** | 勾，见下表 | CI 必过才能合并（对齐 `make check`） |
| ↳ **Require branches to be up to date** | 勾 | 合并前 PR 须与 main 同步，防 stale 合进 |
| **Do not allow bypassing the above rules** | 勾（即 enforce for administrators） | 管理员也强制走 PR+CI |
| **Restrict who can push to matching branches** | 不设 | 已由「Require a pull request」覆盖 |
| Linear history | 可选 squash | 推荐 squash（Conventional Commits + 单 commit 入 main，release-please 解析干净） |

**Required status checks（必须与 ci.yml 的 job `name:` 完全一致）**：

| Check context | ci.yml job | 对齐 make check 项 |
|---|---|---|
| `Lint & Secret Scan` | `lint` | ruff/black/isort/detect-secrets/prettier/eslint（`pre-commit run --all-files`） |
| `Type Check (mypy)` | `type-check` | mypy --strict |
| `Security Scan (bandit)` | `security-scan` | bandit -ll -c .bandit |
| `Backend Unit Tests` | `backend-unit-test` | pytest（not integration）+ alembic check |
| `Backend Integration Tests` | `backend-integration-test` | pytest -m integration（Postgres+Redis service） |
| `Frontend Type Check & Unit Tests` | `frontend-test` | vue-tsc + vitest |

> **E2E Tests（`e2e-test` job）不在 required 集**——它 `if: github.event_name == 'pull_request'` 且依赖 Playwright 起服务，当前未稳定（见 §6 待办），不阻断合并。
>
> **required check 名 = ci.yml 里 job 的 `name:` 字段**。改 job 显示名时务必同步更新 Ruleset，否则 PR 会卡「missing check」。

### 1.3 验证 Ruleset 生效

```bash
# 匿名（public 仓库）即可读 ruleset 摘要
curl -s https://api.github.com/repos/guoyamin/rag-qa-platform/rulesets | python -m json.tool
```
应看到一条 `enforcement: active`、`target: branch` 的规则。也可在 PR 页面「Merge」按钮旁看到检查项被列为 required。

---

## 2. CODEOWNERS（已在仓库）

`.github/CODEOWNERS`：
```
# 默认所有代码由 @guoyamin review
* @guoyamin
```
单人即全仓 owner。多人时按目录细分（如 `backend/ @xxx`、`frontend/ @yyy`），再在 Ruleset 勾「Require approval from Code Owners」启用强制领域审查。

---

## 3. Dependabot（依赖更新主力）

### 3.1 配置已在仓库（`.github/dependabot.yml`）

覆盖三类生态，每周一提 PR，**仅自动提 minor/patch**（`version-update:semver-major` 被忽略，大版本升级人工评估后手动做）：

| 生态 | 目录 | 说明 |
|---|---|---|
| `pip` | `/backend` | 后端 Python 依赖 |
| `npm` | `/frontend` | 前端依赖 |
| `github-actions` | `/` | workflow 用的 action 版本（actions/checkout 等） |

**配置提交后自动生效**，无需额外开关即可开依赖 PR。

### 3.2 必须手动开启：安全告警（B 类）

Dependabot **版本更新 PR**（上面的）默认开；但 **Dependabot security alerts**（已知漏洞告警）需单独开：

**Settings → Code security → Code security analysis**

- **Dependabot security updates**: **Enable**（发现漏洞自动开修复 PR）
- **Dependabot alerts**: **Enable**（收到漏洞告警通知）

> 这是 §6 SCA 体系的主力（见 HARNESS §6）。pip-audit/npm audit 仅作本地 `make security-check` advisory 预检，不阻断。

---

## 4. release-please（发版自动化）

### 4.1 配置已在仓库（`.github/workflows/release-please.yml`）

- 触发：`push: [main]`（**不在 PR 上跑**，故非 required check）
- `release-type: python`，**`path: backend`**：以 `backend/pyproject.toml` 的 `[project] version` 为发版源（当前 `1.0.0`）
- `include-component-in-tag: false`：tag 形如 `v1.0.1`（无 `backend-` 前缀）
- 语义：`feat:` → minor，`fix:` → patch，`BREAKING CHANGE` / `feat!` → major

### 4.2 ⚠️ 必须手动开启的两个仓库设置（B 类，否则 release-please 必失败）

release-please 要**开 release PR、打 tag、建 Release**，需要 Actions 有写权限。在 **Settings → Actions → General → Workflow permissions**：

| 设置 | 值 | 原因 |
|---|---|---|
| **Workflow permissions** | **Read and write permissions** | release-please 要写 tag/release（workflow 里也声明了 `contents: write`，但仓库层默认必须允许） |
| **Allow GitHub Actions to create and approve pull requests** | **勾选** | release-please 的核心动作是开「release PR」；不勾则直接失败 |

> 不勾这两个，release-please 会在 main 上**每次 push 都红 X**（job `release-please` failed at `Run googleapis/release-please-action@v4`）。这是 release-please 最常见的「配了不跑」根因。
>
> workflow 文件已声明 `permissions: contents: write, pull-requests: write`，与上面仓库层设置配合生效。

### 4.3 工作方式

1. 你正常提 `feat:` / `fix:` 到 main（经 PR）。
2. release-please 自动累积这些 commit，开一个** release PR**（标题如 `chore(main): release 1.0.1`），更新 `backend/pyproject.toml` 版本号 + `backend/CHANGELOG.md`（版本级，与 `docs/changelogs/` 任务级并存，非冲突）。
3. 合并该 release PR → release-please 自动打 tag `v1.0.1` + 建 GitHub Release。

### 4.4 验证

```bash
# main 上最新一次 release-please run 的结论（匿名可查）
curl -s "https://api.github.com/repos/guoyamin/rag-qa-platform/actions/workflows/release-please.yml/runs?per_page=1" \
  | python -c "import sys,json; r=json.load(sys.stdin)['workflow_runs'][0]; print(r['conclusion'], r['head_sha'][:7])"
# 期望: success <sha>
```

---

## 5. detect-secrets 基线（踩坑备忘）

`.secrets.baseline` 是 detect-secrets 的已知密钥清单（只拦**新增**密钥，不报历史）。**关键坑**：

- **基线敏感于生成它的 Python 版本**：Python 3.10（宿主机）检出的密钥比 3.11+（CI）少。基线**必须在 CI 同款环境（Python 3.11+，Linux 容器）重新生成**，否则 CI 会因「基线比 CI 检出少」而误报失败。
- **Windows 宿主机会污染基线**：`pre-commit run --all-files` 在 Windows 上会把基线里的路径写成反斜杠、行尾变 CRLF，与 CI（Linux 正斜杠）不一致。规则：**基线由 Linux 生成并提交，Windows 宿主机的改动要 revert**。commit 钩子只扫暂存文件，非密钥文件不会改基线，故日常 commit 不受影响。
- **重新生成命令（容器内，Python 3.11+，Linux）**：
  ```bash
  docker exec rag-qa-backend bash -lc 'cd /app && detect-secrets scan --all-files --exclude-files "\.claude/" > .secrets.baseline'
  # 然后格式化 + 提交
  ```

只要改动了**含密钥的文件**（哪怕是注释里的示例 token）导致行号变化，就要重新生成基线，否则 CI detect-secrets 失败。

---

## 6. 验收清单（确认平台全部生效）

逐项打勾，全部 ✅ 即平台就绪：

- [ ] **Ruleset**：`curl .../rulesets` 返回 active 规则；任意 PR 的 6 个 required check 标为 required
- [ ] **CI 绿**：main 最新 `CI` run = success（`curl .../actions/workflows/ci.yml/runs?per_page=1`）
- [ ] **release-please 不再红**：main 最新 `release-please` run = success（需 §4.2 两个仓库设置已开）
- [ ] **Dependabot alerts 开启**：Settings → Code security 显示 Dependabot alerts / security updates = Enabled
- [ ] **直推 main 被拒**：本地 `git push origin main` 应被远端拒绝（证明保护生效）
- [ ] **本地门禁**：`make check` 容器内全绿（main 代码基线复核）

---

## 7. 已知遗留（不阻断，按需处理）

| 项 | 状态 | 说明 |
|---|---|---|
| **派生物一致性 CI 校验** | ✅ 已加（PR #32） | ci.yml `derivative-check` job：重新生成 api-schema + TS 类型后 `git diff --exit-code`。**⚠️ 待加入 Ruleset required status checks 才阻断合并**——见下方补充。 |
| **E2E 测试** | 未稳定 | `e2e-test` job 依赖 Playwright 起前后端服务，未稳定故非 required。核心问答功能成型后再补。 |
| **技能层（skills/）** | 可选 | HARNESS §10 第 5 步，示例 `onboard-endpoint` 技能 + 根索引。当前跳过，按需加。 |
| **剩余 Dependabot PR** | 可选 | #2/#4/#15-17/#20-22 等小版本升级，逐个 review 合并即可。 |
| **容器镜像扫描（Trivy）** | ✅ 已加（PR #32） | `container-scan.yml`：构建 backend 镜像 + trivy 扫描 + SARIF 上传。advisory（exit-code 0），不阻断；后续可收紧 fail-on-CRITICAL。 |

### 7.1 把 derivative-check 加入 Ruleset（让它真正阻断合并）

`derivative-check` job 已在 ci.yml，但默认不在分支保护必过清单，故漂移时**不阻断合并**。要让它强制生效：

1. 打开 **Settings → Rules → Rulesets** → 编辑 `main-protection`
2. 在 **Require status checks** 的搜索框输入 `Derivative Check`
3. 勾选 **`Derivative Check (OpenAPI/TS sync)`** 加入必过清单 → 保存

之后 PR 须 `derivative-check` 也绿才能合并（防「后端改了前端类型没同步」直接进 main）。

---

## 附：常用诊断命令（public 仓库匿名可用）

```bash
# main 最新 CI 结论
curl -s "https://api.github.com/repos/guoyamin/rag-qa-platform/actions/workflows/ci.yml/runs?branch=main&per_page=1" \
  | python -c "import sys,json; r=json.load(sys.stdin)['workflow_runs'][0]; print('CI:', r['conclusion'], r['head_sha'][:7])"

# 某 run 各 job/step 结论（定位哪步红）
RID=<run_id>
curl -s "https://api.github.com/repos/guoyamin/rag-qa-platform/actions/runs/$RID/jobs" \
  | python -c "import sys,json; [print(j['name'],'|',j['conclusion']) or [print('   ',s['name'],'|',s['conclusion']) for s in j['steps']] for j in json.load(sys.stdin)['jobs']]"

# 查 ruleset
curl -s https://api.github.com/repos/guoyamin/rag-qa-platform/rulesets | python -m json.tool
```
> 查**日志正文**需 token；查 run/job/step **结论**匿名即可（public 仓库）。
