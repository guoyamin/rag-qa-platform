# 智能问答平台

# 测试策略规范

**文档编号：** RAG-QA-STD-002  
**版本号：** V1.0  
**编制部门：** 信息技术部  
**发布日期：** 2026年07月30日  
**密级：** 内部公开  

---

**修订记录**

| 版本号 | 修订日期 | 修订内容 | 作者 | 审核人 |
|--------|----------|----------|------|--------|
| V1.0 | 2026-07-30 | 初始版本 | AI辅助 | 待确认 |

---

**分发范围：** 项目开发团队  
**保管部门：** 信息技术部  

---

## 目录

1. [测试金字塔](#1-测试金字塔)
2. [测试分层定义](#2-测试分层定义)
3. [测试编写责任](#3-测试编写责任)
4. [测试数据管理](#4-测试数据管理)
5. [测试用例编写规范](#5-测试用例编写规范)
6. [测试环境配置](#6-测试环境配置)
7. [测试执行策略](#7-测试执行策略)
8. [附录](#8-附录)

---

## 1. 测试金字塔

本平台遵循测试金字塔原则，各层比例要求如下：

```
      /\
     /  \   E2E测试   10%  ← 关键用户路径
    /____\  
   /      \ 集成测试  30%  ← 模块间交互
  /________\ 
 /          \ 单元测试 60%  ← 业务逻辑核心
/____________\
```

量化指标：每新增100行业务代码，对应测试代码量约为：
- 单元测试：60行
- 集成测试：30行
- E2E测试：10行

### 1.1 覆盖率基线

| 测试类型 | 后端 | 前端 | 度量方式 |
|----------|------|------|----------|
| 单元测试 | ≥80% | ≥70% | 行覆盖率 |
| 集成测试 | ≥60% | ≥50% | 关键路径覆盖 |
| E2E测试 | N/A | N/A | 场景覆盖数 |

**增量代码要求：** 新提交的代码其单元测试覆盖率不得低于基线，否则阻塞合并。

---

## 2. 测试分层定义

### 2.1 单元测试

**目标：** 验证单个函数/方法在隔离环境中的正确性。

**工具：**
- 后端：pytest + pytest-asyncio
- 前端：vitest + @vue/test-utils

**速度要求：** 单测执行时间不超过1秒。

**依赖隔离：** 所有外部依赖必须Mock，包括：
- 数据库操作
- 外部HTTP调用
- LLM API调用
- 文件系统操作
- 时间/随机数等不确定性来源

**命名规范：** `test_{被测函数}_{场景}_{预期结果}`

```python
# ✅ 正确
def test_authenticate_with_valid_credentials_returns_token():
    ...

def test_authenticate_with_invalid_password_raises_error():
    ...

# ❌ 错误
def test_auth():
    ...
```

**存放位置：**
- 后端：`backend/tests/unit/`（按模块分子目录）
- 前端：`frontend/tests/unit/`（与被测文件同名）

### 2.2 集成测试

**目标：** 验证模块间交互的正确性。

**工具：**
- 后端：pytest-asyncio
- 前端：vitest

**范围：**
- 数据库操作（使用真实测试数据库）
- API接口（通过TestClient调用）
- 服务间调用
- 缓存（Redis）读写

**环境要求：**
- 使用独立的测试数据库（PostgreSQL实例或SQLite内存）
- 测试之间不共享状态，使用事务回滚隔离
- 每个测试用例独立，不依赖执行顺序

**存放位置：**
- 后端：`backend/tests/integration/`
- 前端：`frontend/tests/integration/`

### 2.3 端到端测试

**目标：** 验证完整用户场景。

**工具：** Playwright

**范围：** 关键业务流程
- 用户登录与登出
- 智能问答全流程（提问 → 等待回答 → 查看来源）
- 文档上传与知识库管理
- 管理员用户管理

**环境要求：**
- 接近生产的完整环境（前后端 + 数据库）
- 使用专用测试数据（Factory Boy/faker生成）

**速度要求：**
- 允许较慢，但全套E2E测试须控制在10分钟以内
- 单个测试不超过2分钟

**存放位置：** `frontend/tests/e2e/`

---

## 3. 测试编写责任

| 测试类型 | 编写主体 | 编写时机 | 验收主体 |
|----------|----------|----------|----------|
| 单元测试 | AI | 功能实现时同步编写 | AI自检 |
| 集成测试 | AI | 模块联调时编写 | AI自检 |
| E2E测试 | AI编写框架，用户补充场景 | 功能验收阶段 | 用户 |
| 性能测试 | 视情况安排 | 上线前 | 用户 |

### 3.1 编写时序

```
需求确认
  │
  ├─→ AI实现业务代码（同步编写单元测试）
  │
  ├─→ AI自检（单元测试通过）
  │
  ├─→ AI编写集成测试（验证模块交互）
  │
  ├─→ AI自检（集成测试通过）
  │
  ├─→ 用户Review（关注业务逻辑）
  │
  ├─→ AI修复
  │
  ├─→ 用户确认场景，AI编写E2E测试框架
  │
  └─→ 用户补充E2E场景，验收通过
```

---

## 4. 测试数据管理

### 4.1 基本原则

- **严禁使用生产环境数据作为测试数据**
- 所有测试数据通过程序生成，不得手动维护测试数据文件
- 测试数据须与测试代码放在同一版本控制下

### 4.2 数据生成方式

| 类型 | 工具 | 使用场景 |
|------|------|----------|
| 假数据生成 | faker | 用户名、邮箱、手机号、地址等 |
| 模型工厂 | factory-boy | 数据库模型实例快速创建 |
| 固定测试数据 | Python常量/Vue常量 | 边界值、特殊字符、超长字符串 |

### 4.3 数据隔离

- 数据库测试使用事务回滚，确保测试不残留数据
- 每个测试用例独立，不依赖执行顺序
- 测试数据库与开发/生产数据库物理隔离

### 4.4 确定性要求

- 相同输入必须产生相同输出
- 禁止使用非确定性数据（如当前时间、随机数）作为断言依据
- 如需测试时间相关逻辑，使用时钟模拟（freezegun / vitest fake timers）

---

## 5. 测试用例编写规范

### 5.1 单一职责

每个测试只验证一个行为。

```python
# ✅ 正确
async def test_login_with_valid_credentials_returns_token():
    ...

async def test_login_with_invalid_password_raises_error():
    ...

async def test_login_with_locked_account_returns_403():
    ...

# ❌ 错误（一个测试验证多个行为）
async def test_login():
    # 验证成功...
    # 验证失败...
    # 验证锁定...
```

### 5.2 AAA模式

每个测试按 Arrange → Act → Assert 三段式组织：

```python
async def test_user_can_login():
    # Arrange: 准备数据和依赖
    user = UserFactory(username="test", hashed_password=hash("123456"))
    
    # Act: 执行被测操作
    result = await auth_service.authenticate("test", "123456")
    
    # Assert: 验证结果
    assert result.access_token is not None
    assert result.expires_in == 28800
```

### 5.3 边界覆盖

每个功能必须覆盖以下路径：

| 路径类型 | 说明 | 示例 |
|----------|------|------|
| 正常路径 | 标准输入，预期输出 | 正确的用户名密码 |
| 边界值 | 最小值、最大值、空值 | 密码刚好8位、刚好5000字符 |
| 异常路径 | 错误输入、异常状态 | 用户不存在、账号已锁定 |
| 并发路径 | 多用户同时操作 | 同时刷新Token |

### 5.4 Mock规范

**必须Mock的外部依赖：**

```python
# ✅ 正确：Mock LLM调用
@pytest.fixture
def mock_llm():
    with patch("app.rag.pipeline.LLMFactory.create") as mock:
        mock.return_value.chat = AsyncMock(
            return_value=LLMResponse(content="测试回答", total_tokens=10)
        )
        yield mock

# ❌ 错误：测试中真实调用LLM
async def test_chat():
    result = await rag_pipeline.query("问题")  # 可能超时/产生费用
```

**Mock原则：**
- 只Mock外部依赖（数据库、网络、文件系统），不Mock被测代码内部逻辑
- Mock的返回值须符合真实接口的Schema
- Mock后须验证被测代码正确调用了依赖（assert_called_with）

---

## 6. 测试环境配置

### 6.1 后端测试配置

**pytest.ini：**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts =
    --strict-markers
    --cov=app
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=80
markers =
    unit: 单元测试
    integration: 集成测试
    e2e: 端到端测试
    slow: 执行时间超过1秒的测试
```

**pyproject.toml 测试相关配置：**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--cov=app --cov-report=term-missing --cov-report=html"

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
]
```

### 6.2 前端测试配置

**vitest.config.ts：**

```typescript
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      thresholds: {
        lines: 70,
        functions: 70,
        branches: 60,
        statements: 70,
      },
    },
  },
})
```

### 6.3 Playwright配置

```typescript
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
})
```

---

## 7. 测试执行策略

### 7.1 本地开发阶段

```bash
# 仅运行当前修改相关的单元测试（快速反馈）
pytest -k test_auth

# 运行全部单元测试
pytest -m unit

# 运行全部测试（提交前）
pytest
```

### 7.2 CI流水线阶段

| 阶段 | 执行内容 | 失败处理 |
|------|----------|----------|
| Lint | ruff + mypy + black --check | 阻塞 |
| Unit Test | pytest -m unit --cov | 阻塞 |
| Integration Test | pytest -m integration | 阻塞 |
| E2E Test | playwright test | 阻塞 |
| Coverage | 合并覆盖率报告，检查阈值 | 阻塞 |

### 7.3 测试报告

- HTML覆盖率报告留存至CI产物
- 测试失败时保留截图（Playwright）和日志
- 每周生成测试质量报告（通过率、覆盖率趋势、慢测试列表）

---

## 8. 附录

### 附录A：常用测试工具速查

| 工具 | 用途 | 安装 |
|------|------|------|
| pytest | Python测试框架 | `pip install pytest pytest-asyncio` |
| pytest-cov | 覆盖率 | `pip install pytest-cov` |
| factory-boy | 模型工厂 | `pip install factory-boy` |
| faker | 假数据 | `pip install faker` |
| freezegun | 时间模拟 | `pip install freezegun` |
| respx | HTTP Mock | `pip install respx` |
| vitest | 前端测试 | `npm install -D vitest` |
| @vue/test-utils | Vue组件测试 | `npm install -D @vue/test-utils` |
| jsdom | DOM环境 | `npm install -D jsdom` |
| Playwright | E2E测试 | `npm install -D @playwright/test` |

### 附录B：测试 fixture 示例

```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    """创建数据库会话"""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(db_session):
    """创建测试客户端"""
    from fastapi.testclient import TestClient
    # 覆盖依赖注入
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
```

---

**文档结束**

---

*本文档为《编码规范》配套专项规范，与之共同构成项目规范体系。*
