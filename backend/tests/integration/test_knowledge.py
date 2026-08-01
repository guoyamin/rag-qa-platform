"""
知识库管理 API 集成测试。

覆盖 /api/v1/knowledge/bases 下各端点：list / create / get / update / delete，
使用真实测试库验证 SQL，mock 外部依赖（LLM/Milvus/Vault 由 conftest autouse
fixture 注入）。list/get 端点要求 get_current_active_user（任意活跃用户），
create/update/delete 端点要求 require_admin。当前路由为 TODO 桩实现，
成功用例断言桩响应；失败/权限/边界用例验证认证、授权与参数校验。
遵循 AAA 模式，每测试独立内存库，函数体 <=50 行。
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
class TestKnowledgeAPI:
    """知识库管理接口集成测试。"""

    # ---------- GET /knowledge/bases（列表） ----------

    async def test_list_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/knowledge/bases")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_list_with_invalid_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get(
            "/api/v1/knowledge/bases",
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_list_staff_returns_empty(self, client, db_session):
        # Arrange：list 仅需活跃用户，普通职工可访问
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/knowledge/bases", headers=headers)
        # Assert：当前为 TODO 桩实现，返回空列表
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["data"] == []
        assert body["total"] == 0

    async def test_list_with_pagination_returns_empty(self, client, db_session):
        # Arrange：合法分页参数应被接受
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get(
            "/api/v1/knowledge/bases?page=2&page_size=10", headers=headers
        )
        # Assert
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_invalid_page_returns_422(self, client, db_session):
        # Arrange：page 必须 >=1
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/knowledge/bases?page=0", headers=headers)
        # Assert
        assert resp.status_code == 422

    async def test_list_page_size_exceeds_limit_returns_422(self, client, db_session):
        # Arrange：page_size 上限 100，超出应 422
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get(
            "/api/v1/knowledge/bases?page_size=101", headers=headers
        )
        # Assert
        assert resp.status_code == 422

    # ---------- POST /knowledge/bases（创建） ----------

    async def test_create_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/knowledge/bases",
            json={"name": "企业制度库"},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_create_non_admin_returns_403(self, client, db_session):
        # Arrange：create 要求 admin，普通职工应被拒
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/knowledge/bases",
            json={"name": "企业制度库"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_create_admin_returns_null(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/knowledge/bases",
            json={"name": "企业制度库", "description": "企业制度"},
            headers=headers,
        )
        # Assert：当前为 TODO 桩实现，返回 data=null
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["data"] is None

    async def test_create_missing_name_returns_422(self, client, db_session):
        # Arrange：name 为必填，缺失应 422
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/knowledge/bases",
            json={"description": "无名称"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    async def test_create_empty_name_returns_422(self, client, db_session):
        # Arrange：name 最小长度 1，空串应 422
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/knowledge/bases",
            json={"name": ""},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    async def test_create_name_too_long_returns_422(self, client, db_session):
        # Arrange：name 最大长度 200，超出应 422
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/knowledge/bases",
            json={"name": "x" * 201},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    # ---------- GET /knowledge/bases/{kb_id}（详情） ----------

    async def test_get_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/knowledge/bases/kb-001")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_get_staff_returns_null(self, client, db_session):
        # Arrange：get 仅需活跃用户，普通职工可访问
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/knowledge/bases/kb-001", headers=headers)
        # Assert：当前为 TODO 桩实现，统一返回 data=null
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    # ---------- PUT /knowledge/bases/{kb_id}（更新） ----------

    async def test_update_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.put(
            "/api/v1/knowledge/bases/kb-001",
            json={"name": "新名称"},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_update_non_admin_returns_403(self, client, db_session):
        # Arrange：update 要求 admin，普通职工应被拒
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/knowledge/bases/kb-001",
            json={"name": "新名称"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_update_admin_returns_null(self, client, db_session):
        # Arrange：所有字段可选，部分更新应成功
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/knowledge/bases/kb-001",
            json={"description": "更新后的描述"},
            headers=headers,
        )
        # Assert：当前为 TODO 桩实现，统一返回 data=null
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    # ---------- DELETE /knowledge/bases/{kb_id}（删除） ----------

    async def test_delete_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.delete("/api/v1/knowledge/bases/kb-001")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_delete_non_admin_returns_403(self, client, db_session):
        # Arrange：delete 要求 admin，普通职工应被拒
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.delete("/api/v1/knowledge/bases/kb-001", headers=headers)
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_delete_admin_returns_success(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.delete("/api/v1/knowledge/bases/kb-001", headers=headers)
        # Assert：当前为 TODO 桩实现，返回成功
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["message"] == "删除成功"
