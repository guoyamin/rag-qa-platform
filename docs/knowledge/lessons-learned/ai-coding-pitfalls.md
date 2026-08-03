# AI 编码陷阱

AI 辅助编码时引入的 bug，记录教训与规避方式。

## 1. Edit 大块替换破坏文件

**问题**：用 Edit 工具替换 `test_auth.py` 的 fixture 代码块时，`old_string` 匹配错位，导致 `User(` 和 `id="test-uuid"` 合并到一行，且残留重复行，引发 `IndentationError`。

**后果**：测试无法 collect，`IndentationError: unexpected indent`。

**教训**：Edit 的 `old_string` 必须精确匹配；大段替换时边界容易错位。

**如何避免**：
- 大段修改（整个函数/类）优先用 Write 重写整文件
- Edit 后立即跑编译/测试验证（`python -m pytest --collect-only`）
- `old_string` 带足够上下文确保唯一匹配

## 2. `declare module` 覆盖第三方类型

**问题**：为修复 `meta.hidden` 类型错误，在 `vite-env.d.ts` 加了 `declare module 'vue-router' { interface RouteMeta {...} }`，结果覆盖了 vue-router 的真实类型，导致 `createRouter`、`useRoute`、`useRouter` 全部「找不到导出」。

**后果**：vue-tsc 报 10+ 个 `Module '"vue-router"' has no exported member` 错误。

**教训**：`declare module 'xxx'` 是模块增强（declaration merging），但如果原始类型未正确加载，会变成「覆盖」（只剩你声明的内容）。

**如何避免**：
- 扩展第三方类型优先用官方推荐方式（vue-router 的 `RouteMeta` 通过接口合并在 `vue-router` 模块内声明）
- 加 `declare module` 后跑 `vue-tsc --noEmit` 验证，确认是增强不是覆盖
- 不确定时，用类型断言（`as`）或 `RouteRecordRaw[]` 标注替代

```ts
// ❌ 错误：可能覆盖 vue-router 类型
declare module 'vue-router' {
  interface RouteMeta { hidden?: boolean }
}

// ✅ 正确：用 RouteRecordRaw[] 标注路由，meta 自动放宽
const routes: RouteRecordRaw[] = [...]
```

## 3. 误删「再导出」的 import

**问题**：ruff 报 `get_db` imported but unused（F401），我直接删除了 `deps.py` 的 `from app.db.session import get_db`。但 `get_db` 是供 API 路由通过 `from app.api.deps import get_db` 再导出使用的，删除后 `chat.py` 等导入失败。

**后果**：`ImportError: cannot import name 'get_db' from 'app.api.deps'`，后端启动失败。

**教训**：「未用 import」可能用于再导出（re-export），供其他模块导入。

**如何避免**：
- 删 import 前用 `grep -rn "from app.api.deps import" backend/app/` 确认是否被其他文件导入
- 若是再导出，用 `__all__` 显式声明，ruff 不再报 F401

```python
# deps.py：get_db 定义在 app.db.session，供 API 路由通过 deps 统一导入
from app.db.session import AsyncSessionLocal, get_db

__all__ = ["get_current_user", "get_db", "get_ws_user", ...]
```

## 4. 401 拦截器对 login 请求触发 refresh 循环

**问题**：为支持 token 续期，在 `request.ts` 响应拦截器对所有 401 尝试 refresh。但 login 请求密码错误返回 401 时，拦截器拿旧 refreshToken 去 refresh（成功），再重试 login（还是 401），形成 `login 401 → refresh 200 → login 401` 死循环。

**后果**：错误密码登录时，浏览器无限循环请求，后端日志刷屏。

**教训**：refresh 逻辑只用于「token 过期的业务请求」，不能覆盖 auth 请求本身。

**如何避免**：
- 401 refresh 逻辑排除 `/auth/login`、`/auth/refresh` URL
- auth 请求的 401 直接抛出，由调用方处理（显示后端 message）

```ts
// ❌ 错误：所有 401 都 refresh
if (response?.status === 401 && config) {
  // 尝试 refresh...（login 401 也会触发，循环）
}

// ✅ 正确：排除 auth 请求
const isAuthRequest =
  config?.url?.includes('/auth/login') ||
  config?.url?.includes('/auth/refresh')
if (isAuthRequest) {
  return Promise.reject(error)  // 直接抛出，不 refresh
}
if (response?.status === 401 && config && !retriedConfigs.has(config)) {
  // 仅业务请求的 401 才 refresh
}
```

## 5. 代码写完未自检（本次迭代最大教训）

**问题**：一次提交了 71 个文件的新增/修改（11 个 service、9 个 model、8 个 API、前端模型管理页），实现完成后**没有按规范 6.2 跑自检**（mypy/ruff/pytest/bandit），直接进入 Review。

**后果**：自检阶段一次性暴露大量低级问题：
- **216 个 mypy --strict 错误**（类型注解大面积缺失，分布在 39 个文件）
- **49 个 ruff F821 undefined-name**（漏 import）
- **测试覆盖率 37%**（11 个 service 0% 覆盖，测试只测 schema/enum 不测 service 逻辑）
- **测试自身语法错误**：`test_usage_stats.py` 括号不匹配，导致整个后端测试 collection 失败，0 用例执行
- **运行时 bug 漏到验收**：登录 500、创建模型 503、熔断功能 ImportError 完全不可用

**教训**：「写完代码」≠「代码可用」。规范 6.2 的自检清单（mypy --strict / ruff / pytest --cov / bandit）是真实验收门禁，不跑就是裸奔。本次几乎所有问题都能在自检阶段 5 分钟内暴露，却拖到 Review / 运行时才被发现，返工成本远高于自检。

**如何避免**：
- 实现代码后**立即**跑自检，不要积累到 Review 前：
  ```bash
  make lint      # black + isort + ruff + mypy
  make test      # pytest --cov
  make security  # bandit + detect-secrets
  ```
- **mypy --strict** 能抓「漏 import / 未定义名称 / 类型缺失」-- 49 个 F821 和大部分 mypy 错误会立即暴露
- **pytest --cov** 能抓「测试只测 schema 不测 service」-- 覆盖率 37% 一目了然
- 测试自身要先能 collect（`pytest --collect-only`），语法错误会让全部测试静默跳过（本次 test_usage_stats 语法错导致 116 个用例一个没跑）
- 把自检纳入「完成的定义」：没跑自检的代码不算写完，不能进入 Review

**本次具体案例**（都因没自检漏到运行时）：

| 文件 | 问题 | 后果 |
|------|------|------|
| `auth_service.py` | 漏 `from datetime import datetime` | 登录接口 500 |
| `llm_manager.py` | 漏 `import asyncio` + `asyncio.Lock` 用在同步方法 | TypeError |
| `db/base.py` | 重复定义 `class Base`（空 + 带字段） | 所有 model 的 id 继承失效（25 个类型错误） |
| `circuit_breaker_service.py` | `from app.models.circuit_breaker_state import ...`（模块不存在） | ImportError，熔断功能完全不可用 |
| `model_service.create` | 新建 INACTIVE 模型却调 `get_llm`（只认 ACTIVE） | 创建模型 503 |
| `requirements.txt` | 缺 apscheduler/hvac/aiosqlite/freezegun | 后端启动 ModuleNotFoundError |

这些里**前 4 个 mypy/ruff 一跑就报**，第 5 个跑 pytest 就报，第 6 个启动就报 -- 全部能在自检阶段拦截。
