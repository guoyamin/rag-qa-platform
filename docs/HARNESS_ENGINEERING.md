# Harness Engineering 工程门禁体系方案

> **版本**：v2.6（v1 重构 + right-size + 评审修订 v2.1 + 原则沉淀 v2.3 + 实现细化 v2.4 + DX 补丁 v2.5 + 实施状态 v2.6）
> **日期**：2026-08-02
> **状态**：**已实施**（步骤 1-6、8 落地并入 main；步骤 5 可选跳过；派生物 CI 校验 / E2E / Trivy 见 §0 待办）
> **定位**：智能问答平台（内部 RAG 应用）的工程基础设施总方案

---

## 0. 实施状态（v2.6，2026-08-02）

> **本节为落地事实**，配置细节见各 § 及 [harness-setup-runbook.md](harness-setup-runbook.md)。

| §10 步骤 | 内容 | 状态 | 落地证据（main sha） |
|---|---|---|---|
| ① 修 ci.yml 5 bug + CI 弄绿 | lint 走 pre-commit、lockfile、固定版本、bandit 阻断 | ✅ 完成 | CI green on main |
| ② 分支保护 | **Ruleset**（非 classic）：0 approvals + enforce admins + 6 required checks | ✅ 完成 | 见 runbook §1 |
| ③ 契约链 + 发版 | export-openapi + openapi-typescript + release-please | ✅ 完成 | PR #24 |
| ④ 治理文件 | CODEOWNERS / PR 模板 / Issue 模板 / Dependabot | ✅ 完成 | PR #23 / dependabot.yml |
| ⑤ 技能层 | skills/onboard-endpoint + 根索引 | ⏭️ 可选，跳过 | 按需再加 |
| ⑥ Alembic 初始化 | env.py + 初始迁移 + alembic.ini URL 可配置 + alembic check 门禁 | ✅ 完成 | PR #25 |
| ⑦ 总基准 + runbook | 本文件 + harness-setup-runbook.md | ✅ 本次完成 | 本 PR |
| ⑧ 复核基线 | main `make check` 全绿 | ✅ CI 全绿已证 | CI green @ 97f575c |

**CI 当前状态**（main）：`ci.yml` = ✅ success；`release-please.yml` = ❌ failure（见下）。

**release-please 修复（本 PR）**：`release-type: python` 缺 `path`，在仓库根找不到 `pyproject.toml`（实际在 `backend/`）→ release-please 在 main 每次 push 红 X。本 PR 加 `path: backend`。**仍需手动开两个仓库设置**（Settings → Actions → Workflow permissions = read+write；Allow Actions to create PRs = 勾），否则依旧失败——见 [runbook §4.2](harness-setup-runbook.md)。

**已知遗留（不阻断合并，见 runbook §7）**：
- 派生物一致性 CI 校验（§14.3）待加：CI 重新生成 api-schema + `git diff --exit-code`。
- E2E 测试（`e2e-test`）未稳定，非 required check。
- 容器镜像扫描 Trivy（§6）待加。
- Dependabot 安全告警需在 Settings 手动开启（runbook §3.2）。

---

## 1. 背景与目标

### 1.1 起因

上一迭代最大教训是「代码写完没自检」--71 文件代码未跑 mypy/ruff/pytest 就进 Review，导致 216 mypy 错、登录 500、创建 503。根因：自检是**自觉行为**，不是**强制门禁**。

v1（2026-08-01 已落地）建立了 pre-commit + `make check` 的基础门禁。本方案在 v1 基础上做两件事：

1. **补齐企业级强制层**：v1 的门禁可被 `--no-verify` 跳过、可直推 main，本质是「建议」不是「门禁」。补分支保护、CODEOWNERS、PR 模板等强制层。
2. **right-size**：剔除对内部应用过度的实践（SBOM 等），保留真正标配；按规模引入契约驱动与发版自动化。

### 1.2 核心目标

- 把「编码规范 / 自检清单」从自觉行为变为**机械化强制门禁**
- 覆盖**编码 -> 提交 -> 测试 -> 契约 -> 发版**全链路
- 配置遵循**工具原生位置**，不发明平行目录
- 强制力来自**分支保护**，不是配置文件

### 1.3 设计哲学

> **企业门禁的强制力来自分支保护，不是配置文件。** pre-commit 能被 `--no-verify` 跳过，CI 不通过也能直推 main--没有分支保护 + 必需检查，前面建的整套都是「建议」，不是「门禁」。

---

## 2. 设计原则

| 原则 | 含义 |
|---|---|
| **原生配置位置** | CI 进 `.github/workflows/`、lint 进 `pyproject.toml`、提交钩子进 `.pre-commit-config.yaml`。不发明 `.harness/`、`.agents/` 等平行目录（平行目录 = 工具静默失效）。 |
| **两段式门禁** | 快检查（lint/format/快速安全 bandit+detect-secrets）进 commit 钩子，秒级反馈；慢检查（mypy/pytest）进 `make check`，不阻塞提交。 |
| **门禁纯度** | `make check` / CI gate **全阻断**；advisory 检查（如依赖漏洞预检）单独 target/job 并醒目标注，**不混入 gate**--混入会让 dev 忽视全部警告。 |
| **派生物一致性校验** | 仓库内任何派生物（OpenAPI、生成 TS 类型、alembic 迁移、package-lock）须 CI 重新生成并 `git diff --exit-code`，否则必漂移。 |
| **契约派生而非手写** | OpenAPI 从代码导出（派生物）；**DB schema 单一真相源**（团队选 ORM models 或 DDL-first，当前为 models），不手写第二份。 |
| **单一真相源** | ADR 只在 `docs/adr/` 一处；OpenAPI 从代码导出；文档人与 AI 共用一棵 `docs/` 树。 |
| **跨厂商便携** | AI 技能内容放 `skills/`（便携源）+ 根路由索引；脚本放 `tools/`（纯脚本，任何 agent 可调用）。不绑死单一 agent 框架。 |
| **按规模 right-size** | 内部 RAG 应用，不做合规/售卖场景才需要的 SBOM 等。标配打底，高级实践按需引入；方案随讨论膨胀，须周期性复盘是否过重。 |

### 2.1 显式不做（避免重蹈覆辙）

- ❌ 不引入 `.harness/`、`.agents/`、`.claude/skills/`（作为唯一位置）、`.claude/memory/` 等自创/重复目录
- ❌ 不用 `local-ci-runner.sh` 替代提交门禁--保留 `.pre-commit-config.yaml` 两段式
- ❌ 不加根 `pyproject.toml` / 根 `package.json`--`Makefile` 已够编排
- ❌ 不开 `docs/ai-wiki/` 第二处 ADR--合并进现有 `docs/adr/`
- ❌ 不在 CI 用裸 `pip install`（不固定版本）--用 `requirements-dev.txt`
- ❌ 不在 `make check` 混入 advisory 检查--advisory 单独成 `make security-check`
- ❌ 不手写第二份 DB schema 文档（单一真相源，不另建 DDL/文档副本）

---

## 3. 目录结构（最终基准）

**图例**：✅ 已有保留 · 🆕 需新增 · 📝 自动生成产物 · ⚠️ 已有需修复

```
rag-qa-platform/
│
├── .github/                             # [原生标准] CI/CD 与治理
│   ├── workflows/
│   │   ├── ci.yml                       # ✅ ⚠️ 修 5 bug + 对齐 make check + 派生物一致性校验
│   │   ├── container-scan.yml           # 🆕 Trivy 镜像漏洞扫描（复用 ci.yml 构建的镜像）
│   │   └── release-please.yml           # 🆕 语义化版本 + 版本级 CHANGELOG
│   ├── CODEOWNERS                       # 🆕 按目录指定审查责任人（多人团队）
│   ├── PULL_REQUEST_TEMPLATE.md         # 🆕 PR 自检清单（make check/测试/文档/changelog）
│   ├── ISSUE_TEMPLATE/                  # 🆕 bug/feature 模板
│   └── dependabot.yml                   # 🆕 依赖更新配置（Dependabot 原生告警的主力载体）
│
├── .claude/                             # [Claude Code 原生] 仅 Claude 专属配置
│   ├── launch.json                      # ✅ dev server 预览配置
│   └── skills/                          # 🆕 可选：要 /slash 调用才加薄壳（指向 skills/）
│
├── docs/                                # [通用知识底座] 人与 AI 共享的唯一真相源
│   ├── adr/                             # ✅ ADR-008~015（唯一 ADR 源）
│   ├── api-contracts/                   # 🆕
│   │   └── api-schema.json              # 📝 由 FastAPI 导出的 OpenAPI 契约
│   ├── business/                        # 🆕 可选：业务状态机/权限矩阵
│   ├── changelogs/                      # ✅ 任务级变更清单（review 用，区别于版本级 CHANGELOG）
│   ├── lessons-learned/                 # ✅ 避坑指南唯一源（AI 动态记忆也并入此处）
│   ├── architecture/                    # ✅
│   ├── templates/                       # ✅ change-list 等文档模板
│   ├── HARNESS_ENGINEERING.md           # 🆕 本文件（总方案）
│   ├── CONTRIBUTING.md                  # 🆕 端到端 onboarding（含 setup-dev 全步骤 + 前置）
│   ├── CODING_STANDARD.md               # ✅ 编码法则层
│   ├── SECURITY_BASELINE.md             # ✅ 安全红线
│   ├── TEST_STRATEGY.md                 # ✅ 测试策略（含 DB 隔离配置）
│   ├── AI_COLLABORATION_RULES.md        # ✅ AI 协作白皮书
│   └── API.md / API_DESIGN.md / deployment.md  # ✅
│
├── backend/                             # [后端] Python FastAPI
│   ├── pyproject.toml                   # ✅ 原生配置：ruff/black/mypy（AI 无法破坏）
│   ├── pytest.ini                       # ✅ ⚠️ 加 --cov-fail-under=85
│   ├── requirements.txt                 # ✅ 运行期依赖（alembic==1.13.2 已锁，支持 check）
│   ├── requirements-dev.txt             # ✅ lint/安全工具固定版本（CI 也须用）
│   ├── .bandit                          # ✅ 安全扫描配置
│   ├── .env.example                     # ✅ 已有环境变量占位
│   ├── alembic.ini                      # ✅ ⚠️ 迁移配置（待初始化 + URL 可配置化，见 §12）
│   ├── Dockerfile / Dockerfile.dev      # ✅
│   ├── app/                             # ✅ 业务源码
│   └── tests/                           # ✅ 单元 + 集成测试
│
├── frontend/                            # [前端] Vue 3 + TypeScript
│   ├── package.json                     # ✅ ⚠️ 加 engines + openapi-typescript devDep
│   ├── package-lock.json                # 🆕 锁定依赖（CI 的 npm ci 必需）
│   ├── .npmrc                           # 🆕 engine-strict=true
│   ├── tsconfig.json / tsconfig.node.json # ✅ 原生 TS 配置
│   ├── vite.config.ts / vitest.config.ts / playwright.config.ts  # ✅
│   ├── .eslintrc.cjs / .prettierrc      # ✅ 原生 lint/格式化
│   ├── Dockerfile / Dockerfile.dev / nginx.conf  # ✅
│   ├── index.html / public/             # ✅
│   ├── src/                             # ✅ 视图/状态/组件
│   └── tests/                           # ✅ 前端测试
│
├── tools/                               # 🆕 [通用约定] 工具脚本（跨厂商便携）
│   ├── export-openapi.py                # 🆕 从 FastAPI 导出 api-schema.json（脚本内注入 mock env）
│   ├── generate-api-client.sh           # 🆕 从 OpenAPI 生成前端 TS 类型（openapi-typescript）
│   └── hooks/                           # 🆕 vendor 的卫生钩子（python+PyYAML）+ check-commit-msg.sh
│
├── templates/                           # 🆕 [通用约定] 代码骨架（防野路子）
│   ├── fastapi-router.py.tpl            # 🆕 后端标准路由 + Pydantic 校验
│   └── vue-component.vue.tpl            # 🆕 前端 Element Plus + Pinia 标准组件
│
├── skills/                              # 🆕 [便携技能源] 厂商中性的技能内容真相源
│   └── onboard-endpoint/                # 🆕 示例：新接口上线引导
│       └── SKILL.md
│
├── deployment/                          # ✅ [基础设施] 容器化编排
│   ├── docker-compose.dev.yml           # ✅ 容器已挂 main（suspicious-allen 已解决，见 §12）
│   └── docker-compose.yml               # ✅
│
├── .pre-commit-config.yaml              # ✅ ⚠️ 加卫生/commit-msg/.env 钩子
├── Makefile                             # ✅ ⚠️ 加 security-check/gen-client 目标（alembic check 待初始化）
├── .editorconfig                        # 🆕 跨编辑器基线（缩进/字符集/eol）
├── .nvmrc                               # 🆕 锁定 Node 版本（与 CI 对齐）
├── .gitattributes                       # ✅ 强制 LF 行尾（Windows 必备）
├── .secrets.baseline                    # ✅ 密钥基线
├── .gitignore                           # ✅ ⚠️ 确认忽略 .env
├── CLAUDE.md                            # 🆕 薄指针 -> AGENTS.md（根路由唯一源）
├── AGENTS.md                            # 🆕 跨厂商中性根路由 + 技能索引（唯一源）
└── README.md                            # ✅
```

---

## 4. 技能层（Skills）便携机制

Skill 的**自动发现**是厂商专属机制（Claude 扫 `.claude/skills/`、Cursor 扫 `.cursor/rules/`），没有跨厂商统一的自动发现格式。本方案用三层结构实现「便携内容 + 各 agent 可用」：

### 4.1 三层结构

| 层 | 位置 | 作用 |
|---|---|---|
| **便携源** | `skills/<name>/SKILL.md` | 厂商中性的内容真相源（指令 + 引用 `tools/` 脚本） |
| **根索引** | `AGENTS.md`（唯一源）/ `CLAUDE.md`（薄指针） | 每个 skill 一行 name + 触发条件；agent 读根路由即知技能存在 |
| **可选适配层** | `.claude/skills/<name>/SKILL.md` | 薄壳，仅 frontmatter + 一行指针；要 `/slash` 调用或框架级主动建议才加 |

### 4.2 SKILL.md 通用格式

```markdown
---
name: onboard-endpoint
description: 上线一个新 API 接口的标准化流程
when: 用户要求新增后端接口/路由时
---

## 步骤
1. 套用 templates/fastapi-router.py.tpl 建路由
2. 新建对应 Pydantic 模型，注册到 main.py
3. 运行 `python tools/export-openapi.py` 更新 docs/api-contracts/api-schema.json
4. 运行 `make gen-client` 重新生成前端 TS 类型
5. 套用 templates/vue-component.vue.tpl 加前端调用
6. 套模板补测试，跑 make check
```

`name` / `description` / `when` 是各厂商 frontmatter 的公共子集，可映射到 Cursor 的 `globs` / Claude 的触发。

### 4.3 发现机制

- **Claude Code**：读根 `CLAUDE.md`（指向 `AGENTS.md`）技能索引，任务匹配时去找 `skills/<name>/SKILL.md` 执行。要 `/onboard-endpoint` 斜杠调用再加 `.claude/skills/` 薄壳。
- **Cursor / Codex / 其他**：读根 `AGENTS.md` 同一份索引。
- **脚本层**：技能调用的脚本在 `tools/`，任何 agent 跑 `python tools/...` 都行。

### 4.4 取舍

- **根路由去重**：`AGENTS.md` 为唯一源，`CLAUDE.md` 只一行指向（"见 AGENTS.md"）。不用 symlink（Windows 上不可靠）。零漂移。
- **薄壳按需**：先只做 `skills/` + 根索引（90% 价值、100% 便携、零重复）。仅当确实需要 `/slash` 显式调用或 Claude UI 主动建议时，再为那几个技能加 `.claude/skills/` 薄壳。

### 4.5 工作流集合（演进目标）

`skills/` 首批只搭壳 + 一个 `onboard-endpoint` 示例。演进目标是覆盖软件生命周期的一套工作流：`feature-development` / `bug-fix` / `refactor` / `api-change` / `database-change` / `rag-pipeline-change` / `frontend-page-development` / `release` / **`review`**（Review Agent：AI 完成代码后自动检查架构违规/重复代码/缺测试/安全规范/文档/接口影响），逐个按实际场景填充，不一次性堆全。这让 AI 层从脚手架走向实质的工作流库。

---

## 5. 门禁体系

### 5.1 提交门禁（pre-commit，秒级）

`.pre-commit-config.yaml` 采用 `repo: local + language: system`，调用本机已装工具，不依赖 GitHub 网络（适配国内环境）。

**现有钩子（保留）**：
- 后端：ruff / black / isort / bandit
- 全仓库：detect-secrets（基于 `.secrets.baseline`，只拦新增密钥）
- 前端：prettier / eslint

**新增钩子**：
- **卫生钩子**（vendor 到 `tools/hooks/`，用 **python + PyYAML** 实现，离线且比 bash 稳健）：
  - `check-yaml` / `check-json`：拦截写坏的 `ci.yml` / `.pre-commit-config.yaml`
  - `check-merge-conflict`：拦截未解决的合并冲突标记
  - `check-large-files`：拦截误提交大文件
  - `trailing-whitespace` / `end-of-file-fixer`：基础格式
- **`.env` 提交守卫**：拦截 `.env` 误提交
- **commit-msg**（`tools/hooks/check-commit-msg.sh`）：校验 Conventional Commits 格式（`feat:` / `fix:` / `docs:` 等）。**这是 release-please 的前提**。

> 注：mypy / pytest 是慢检查，**不进 pre-commit**（见 §2 两段式门禁），放 `make check` 与 CI。

### 5.2 完整门禁（make check，容器内）

后端在容器 `rag-qa-backend` 内执行（本机无 3.11 环境），前端本机执行。

**定位**：`make check` 是**纯阻断**门禁--任一项失败即返回非零，**不混入 advisory 检查**（见 §2 门禁纯度）。

**包含（全阻断）**：ruff + black + isort + mypy --strict + bandit + pytest（`--cov-fail-under=85`）。

**待加入（前置未就绪）**：`alembic check`（Alembic 1.9+，比对模型与 migration 脚本，非破坏性）--待 Alembic 初始化后加入 make check 与 CI（见 §14.4、§12）。**当前不进 make check，否则必失败**（Alembic 未初始化）。

**DB 安全**：`make check` 涉及 DB 的步骤（pytest 集成测试）一律用**隔离测试库**（sqlite 内存或 `rag_qa_test`），**不连开发库**，防误操作开发数据。具体配置（`.env.test` 或 conftest fixture 切换 `DATABASE_URL`）见 `TEST_STRATEGY.md` / `CONTRIBUTING.md`。

**移出（advisory，不进 make check）**：依赖漏洞预检 `pip-audit` / `npm audit` 拆到独立 `make security-check`（仅告警，不阻断）；CI 主力靠 Dependabot 原生告警。可逆性迁移测试见 §11 backlog。

**门槛策略**：`--cov-fail-under=85` 为当前全局门槛（基线 92%，留余量）；mypy --strict 全项目保持。未来可按核心/边缘模块分阶细化（核心更严），**不降标准**；若 AI/LLM 模块将来出现第三方库 typing 摩擦，可按核心 strict / AI 模块宽松分阶，不预先放松。

### 5.3 CI（.github/workflows/ci.yml）

**CI 与 make check 对齐（关键）**：CI 的 required status check 集合 = `make check` 的全部阻断项。lint（ruff/black/isort/eslint/prettier）走 `pre-commit run --all-files`（替代手写 lint 步骤）；**mypy --strict / pytest（含 `--cov-fail-under=85`）/ bandit 保持独立 required job，不被 pre-commit 替代**（它们不在 `.pre-commit-config`）。alembic check 待 Alembic 初始化后加入 CI。如此 §5.4「PR 必过 CI」才等价于「必过 make check 门禁」。

**修复 v1 的 5 个 bug**：
1. 前端无 lockfile -> `npm ci` 必失败（补 `package-lock.json`）
2. CI 工具版本未固定 -> 改 `pip install -r requirements-dev.txt`
3. `detect-secrets` 无 `--baseline` -> 加 `--baseline .secrets.baseline`
4. `bandit || true` 非阻断 -> 去 `|| true`，用 `-c .bandit -ll`，作为 required job
5. CI 重复实现 **lint** 与 pre-commit 漂移 -> **lint 步骤**改跑 `pre-commit run --all-files`（CI 有网络）；mypy/pytest 等 slow 检查保持独立 job 不变

**执行顺序（关键）**：`pre-commit run --all-files` 的前端钩子用 `npx --no-install`，**必须 `node_modules` 已存在**。故 CI 顺序为：先 `pip install -r requirements-dev.txt` + `npm ci`，**再** `pre-commit run --all-files`。ci.yml 中以注释加粗警示，防后续维护误调顺序。

**新增 job / 步骤**：
- **镜像构建与扫描衔接**：`ci.yml` 内独立 job 构建镜像并产出 tag，`container-scan.yml`（或同 workflow 后续 job）复用该 tag 扫描，避免重复构建
- 依赖扫描：pip-audit + npm audit（**独立非阻断 job**，仅告警，不使 workflow 失败--见 §2 门禁纯度）
- **派生物一致性校验**（见 §14.3 / §2）：重新跑 `python tools/export-openapi.py` + `make gen-client`，再 `git diff --exit-code`；**失败时打印明确指引**：`OpenAPI/types out of sync. Run: python tools/export-openapi.py && make gen-client, then commit.`，便于 AI/新手定位
- 覆盖率上传：暂缓（见 §11）

### 5.4 分支保护（强制层--runbook，需平台操作）

> 这是把「配置」变「强制」的**唯一手段**。没有它，前面所有门禁都可被 `--no-verify` 或直推 main 绕过。

**main 分支保护规则**（已落地，见 [harness-setup-runbook.md §1](harness-setup-runbook.md)）：
- 禁止直推 main，必须 PR
- PR 必过 CI（required status checks：§5.3 对齐 make check 的全部 job，共 6 个）
- **required approving reviews = 0**（单人项目：classic「至少 1 review」会让作者无法合并自己 PR，故改用 **Ruleset**，0 approvals + enforce for administrators，既强制 CI 又不卡自己）
- linear history（squash）
- 上述配置 + CODEOWNERS 规则 + 验证方法详见 `docs/harness-setup-runbook.md`

**前置（已满足）**：git remote 已配（SSH-443），CI 已运行，分支保护已激活。

---

## 6. 安全体系

| 层 | 措施 | 状态 |
|---|---|---|
| 代码漏洞 | bandit（后端静态扫描，required） | ✅ 已有 |
| 密钥泄露 | detect-secrets + `.secrets.baseline`（只拦新增） | ✅ 已有 |
| 依赖漏洞（SCA） | **GitHub Dependabot 原生告警（主力）** + `make security-check` 本地预检（advisory） | 🆕 主力靠 Dependabot |
| 容器镜像 | Trivy 扫描镜像（复用 CI 构建镜像） | 🆕 |
| 环境变量 | `.env.example` 占位 + `.env` 入 `.gitignore` + 提交守卫 | ✅/🆕 |

**关于 SCA 的 right-size**：当代供应链（log4j/xz 之后）依赖扫描是标配，但绝大多数团队用 **GitHub Dependabot 原生告警**（免费、自动、开箱即用），而非自己在 CI 里接 pip-audit 当阻断门。本方案以 Dependabot 为主，pip-audit/npm audit 仅作 `make security-check` 本地 advisory 预检，**不进 `make check`、不阻断 CI**（CI 里也是独立非阻断 job）。

---

## 7. 契约与发版

### 7.1 OpenAPI 契约（从代码导出）

- `tools/export-openapi.py`：从 FastAPI 逆向导出 `docs/api-contracts/api-schema.json`
- 契约是**派生物**，非手写--手写 JSON 必然与代码漂移（见 §2 契约派生）
- 后端改路由 -> 跑导出脚本 -> 提交更新的 `api-schema.json`
- **脚本健壮性**：脚本导入 app 前**无条件注入完整 mock env**（`DATABASE_URL=sqlite:///:memory:`、`SECRET_KEY=...` 等），不依赖 config 默认值或 `.env` 存在--防未来某开发新增无默认的必填配置项导致 CI 导出崩溃

### 7.2 OpenAPI 客户端生成（契约驱动前端）🆕

- `tools/generate-api-client.sh`：从 `api-schema.json` 用 **`openapi-typescript`** 生成前端 **TS 类型**（只生成类型，不生成运行时 client；请求函数仍人工在 `api/` 层封装，保留错误处理/token 刷新/埋点）
- `openapi-typescript` 须加入 `frontend/package.json` 的 devDependencies 并锁版本（否则 `npm ci` 不装，`make gen-client` 与 CI 派生物校验失败）
- `make gen-client`：一键重新生成
- **CI 强校验**（见 §5.3 / §14.3）：CI 重新生成并 `git diff --exit-code`，派生物不一致即 CI 红--不靠自觉记 `make gen-client`
- **价值**：后端改接口 -> 前端用到改动处 **tsc 编译直接报错**，运行期才发现的断裂提前到编译期

### 7.3 发版自动化（release-please）🆕

- `.github/workflows/release-please.yml`：从 Conventional Commits 自动推算语义化版本 + 生成**版本级** CHANGELOG
- **CHANGELOG 双源澄清**（非冲突）：`docs/changelogs/` 是**任务级变更清单**（每次 AI 交付的 review 输入，见 AI_COLLABORATION_RULES §5）；release-please 的是**版本级发版汇总**。两者用途不同，非第二真相源。配置 release-please 的 `changelog-path` 为根 `CHANGELOG.md`，与 `docs/changelogs/` 共存
- **前提**：Conventional Commits 强制（由 §5.1 的 commit-msg 钩子保障）
- **价值**：消除手动维护版本号与 changelog 的琐碎与不一致

---

## 8. 协作治理

| 文件 | 作用 |
|---|---|
| `.github/CODEOWNERS` | 按目录指定审查责任人，强制领域 owner 审查（团队多人，已确认） |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR 自检清单：跑过 `make check` / 补了测试 / 更新了文档 / 关联 changelog |
| `.github/ISSUE_TEMPLATE/` | bug / feature 标准化提交模板 |
| `docs/CONTRIBUTING.md` | 端到端 onboarding：列全 `make setup-dev` 步骤（**含 pipx + Python 3.11 前置**、宿主机工具、容器工具、npm ci、pre-commit install、.env）、自检流程、提交规范 |
| `AGENTS.md`（源）/ `CLAUDE.md`（指针） | AI 根路由唯一源 + 技能索引；CLAUDE.md 一行指向，防双份漂移 |

---

## 9. 与现状的差异（落地清单）

### 9.1 新增文件（A 类，统一实施时落盘）

| 路径 | 说明 |
|---|---|
| `frontend/package-lock.json` | `npm install` 生成，修复 CI `npm ci` |
| `frontend/.npmrc` + `package.json` engines | `engine-strict=true`，锁 Node 版本 |
| `frontend/package.json` devDependencies | 加 `openapi-typescript` 并锁版本（`make gen-client` 与 CI 派生物校验依赖） |
| `.nvmrc` | 锁 Node 20，宿主机与 CI 对齐 |
| `.editorconfig` | 跨编辑器基线 |
| `CLAUDE.md` / `AGENTS.md` | AI 根路由（AGENTS.md 源 + CLAUDE.md 指针）+ 技能索引 |
| `tools/export-openapi.py` | 导出 OpenAPI（脚本内注入 mock env） |
| `tools/generate-api-client.sh` | 生成前端 TS 类型（openapi-typescript） |
| `tools/hooks/` | vendor 卫生钩子（python+PyYAML）+ `check-commit-msg.sh` |
| `templates/fastapi-router.py.tpl` / `vue-component.vue.tpl` | 代码骨架 |
| `skills/onboard-endpoint/SKILL.md` | 示例技能 |
| `docs/api-contracts/api-schema.json` | OpenAPI 契约（生成） |
| `docs/CONTRIBUTING.md` | 端到端 onboarding（含 setup-dev 全步骤 + 前置） |
| `.github/CODEOWNERS` / `PULL_REQUEST_TEMPLATE.md` / `ISSUE_TEMPLATE/` | 治理文件 |
| `.github/dependabot.yml` | Dependabot 配置 |
| `.github/workflows/container-scan.yml` | Trivy 镜像扫描（复用 ci.yml 镜像） |
| `.github/workflows/release-please.yml` | 发版自动化 |

### 9.2 修复文件（已有，对应 v1 遗留问题）

| 路径 | 修复内容 |
|---|---|
| `.github/workflows/ci.yml` | 修 5 bug（lint 改 `pre-commit run --all-files`，安装顺序先 `npm ci`）+ required check 对齐 make check（mypy/pytest/bandit 独立 required job）+ 派生物一致性校验（失败打印指引）+ Trivy job（复用构建镜像） |
| `backend/pytest.ini` | 加 `--cov-fail-under=85` |
| `.pre-commit-config.yaml` | 加卫生/commit-msg/.env 钩子 |
| `Makefile` | 加 `security-check`（advisory）/ `gen-client` 目标；`alembic check` 待 Alembic 初始化后加入 |
| `Makefile` 的 `setup-dev` | 增加宿主机 `pipx` 装 pre-commit 工具链（对齐 requirements-dev.txt）+ 自检 pipx/Python 前置并打印兜底（见 §14.1） |
| `backend/alembic.ini` | URL 可配置化（现硬编码开发库 `postgresql+asyncpg://...localhost:5432/rag_qa`）；补 env.py + 初始迁移（Alembic 初始化） |
| `.gitignore` | 确认忽略 `.env` |

### 9.3 平台设置（B 类，已写 runbook）

> 详见 [harness-setup-runbook.md](harness-setup-runbook.md)。落地状态：

1. ~~建 git remote~~ ✅（SSH-443，仓库 public）
2. **main 分支保护** ✅：Ruleset（0 approvals + enforce admins + 6 required checks + squash）—— runbook §1
3. **Dependabot** ✅ 配置生效：alerts/security updates 需在 Settings 手动开 —— runbook §3
4. **release-please** ✅ 配置生效：需在 Settings 开 Workflow permissions + Allow Actions create PRs —— runbook §4
5. Trivy：待加（见 §0 待办）

---

## 10. 实施顺序（统一实施，分批验证）

> **落地状态见 §0**（步骤 1-6、8 ✅；步骤 5 ⏭️ 可选跳过）。以下为原计划顺序，保留作实施路径参照。

1. **零风险增量**：`frontend/package-lock.json`、`.nvmrc`、`.editorconfig`、`.gitignore` 核对、根 `AGENTS.md`+`CLAUDE.md`、`tools/export-openapi.py`（含 mock env）、`docs/api-contracts/`、`docs/CONTRIBUTING.md`
2. **门禁增强**：`.pre-commit-config.yaml`（卫生 + commit-msg + .env 钩子，vendor `tools/hooks/`）、`Makefile`（`security-check` + `gen-client` 目标；`setup-dev` 补宿主机工具 + 自检前置；`alembic check` 待初始化）、`ci.yml`（修 5 bug + 安装顺序 + `pre-commit run --all-files` 仅 lint + required check 对齐 make check + 派生物校验 + Trivy job）
3. **契约与发版**：`tools/generate-api-client.sh` + `make gen-client` + `openapi-typescript` 进 devDependencies、`.github/workflows/release-please.yml`、`.github/dependabot.yml`（commit-msg 钩子已在第 2 步保障 conventional commits 前提）
4. **治理文件**：`CODEOWNERS`、`PULL_REQUEST_TEMPLATE.md`、`ISSUE_TEMPLATE/`
5. **技能层**：`skills/onboard-endpoint/SKILL.md` 示例 + 根路由索引段
6. **Alembic 初始化**：补 env.py + 初始迁移 + alembic.ini URL 可配置化；完成后把 `alembic check` 加入 make check 与 CI
7. **总基准 + runbook**：`docs/HARNESS_ENGINEERING.md`（本文件，持续更新）+ `docs/harness-setup-runbook.md`（B 类平台设置步骤）
8. **复核基线**：容器已挂 main，跑一次 `make check` 确认 main 当前代码全绿（无需重建容器）

---

## 11. 待办（Backlog，按需引入）

以下实践当前未实施，**等具体驱动出现再引入**：

| 实践 | 是什么 | 触发条件 |
|---|---|---|
| **SBOM**（软件物料清单） | Syft 生成全部依赖（含间接）的清单（SPDX/CycloneDX 格式），Grype 查漏洞。合规要求（美行政令 14028 / 欧盟 CRA）针对卖软件/卖给政府 | 需要合规认证 / 软件对外售卖 |
| **Codecov 趋势** | 覆盖率历史趋势 + 逐 PR「覆盖率变化」高亮未测新增代码。门槛防回退是刚需，趋势是可视化 | 团队扩大 / 需要 PR 级覆盖率可视化 |
| **迁移可逆性测试** | CI 里 `alembic upgrade head` + `downgrade -1` 往返，抓坏 `downgrade()`。防回滚发布时卡死。需 Alembic 先初始化 | 部署频繁 / 常回滚 / 零停机 |
| **AI 编码效能指标采集分析** | 采集 AI 编码任务的量化指标（token 消耗、自修正轮数、AST 拦截命中率、交付耗时），分析 AI Coding 效能与质量趋势。可引入 Langfuse 或 CI 内采集落看板 | 需量化 AI 编码 ROI / 推广 AI Coding 需数据支撑 / 团队扩大考核效能 |
| **RAG 评测门禁** | RAGAS + golden dataset 评估回答质量（Faithfulness / Answer Correctness / Retrieval Recall / Citation Accuracy），拦「代码 100 分、业务 0 分」。当前 `test_rag.py` 是 mock 单测，不评回答质量 | **核心问答功能实现后**再考虑（用户已确认） |

---

## 12. 已知前置与风险

| 项 | 影响 | 处置 |
|---|---|---|
| **无 git remote** | CI / 分支保护 / Dependabot / release-please 全部待此激活 | 实施第 1~5 步可先行（纯本地文件）；B 类平台设置需先配 remote |
| **Alembic 未初始化** | migrations 目录空、无 env.py；`alembic check` 跑不了；alembic.ini 硬编码开发库 URL；schema 实际经 models `create_all` 建表 | 实施第 6 步初始化（env.py + 初始迁移 + URL 可配置化），`alembic check` 待此后启用 |
| ~~dev 容器挂载旧 worktree~~（**已解决**） | 实测当前 `rag-qa-backend` 容器已挂 main（`D:/Project/Demo/backend/...`），不再挂 suspicious-allen；`make check` 现跑 main 代码 | 仅需复核 `make check` 基线，无需重建 |
| **ci.yml 5 个 bug** | 配 remote 后 CI 必红 | 实施第 2 步修复 |
| **覆盖率门槛值** | 85% 留余量 vs 90% 顶住防回退 | 暂定 85%，可按团队共识调整 |

---

## 13. 使用方式

```bash
# 首次启用（自检前置 + 宿主机装 pre-commit 工具 + 容器装 lint 工具 + 装 git 钩子 + npm ci）
make setup-dev

# 之后每次 commit 自动触发提交门禁（秒级）
git commit ...

# 提交前跑完整门禁（纯阻断，与 CI required check 一致；当前阶段 alembic check 挂起，待 Alembic 初始化后加入，见 §10/§14.4）
make check

# 依赖漏洞 advisory 预检（不阻断，单独目标）
make security-check

# 后端改路由后，更新契约并重新生成前端类型
python tools/export-openapi.py
make gen-client

# 新接口上线（AI 技能引导）
# 在 AGENTS.md 索引中查 onboard-endpoint 技能
```

---

## 14. 评审修订（v2.1）

基于方案评审，修订 5 项（问题 1/2/3 + 优化建议 4；问题 4 已过时，见 §12 更正）：

### 14.1 `make setup-dev` 补宿主机工具安装（影响 §5.1 / §9.2 / §13）
- **问题**：现 `make setup-dev` 只 `docker exec` 把工具装进容器 + `pre-commit install`，但 pre-commit 钩子在**宿主机**执行 ruff/black/isort/bandit（`language: system`）。宿主机未装这些工具时，commit 钩子激活却 `command not found`，秒级门禁失效。
- **修法**：`make setup-dev` 增加一步，用 `pipx install`（或 `pip install --user`）在宿主机装 pre-commit 工具链，版本对齐 `requirements-dev.txt`；且启动时**自检 pipx / Python 3.11+ 前置，缺失则打印安装指引**（不静默失败）。**不采用**评审建议的「pre-commit 容器化执行」--每次 commit 都 `docker exec` 会把秒级变十几秒，违背快检查初衷。

### 14.2 锁定 Node 版本（影响 §5.3 / §9.1）
- **问题**：`package-lock.json` 修了 `npm ci` 硬失败，但宿主机 Node 版本不齐仍可能让锁文件漂移。
- **修法**：新增 `.nvmrc`（锁 Node 20）+ `package.json` 的 `engines` 字段 + `.npmrc` 的 `engine-strict=true`。CI 已用 `node-version: 20`，`.nvmrc` 让宿主机对齐。

### 14.3 CI 派生物一致性校验（影响 §5.3 / §7.2）-- 最重要修订
- **问题**：§7.2 契约驱动工作流未纳入 CI 强制。dev 忘记 `make gen-client` 就提交，「后端改了前端没同步」老问题原样存在，契约驱动形同虚设。
- **修法**：CI 加一步--重新跑 `python tools/export-openapi.py` + `make gen-client`，再 `git diff --exit-code`。提交的 `docs/api-contracts/api-schema.json` 与生成的客户端类型与最新代码不一致即 CI 红（generated-artifact 一致性校验标准模式）；**失败输出打印明确修复指引**。v2.3 将此升格为 §2 横切原则，覆盖所有派生物。

### 14.4 `alembic check`（待 Alembic 初始化后启用，影响 §5.2）
- **问题**：后端「只改模型忘生成 migration」会导致线上启动 503。
- **修法**：`alembic check`（Alembic 1.9+，已锁 1.13.2）比对模型与最新 migration，发现未迁移的模型变更即报错，非破坏性、不碰开发库。
- **前置**：项目 Alembic **当前未初始化**（migrations 目录空、无 env.py，schema 经 models `create_all` 建表）。需先补 env.py + 初始迁移 + alembic.ini URL 可配置化（现硬编码开发库），**之后**才把 `alembic check` 加入 make check 与 CI。在此之前不进 make check，否则必失败。

### 14.5 §12 容器风险更正
- §12 原「dev 容器挂旧 worktree（suspicious-allen）需用户确认重建」已过时：实测当前 `rag-qa-backend` 容器 bind mount 已指向 main（`D:/Project/Demo/backend/...`），问题已解决。仅剩「复核 `make check` 基线」一步，无需重建。

---

## 15. 原则沉淀（v2.3）

基于三份外部评审的复盘，吸收以下原则（具体实现按项目实情定，不连坐否决）：

- **派生物一致性校验（横切）**：§14.3 已对 OpenAPI 落地，v2.3 升格为 §2 通用规则，覆盖所有 generated artifact（OpenAPI / 生成类型 / 迁移 / lockfile）。
- **门禁纯度**：§2 新增原则；§5.2 已重构（`make check` 纯阻断，pip-audit/npm audit 移到 `make security-check`，CI 里独立非阻断 job）。
- **契约派生而非手写**：§2 原则；OpenAPI 从代码导出。DB schema 经 v2.4 修正为「单一真相源，团队选（models 或 DDL-first）」，不手写第二份。
- **skills 工作流集合**：§4.5 演进目标（含 Review Agent，见 v2.4 扩充）。
- **make check 不碰开发库**：§5.2 已写明用隔离测试库。
- **CONTRIBUTING 端到端 onboarding**：§8/§9.1 已要求列全 `setup-dev` 步骤（v2.4 补 pipx/Python 前置）。
- **分模块质量门槛（未来细化）**：当前全局 85% + mypy strict 全项目；未来可按核心/边缘模块分阶，不降标准。

**RAG 评测门禁**（评审建议的最重要一条）按用户决定**功能实现后再考虑**，已记入 §11 backlog。

---

## 16. 实现细化（v2.4）

基于评审 X/Y/Z 的有效项，补充实现细节（不碰已定决策：RAG 评测仍 backlog、release-please 仍保留、覆盖率仍 85%）：

- **Alembic 修正**：§2 DB schema 改「单一真相源，团队选，当前为 models」；§3 修正 alembic.ini 表述（待初始化）；alembic check 移出 make check 待初始化（§5.2/§14.4）；alembic.ini URL 可配置化（§9.2）；§12 增「Alembic 未初始化」风险；§10 增第 6 步「Alembic 初始化」。
- **CI↔make check 对齐**（§5.3）：明确 required check 集 = make check 阻断项；lint 走 `pre-commit run --all-files`（仅替代 lint 步骤），mypy/pytest/bandit 独立 required job 不被替代；alembic check 待初始化后加入 CI。消除「pre-commit 替代全部检查」歧义。
- **OpenAPI 工具链**（§7.1/§7.2/§9.1/§5.3）：export 脚本无条件注入 mock env；`openapi-typescript` 进 frontend devDependencies；派生物校验失败打印明确修复指引。
- **AI 工作流**（§4.5）：加 Review Agent + 扩充工作流清单（database-change/rag-pipeline-change/frontend-page-development/release）。
- **小补丁**：setup-dev 自检 pipx/Python 前置并打印兜底（§14.1）；CONTRIBUTING 加 pipx/Python 3.11 前置（§8）；DB 测试隔离具体配置指向 TEST_STRATEGY/CONTRIBUTING（§5.2）；镜像构建与扫描衔接说明（§5.3）；mypy 未来分阶备注（§5.2）。

---

## 附：Makefile 目标清单（实施参考）

落地 `Makefile` 时按此清单，避免多节对照漏 target：

| 目标 | 类型 | 说明 |
|---|---|---|
| `make setup-dev` | 一次性 | 自检 pipx/Python 3.11 前置；宿主机 `pipx` 装 pre-commit 工具链（对齐 requirements-dev.txt）；容器内装 lint 工具；`pre-commit install`；`npm ci`（见 §14.1） |
| `make check` | 阻断 | 纯阻断完整门禁，与 CI required check 一致：ruff + black + isort + mypy --strict + bandit + pytest（`--cov-fail-under=85`）。**当前不含 alembic check**（待 Alembic 初始化，见 §10 第 6 步 / §14.4） |
| `make security-check` | advisory | 依赖漏洞预检 pip-audit + npm audit，仅告警不阻断（见 §5.2 / §6） |
| `make gen-client` | 一次性 | 从 `docs/api-contracts/api-schema.json` 用 openapi-typescript 重新生成前端 TS 类型（见 §7.2） |
| `make lint-backend` / `lint-frontend` / `test-backend` / `test-frontend` | 已有 | 分项 lint/test，保留自 v1 |
| `make dev` / `dev-down` | 已有 | 启停 docker-compose dev 环境 |
| `make clean` | 已有 | 清理缓存/构建产物 |

> 派生物导出 `python tools/export-openapi.py` 是脚本而非 target，常与 `make gen-client` 串联：后端改路由后 `python tools/export-openapi.py && make gen-client`。

---

## 附：方案演进记录

- **v1（2026-08-01）**：建立 pre-commit + `make check` 基础门禁（分支 `claude/harness-engineering`，见 `docs/changelogs/2026-08-01-harness-engineering.md`）
- **v2（2026-08-01）**：补齐分支保护等强制层；right-size 剔除 SBOM 等过度实践；引入契约驱动（OpenAPI 客户端生成）与发版自动化（release-please）；确立跨厂商便携技能机制
- **v2.1（2026-08-01，评审修订）**：补 setup-dev 宿主机工具安装、Node 版本锁定、CI 派生物一致性校验、`make check` 加 `alembic check`；更正 §12 容器风险（已挂 main）
- **v2.3（2026-08-01，原则沉淀）**：吸收三份评审有效内核--派生物一致性升格为横切原则、门禁纯度（pip-audit/npm audit 移出 `make check` 成 `make security-check`）、契约派生而非手写、skills 工作流集合、`make check` 不碰开发库、CONTRIBUTING 端到端 onboarding、CI 安装顺序与卫生钩子用 PyYAML；RAG 评测门禁记入 backlog；消除 §3/§5.2/§9.2/§10/§13 间的前后矛盾
- **v2.4（2026-08-01，实现细化）**：Alembic 修正（alembic check 移出 make check 待初始化、alembic.ini URL 可配置化、§2 DB schema 改「单一真相源」、§12 增风险、§10 增初始化步骤）；CI↔make check 对齐（required check 集 = make check 阻断项，lint 走 pre-commit 不替代 mypy/pytest，消除歧义）；OpenAPI 工具链（export 脚本无条件 mock env、openapi-typescript 进 devDep、派生物校验失败明确指引）；§4.5 加 Review Agent + 扩充工作流；setup-dev 自检、CONTRIBUTING pipx 前置、DB 隔离配置、镜像扫描衔接、mypy 分阶备注；再次通读消除 Alembic/CI 相关前后矛盾
- **v2.5（2026-08-01，DX 补丁）**：增「Makefile 目标清单」附录（实施参考）；§13 标注当前阶段 alembic check 挂起；§16 DB schema 补「当前为 models」对齐 §2/§15
- **v2.6（2026-08-02，实施状态）**：步骤 1-6、8 落地并入 main（CI green @ 97f575c），新增 §0 实施状态总览；分支保护确认用 **Ruleset**（0 approvals + enforce admins，单人硬门禁，纠正 §5.4「至少 1 review」歧义）；§9.3 B 类设置标注完成 + 指向 runbook；产出 `docs/harness-setup-runbook.md`（平台设置复现手册）；修复 release-please（`release-type: python` 缺 `path` 致 main 红 X → 加 `path: backend`，版本级 CHANGELOG 落 `backend/CHANGELOG.md`）；待办：派生物 CI 校验、E2E、Trivy、Dependabot alerts 手动开启
