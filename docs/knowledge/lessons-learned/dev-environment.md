# 开发环境问题

Docker / vite / worktree 等环境陷阱，开发过程中反复遇到。

## 1. vite HMR 不更新（反复出现）

**问题**：修改了 worktree 的前端代码，但浏览器/容器 serve 的仍是旧版（CSS 变量、topbar 等不生效）。`curl` vite serve 的文件也不含新代码。

**后果**：改了代码看不到效果，误以为代码有问题，反复排查。

**教训**：vite dev 的编译缓存/监听在挂载源变更后不会自动清；HMR 偶尔失效。

**如何避免**：
- 改了代码若页面没变化，先 `curl http://localhost:5173/src/xxx.vue` 确认 vite serve 的文件是否含新代码
- 若 serve 旧版，`docker-compose restart frontend` 让 vite 重新编译
- 验证修改时，优先用 Playwright 提取实际 DOM/CSS，而非只看页面（避免被缓存误导）

```bash
# 确认 vite serve 的文件是否最新
curl -s http://localhost:5173/src/api/request.ts | grep isAuthRequest
# 若返回 0，说明 vite 缓存旧版，需 restart
docker-compose -f deployment/docker-compose.dev.yml restart frontend
```

## 2. `docker cp` 目录复制不覆盖文件

**问题**：用 `docker cp tests rag_qa_platform-backend:/app/tests` 复制测试目录到容器，但容器内已有的旧文件没被更新（`test_auth.py` 还是旧版）。

**后果**：测试跑的还是旧版，修改不生效，误判测试失败原因。

**教训**：`docker cp` 目录到已存在目录是「合并」，不覆盖已存在文件。

**如何避免**：
- 用单文件 `docker cp src/file container:/app/file` 确保覆盖
- 或先 `docker exec rm -rf /app/tests` 再 cp 目录

```bash
# ❌ 目录 cp 不覆盖已存在文件
docker cp tests rag_qa_platform-backend:/app/tests

# ✅ 单文件 cp 覆盖
docker cp tests/unit/test_auth.py rag_qa_platform-backend:/app/tests/unit/test_auth.py
```

## 3. worktree 与主仓库不同步

**问题**：在 worktree（基于初始 commit `d73224c`）审计代码，发现一堆 P0 bug。但主仓库已经修复了这些 P0，worktree 是过时版本。

**后果**：基于过时代码审计，P0 结论全部失效，白做一轮工作。

**教训**：worktree 可能基于旧 commit，开发/审计前必须确认基线同步。

**如何避免**：
- 审计前对比 worktree 与主仓库的 HEAD（`git log` 对比）
- 必要时 `git reset --hard main` 对齐
- 容器挂载的代码路径也要确认（容器可能挂主仓库，而你在 worktree 改）

```bash
# 确认 worktree 与主仓库同步
git -C /d/Project/Demo log --oneline -1   # 主仓库 HEAD
git log --oneline -1                       # worktree HEAD
# 若不一致，worktree reset
git reset --hard main
```

## 4. alpine 容器跑不了 Playwright chromium

**问题**：前端 Dockerfile.dev 是 `node:20-alpine`（musl），Playwright 的 chromium 需要 glibc，下载极慢且运行不兼容（`ERR_CONNECTION_CLOSED` 或缺库）。

**后果**：E2E 测试无法在 alpine 容器跑，反复超时。

**教训**：Playwright 与 alpine 不兼容。

**如何避免**：
- E2E 用 `node:slim`（debian）+ `channel: 'chrome'`（宿主机系统 Chrome）
- 或用官方镜像 `mcr.microsoft.com/playwright`
- 不要在 alpine 容器装 chromium

```ts
// playwright.config.ts：用系统 Chrome，不下载 chromium
export default defineConfig({
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },  // 系统 Chrome
    },
  ],
})
```
