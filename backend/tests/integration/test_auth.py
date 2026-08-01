"""
认证 API 集成测试。

覆盖 /api/v1/auth 下的 login / refresh / me / logout，使用真实测试库验证 SQL，
mock 外部依赖（LLM/Milvus/Vault 由 conftest autouse fixture 注入）。
遵循 AAA 模式，每测试独立（独立内存库），函数体 <=50 行。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import get_password_hash
from app.models.user import User, UserAuthType, UserRole, UserStatus

VALID_PASSWORD = "Passw0rd!"


async def _create_user(
    db_session: AsyncSession,
    username: str = "testuser",
    password: str = VALID_PASSWORD,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """在测试库创建本地认证用户（commit 后释放连接，避免与请求争用单连接）。"""
    user = User(
        username=username,
        display_name=username,
        hashed_password=get_password_hash(password),
        auth_type=UserAuthType.LOCAL,
        role=UserRole.STAFF,
        status=status,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.integration
class TestAuthAPI:
    """认证接口集成测试。"""

    async def test_login_success_returns_tokens(self, client, db_session):
        # Arrange
        await _create_user(db_session, username="loginok", password=VALID_PASSWORD)
        # Act
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "loginok",
                "password": VALID_PASSWORD,
                "auth_type": "local",
            },
        )
        # Assert
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_login_wrong_password_returns_401(self, client, db_session):
        # Arrange
        await _create_user(db_session, username="badpw", password=VALID_PASSWORD)
        # Act
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "badpw",
                "password": "WrongPass1!",
                "auth_type": "local",
            },
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_login_unknown_user_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "no_such_user",
                "password": VALID_PASSWORD,
                "auth_type": "local",
            },
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_login_success_updates_login_count(
        self, client, db_session, session_factory: async_sessionmaker[AsyncSession]
    ):
        # Arrange
        await _create_user(db_session, username="counter", password=VALID_PASSWORD)
        # Act
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "counter",
                "password": VALID_PASSWORD,
                "auth_type": "local",
            },
        )
        # Assert：登录成功且真实写入测试库（login_count +1）
        assert resp.status_code == 200
        async with session_factory() as fresh:
            result = await fresh.execute(select(User).where(User.username == "counter"))
            assert result.scalar_one().login_count == 1

    async def test_me_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/auth/me")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_me_with_valid_token_returns_profile(self, client, db_session):
        # Arrange
        await _create_user(db_session, username="meuser", password=VALID_PASSWORD)
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "meuser",
                "password": VALID_PASSWORD,
                "auth_type": "local",
            },
        )
        token = login.json()["data"]["access_token"]
        # Act
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 200
        profile = resp.json()["data"]
        assert profile["username"] == "meuser"
        assert profile["role"] == "staff"

    async def test_me_with_invalid_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_refresh_with_valid_token_returns_new_tokens(
        self, client, db_session
    ):
        # Arrange
        await _create_user(db_session, username="refreshu", password=VALID_PASSWORD)
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "refreshu",
                "password": VALID_PASSWORD,
                "auth_type": "local",
            },
        )
        refresh_token = login.json()["data"]["refresh_token"]
        # Act
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        # Assert
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"

    async def test_refresh_with_invalid_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-refresh-token"},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_refresh_with_access_token_returns_401(self, client, db_session):
        # Arrange：用 access_token 冒充 refresh_token，类型校验应失败
        await _create_user(db_session, username="wrongtype", password=VALID_PASSWORD)
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "wrongtype",
                "password": VALID_PASSWORD,
                "auth_type": "local",
            },
        )
        access_token = login.json()["data"]["access_token"]
        # Act
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_logout_returns_success(self, client):
        # Arrange / Act
        resp = await client.post("/api/v1/auth/logout")
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["message"] == "登出成功"
