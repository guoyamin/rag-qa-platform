"""
集成测试公共基础设施。

设计说明（遵循 TEST_STRATEGY 2.2：真实 DB 验证 SQL、mock 外部依赖、隔离、AAA）：

1. 数据库选择：SQLite 内存库（aiosqlite + StaticPool 共享单连接）。
   - 已验证 Base.metadata.create_all 在 SQLite 下可建全部表：model 的 SQLAlchemy Enum
     在 SQLite 无原生 ENUM，自动回退为 VARCHAR，兼容无问题，无需回退到 postgres 测试库。
   - TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"。

2. 隔离策略：每个测试一个独立内存数据库（function 级 engine + create_all 建表），
   测试结束 dispose 即"不残留"，用例间互不依赖、与顺序无关。
   真正的事务回滚隔离在此架构下不可靠：AuthService 内部会 commit，且 get_current_user
   经独立的 AsyncSessionLocal 会话访问库（async SQLAlchemy 的外部事务+savepoint 模式
   无法跨这些独立 commit 回滚，已验证）。逐测试全新内存库提供更强且稳定的隔离保证。

3. HTTP 客户端：使用 httpx.AsyncClient + ASGITransport（而非 fastapi.TestClient）。
   原因：TestClient 在独立 portal 事件循环上运行 ASGI 应用，而 aiosqlite 连接绑定
   创建它的循环；TestClient + 内存 SQLite 会跨循环复用同一连接导致死锁（已实测验证）。
   AsyncClient 与测试运行在同一事件循环，app.dependency_overrides[get_db] 用法完全一致。

4. get_current_user 直接使用 AsyncSessionLocal（非 get_db 依赖），故同时将
   app.api.deps.AsyncSessionLocal 与 app.db.session.AsyncSessionLocal 指向测试会话工厂，
   确保 /auth/me 等接口也走测试库、不触碰真实 postgres。

5. 外部依赖 mock：LLM(LLMManager)/Milvus(pymilvus.MilvusClient)/Vault(vault_client)
   全量 mock（autouse），杜绝真实外部调用；不 mock service 内部逻辑。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.api.deps as deps
import app.db.session as db_session_module
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.llm_manager import LLMManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """每个测试一个独立内存数据库引擎，建全表后销毁——天然隔离、不残留。"""
    eng = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """绑定到测试引擎的异步会话工厂。"""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """供测试准备数据的异步会话；用例内 commit 后即释放连接，避免与请求争用单连接。"""
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP 客户端：覆盖 get_db 依赖、重定向 AsyncSessionLocal 至测试库。"""
    orig_deps_local = deps.AsyncSessionLocal
    orig_session_local = db_session_module.AsyncSessionLocal

    deps.AsyncSessionLocal = session_factory
    db_session_module.AsyncSessionLocal = session_factory

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    deps.AsyncSessionLocal = orig_deps_local
    db_session_module.AsyncSessionLocal = orig_session_local


@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock 外部依赖：LLM / Milvus / Vault，避免真实调用（不 mock service 内部）。"""
    mock_llm = AsyncMock()
    monkeypatch.setattr(LLMManager, "get_instance", classmethod(lambda cls: mock_llm))
    monkeypatch.setattr("app.services.llm_manager.get_llm_manager", lambda: mock_llm)
    monkeypatch.setattr("pymilvus.MilvusClient", MagicMock)
    mock_vault = MagicMock()
    monkeypatch.setattr(
        "app.services.vault_client.get_vault_client", lambda: mock_vault
    )
    monkeypatch.setattr("app.services.vault_client._vault_client", mock_vault)
