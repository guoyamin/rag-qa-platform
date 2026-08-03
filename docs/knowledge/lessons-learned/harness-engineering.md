# Harness Engineering 搭建复盘

搭建工程门禁体系（HARNESS_ENGINEERING.md，8 步方案）过程中踩的坑。分两类：**方案级错误**（设计本身错了，得回改方案——最有复盘价值）与**实施坑**（方案对、实现时踩的）。

> 对应方案文档版本演进：v1 → v2.7，**几乎每次升版本就是纠正一个方案级错误**。

---

## 一、方案级错误（设计错了，回改方案）

### 1. 分支保护「≥1 review」对单人是死局

**问题**：方案 §5.4 原写「PR 必须至少 1 个 review，CODEOWNERS 领域 owner 必审」——照搬了团队级最佳实践。

**后果**：classic 分支保护下，**作者不能批准自己的 PR**。单人项目没有第二个审查者，于是每个 PR 永远合不了，整个门禁体系卡死在最后一步。

**教训**：很多「最佳实践」（code owner review、≥1 approval）是按**团队场景**设计的，照搬到单人项目就是自杀。方案不能无脑抄团队模板。

**如何避免**：
- 单人项目用 **Rulesets**（不是 classic branch protection）：`required approving reviews = 0` + `enforce for administrators`（管理员也强制走 PR+CI，但不被 review 卡死）。
- 设分支保护前先问：这个规则在我的团队规模下，我能不能自己满足？不能就是死规则。
- 详见 [harness-setup.md §1](../../runbooks/harness-setup.md)。

### 2. release-please 配置缺 `path`，main 每次红 X

**问题**：方案 §7.3 写了「`release-type: python`，以 `backend/pyproject.toml` 为发版源」——**描述了意图，但没给 `path: backend` 这个参数**。

**后果**：release-please 默认在仓库根找 `pyproject.toml`，根没有（在 `backend/`）→ 找不到版本源 → 每次 push main 红 X，且报错不在配置层、看不出原因。

**教训**：「描述意图」≠「给出可运行配置」。方案评审要盯到**具体参数级**，不能停在「以 X 为源」这种半成品描述。

**如何避免**：
- 子目录 monorepo 发版，release-please 必须显式 `path: <子目录>`。
- 新增 CI/发版配置后，**一定要观察它在 main 上实际跑一次**（配置对 ≠ 跑得通）。
- changelog 位置也随之明确：`path: backend` → changelog 落 `backend/CHANGELOG.md`（非根）。

### 3. advisory 检查混进了阻断门（门禁纯度）

**问题**：原方案把 `pip-audit` / `npm audit`（依赖漏洞，advisory 性质）放进 `make check` 阻断门里。

**后果**：advisory 检查掺在 gate 中，一旦报警就阻断提交；dev 会习惯性 `--no-verify` 或无视，**最后连真正的阻断项也被一起无视**。

**教训**：**门禁纯度**——advisory（只该告警的）和 gate（必须阻断的）必须物理分离。混在一起会让 dev 对全部警告脱敏。

**如何避免**：
- gate（`make check` / CI required）只放**全阻断**项；advisory 拆独立 target / 独立非阻断 job（`make security-check`，CI 里 `continue-on-error`）。
- 新增任何检查先归类：它是「必须阻断」还是「最好知道」？后者绝不进 gate。

### 4. 派生物一致性只靠自觉，没进 CI（最重要修订）

**问题**：v2 原方案引入了 OpenAPI 契约生成（`make gen-client`），但**没把一致性校验放进 CI**。

**后果**：契约驱动形同虚设——dev 改了后端路由、忘了 `make gen-client`，前端类型就漂移，运行期才报错。**「代码改了类型没同步」老问题原样存在**。

**教训**：任何「派生物一致性」工作流，如果只靠人自觉执行生成步骤，就等于没有。**必须 CI 重新生成 + `git diff --exit-code` 强制**。

**如何避免**：
- CI 加 `derivative-check` job：重新生成 api-schema + TS 类型，再 `git diff --exit-code`，不一致即红。
- 该原则适用于所有 generated artifact：OpenAPI、生成类型、迁移、lockfile。
- 见 HARNESS §14.3（方案自己标为「最重要修订」）。

### 5. `make setup-dev` 忘了装宿主机工具

**问题**：方案 `make setup-dev` 只 `docker exec` 把工具装进**容器**，但 pre-commit 钩子是 `language: system`，在**宿主机**执行 ruff/black/isort。

**后果**：钩子「成功安装」却 `command not found`，秒级提交门禁**静默失效**——dev 以为有门禁，实际没有。

**教训**：工具在哪一层执行，就得在哪一层安装。`language: system` 的钩子绑宿主机 PATH，容器装得再全也没用。

**如何避免**：
- `setup-dev` 同时装宿主机工具（`pip install --user -r requirements-dev.txt`，版本对齐），并自检前置（Python/pipx 在不在）。
- 钩子激活后，手动 `pre-commit run` 一次确认真在跑、不是静默失败。

### 6. `alembic check` 排在 Alembic 初始化之前

**问题**：方案把 `alembic check` 放进 `make check`，但当时 Alembic **还没初始化**（无 env.py、无迁移）。

**后果**：`alembic check` 必失败 → `make check` 永红，整个门禁不可用。

**教训**：有依赖关系的步骤，**顺序就是正确性**。前置没就绪就上后置检查，等于自废门禁。

**如何避免**：
- 先做初始化（env.py + 初始迁移 + URL 可配置化），**再**把 `alembic check` 加入门禁。
- 每加一个检查项，问：它的前置都就绪了吗？没就绪就先挂起，别让它拖红整个 gate。

---

## 二、实施坑（方案对，实现时踩的）

### 7. detect-secrets 基线对 Python 版本 + OS 敏感

**问题**：`.secrets.baseline` 在宿主机（Python 3.10 / Windows）生成，CI 是 Python 3.11 / Linux。3.10 检出的密钥比 3.11 少，且 Windows 写反斜杠路径 + CRLF。

**后果**：基线和 CI 不一致 → CI 报「基线比实际检出少」误红；或基线路径污染（含 `.claude/worktrees/` 反斜杠路径）。

**教训**：detect-secrets 基线**必须在与 CI 同款环境（同 Python 版本、同 OS）生成**，否则跨环境必漂。

**如何避免**：
- 在 CI 同款容器（Python 3.11+ / Linux）重新生成基线并提交。
- Windows 宿主机 `pre-commit run --all-files` 会改写基线路径——宿主机的改动要 revert，只留 Linux 版。
- commit 钩子只扫暂存文件，非密钥文件不污染基线，日常 commit 不受影响。

### 8. PAT 反复失效：暴露 + 权限不全 + /user 红鲱鱼

**问题**：自动化驱动 PR 时，PAT 接连出问题——(a) 直接贴聊天暴露被迫撤销；(b) 第一个只读，开/合 PR 报 403；(c) fine-grained PAT 调 `/user` 返回 401，误判「token 死了」。

**后果**：认证来回占掉本次搭建**最大块的时间**，远超工程本身。

**教训**：
- token 永不贴聊天——**一次配齐权限**（Contents + Pull requests + Actions + Administration，都 write），别一次一次加 scope。
- fine-grained PAT 只有 repo 权限时调不了 `/user`（需 account 权限），但**能正常操作 repo**——别用 `/user` 判活，用 repo 端点测。

**如何避免**：
- token 存 `.gh-token`（gitignored），`GH_TOKEN=$(cat .gh-token)` 用，永不 echo。
- 判 token 有效：`curl -H "Authorization: Bearer $TOKEN" /repos/<owner>/<repo>` 返回 200 即有效，别用 `/user`。
- `gh` CLI 没装就走 REST API（Python urllib，避开 curl 的中文/引号解析问题）。

### 9. 派生物 regen 与已提交文件不逐字节一致（prettier）

**问题**：`derivative-check` 重新生成 `types.d.ts`，但已提交版本是 prettier 格式化过的；regen 跑 openapi-typescript 后不跑 prettier → 输出不匹配 → CI 误报漂移。

**后果**：派生物校验第一次跑就误红，且看起来像「文件坏了」其实是格式不一致。

**教训**：派生物一致性校验要求 regen 与提交时**同一套工具链**（含格式化）。少跑一步格式化就误报。

**如何避免**：
- 生成脚本（`generate-api-client.sh`）末尾加 `prettier --write`，使 regen 产出与已提交的 prettier'd 文件**逐字节一致**。
- prettier 是幂等的（`prettier(prettier(x)) == prettier(x)`），只要版本锁死（package-lock），regen 必匹配。

### 10. `npm install --package-lock-only` 生成残缺 lockfile

**问题**：为修 CI 的 `npm ci`，用 `--package-lock-only` 生成 lockfile。

**后果**：生成的 lockfile**缺平台可选依赖**（optionalDependencies 的平台二进制），`npm ci` 在 CI 上装不全，测试跑不起来。

**教训**：`--package-lock-only` 不解析实际安装树，会漏 optional deps。**lockfile 必须用真实安装生成**。

**如何避免**：用完整 `npm install` 生成 lockfile（会解析并写入全部平台可选依赖），再提交。

### 11. vitest 2.1.9 hang

**问题**：vitest 2.1.9 在 CI 上挂起不退出。

**后果**：前端测试 job 超时失败。

**教训**：工具某个小版本可能有平台/CI 兼容 bug，不能盲目追新。

**如何避免**：锁到已知稳定版（2.0.3）；在 Dependabot 里**忽略 semver-major**，minor/patch 自动提但 review，大版本人工评估。

### 12. 覆盖率门槛 80 vs 方案要求的 85

**问题**：方案 §5.2/§9.2 写 `--cov-fail-under=85`，但 `pyproject.toml` 实际是 80——**实现没跟上方案**。

**后果**：门槛比设计松，覆盖率防回退力度不足。

**教训**：方案定的值要在实现里核对，别让代码静默漂离设计。

**如何避免**：升门槛前先**借 CI 验证实际覆盖率**（改 85 → 跑 backend-unit-test → 绿才合并），避免盲目改红 CI。实测覆盖率 ≥85% 后才把 pyproject 对齐到 85。

---

## 三、元教训

1. **「配置到位」≠「生效」**：大量东西（Ruleset、release-please 两开关、Dependabot alerts）配置文件对了还不够，必须在 GitHub 平台层再开一次。**文件是建议，平台设置才是门禁。**
2. **方案级错误比实现 bug 更致命**：实现 bug 改一处就好；方案错了（如分支保护死局）会让整套体系在最后一步卡死，且不易察觉是设计的锅。评审要专门盯「这个设计在我的场景下跑得通吗」。
3. **「最佳实践」要按团队规模 right-size**：团队级实践（code owner review、SBOM、多 approval）照搬到单人/内部项目就是过度或自杀。
4. **认证是最大时间黑洞**：token 权限一次配齐、存文件别贴聊天——光这条就省掉大半来回。
5. **派生物一致性必须逐字节对齐工具链 + CI 强制**：少一步格式化就误报，不进 CI 就形同虚设。
6. **HARNESS 文档是活文档**：v1→v2.7 每个版本都是一个被纠正的错误。方案不会一次写对，**复盘→回改方案→再实施**是正常迭代，别追求一稿过。
