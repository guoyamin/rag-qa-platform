"""
用户管理 API 集成测试。

覆盖 /api/v1/users 下各端点：list / create / get / update / delete / status，
使用真实测试库验证 SQL（create 端点验证落库），mock 外部依赖
（LLM/Milvus/Vault 由 conftest autouse fixture 注入）。所有端点均要求 admin
（require_admin）。遵循 AAA 模式，每测试独立内存库，函数体 <=50 行。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import get_password_hash
from app.models.user import User, UserAuthType, UserRole, UserStatus

VALID_PASSWORD = "Passw0rd!"


async def _create_user_in_db(
    db_session: AsyncSession,
    *,
    username: str,
    role: UserRole = UserRole.STAFF,
    password: str = VALID_PASSWORD,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """在测试库创建本地认证用户（commit 后释放连接，避免与请求争用单连接）。"""
    user = User(
        username=username,
        display_name=username,
        hashed_password=get_password_hash(password),
        auth_type=UserAuthType.LOCAL,
        role=role,
        status=status,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login_headers(
    client,
    username: str,
    password: str = VALID_PASSWORD,
) -> dict[str, str]:
    """登录指定用户，返回 Bearer 认证头。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "auth_type": "local"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _admin_headers(client, db_session: AsyncSession) -> dict[str, str]:
    """创建管理员并登录，返回 admin 认证头。"""
    await _create_user_in_db(db_session, username="adminuser", role=UserRole.ADMIN)
    return await _login_headers(client, "adminuser")


async def _staff_headers(client, db_session: AsyncSession) -> dict[str, str]:
    """创建普通职工并登录，返回 staff 认证头（非管理员，用于权限校验）。"""
    await _create_user_in_db(db_session, username="staffuser", role=UserRole.STAFF)
    return await _login_headers(client, "staffuser")


@pytest.mark.integration
class TestUserAPI:
    """用户管理接口集成测试。"""

    # ---------- GET /users（列表） ----------

    async def test_list_users_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/users")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_list_users_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/users", headers=headers)
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_list_users_admin_returns_empty(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/users", headers=headers)
        # Assert：当前为 TODO 桩实现，返回空列表
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["data"] == []
        assert body["total"] == 0

    async def test_list_users_invalid_page_returns_422(self, client, db_session):
        # Arrange：page 必须 >=1
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/users?page=0", headers=headers)
        # Assert
        assert resp.status_code == 422

    # ---------- POST /users（创建） ----------

    async def test_create_user_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/users",
            json={"username": "someone", "password": VALID_PASSWORD},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_create_user_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/users",
            json={"username": "newu", "password": VALID_PASSWORD},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_create_user_admin_success_persists_to_db(
        self,
        client,
        db_session,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        # Arrange
        headers = await _admin_headers(client, db_session)
        payload = {
            "username": "newuser1",
            "password": VALID_PASSWORD,
            "role": "operator",
        }
        # Act
        resp = await client.post("/api/v1/users", json=payload, headers=headers)
        # Assert：响应含完整用户且真实写入测试库
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["username"] == "newuser1"
        assert data["role"] == "operator"
        assert data["auth_type"] == "local"
        assert data["status"] == "active"
        assert "hashed_password" not in data
        async with session_factory() as fresh:
            result = await fresh.execute(
                select(User).where(User.username == "newuser1")
            )
            persisted = result.scalar_one()
            assert persisted.role == UserRole.OPERATOR
            assert persisted.hashed_password

    async def test_create_user_duplicate_username_returns_400(self, client, db_session):
        # Arrange：先直接写入同名用户
        await _create_user_in_db(db_session, username="dupuser", role=UserRole.STAFF)
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/users",
            json={"username": "dupuser", "password": VALID_PASSWORD},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    async def test_create_user_short_password_returns_422(self, client, db_session):
        # Arrange：密码 <8 位
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/users",
            json={"username": "shortpw", "password": "Ab1!"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    # ---------- GET /users/{id}（详情） ----------

    async def test_get_user_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/users/some-id")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_get_user_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/users/some-id", headers=headers)
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_get_user_admin_returns_null(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/users/some-id", headers=headers)
        # Assert：当前为 TODO 桩实现，统一返回 data=null
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    # ---------- PUT /users/{id}（更新） ----------

    async def test_update_user_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.put("/api/v1/users/some-id", json={})
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_update_user_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.put("/api/v1/users/some-id", json={}, headers=headers)
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_update_user_admin_returns_null(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/users/some-id",
            json={"display_name": "新名称"},
            headers=headers,
        )
        # Assert：当前为 TODO 桩实现，统一返回 data=null
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    # ---------- DELETE /users/{id}（删除） ----------

    async def test_delete_user_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.delete("/api/v1/users/some-id")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_delete_user_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.delete("/api/v1/users/some-id", headers=headers)
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_delete_user_admin_returns_success(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.delete("/api/v1/users/some-id", headers=headers)
        # Assert：当前为 TODO 桩实现，返回成功
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["message"] == "删除成功"

    # ---------- PUT /users/{id}/status（状态） ----------

    async def test_update_status_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.put("/api/v1/users/some-id/status?status=active")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_update_status_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/users/some-id/status?status=active", headers=headers
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_update_status_admin_returns_success(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/users/some-id/status?status=disabled", headers=headers
        )
        # Assert：当前为 TODO 桩实现，返回成功
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["message"] == "状态更新成功"

    async def test_update_status_missing_query_returns_422(self, client, db_session):
        # Arrange：status 为必填查询参数，缺失应 422
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.put("/api/v1/users/some-id/status", headers=headers)
        # Assert
        assert resp.status_code == 422
