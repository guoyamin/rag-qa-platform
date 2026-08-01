"""
模板管理 API 集成测试。

覆盖 /api/v1/models/templates 下的 create / list / get / update / delete，
使用真实测试库验证 SQL，mock 外部依赖（LLM/Milvus/Vault 由 conftest autouse fixture 注入）。
遵循 AAA 模式，每测试独立（独立内存库），函数体 <=50 行。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import get_password_hash
from app.models.preset_template import PresetTemplate, TemplateType
from app.models.user import User, UserAuthType, UserRole, UserStatus

VALID_PASSWORD = "Passw0rd!"
DUMMY_ID = "00000000-0000-0000-0000-000000000000"

# 合法的创建负载；每测试独立内存库，name 可跨用例复用
VALID_CREATE_PAYLOAD: dict = {
    "name": "tpl-base",
    "template_type": "chat",
    "template": {"role": "system", "content": "你好 {{name}}"},
    "description": "基础模板",
    "is_default": False,
    "tags": ["faq"],
    "category": "service",
}


async def _create_user(
    db_session: AsyncSession,
    username: str,
    password: str = VALID_PASSWORD,
    role: UserRole = UserRole.ADMIN,
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


async def _login_token(client: AsyncClient, username: str) -> str:
    """登录并返回 access_token。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": VALID_PASSWORD,
            "auth_type": "local",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


async def _admin_token(
    client: AsyncClient, db_session: AsyncSession, username: str = "admin"
) -> tuple[User, str]:
    """创建管理员并登录，返回 (user, access_token)。"""
    user = await _create_user(db_session, username=username, role=UserRole.ADMIN)
    return user, await _login_token(client, username)


async def _staff_token(
    client: AsyncClient, db_session: AsyncSession, username: str = "staff"
) -> str:
    """创建普通职工并登录，返回 access_token。"""
    await _create_user(db_session, username=username, role=UserRole.STAFF)
    return await _login_token(client, username)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _insert_template(
    db_session: AsyncSession,
    name: str,
    template_type: TemplateType = TemplateType.CHAT,
    is_default: bool = False,
    is_active: bool = True,
    category: str | None = None,
    tags: list[str] | None = None,
) -> PresetTemplate:
    """直接向测试库插入一条模板，供 list/get/update/delete 用例准备数据。"""
    tpl = PresetTemplate(
        name=name,
        template_type=template_type,
        template={"role": "system", "content": "你好 {{name}}"},
        is_default=is_default,
        is_active=is_active,
        tags=tags or [],
        category=category,
    )
    db_session.add(tpl)
    await db_session.commit()
    await db_session.refresh(tpl)
    return tpl


@pytest.mark.integration
class TestTemplateAPI:
    """模板管理接口集成测试。"""

    # ---------- POST /models/templates ----------

    async def test_create_template_success_admin_and_persists(
        self, client, db_session, session_factory: async_sessionmaker[AsyncSession]
    ):
        # Arrange
        admin, token = await _admin_token(client, db_session, "admin1")
        # Act
        resp = await client.post(
            "/api/v1/models/templates",
            json=VALID_CREATE_PAYLOAD,
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "tpl-base"
        assert data["template_type"] == "chat"
        assert data["is_default"] is False
        assert data["is_active"] is True
        assert data["tags"] == ["faq"]
        assert data["category"] == "service"
        assert data["version"] == "v1.0"
        assert data["created_by"] == admin.id
        assert data["id"]
        # 真实写入测试库
        async with session_factory() as fresh:
            row = await fresh.execute(
                select(PresetTemplate).where(PresetTemplate.name == "tpl-base")
            )
            assert row.scalar_one().category == "service"

    async def test_create_template_duplicate_name_returns_400(self, client, db_session):
        # Arrange：同名模板已存在
        _, token = await _admin_token(client, db_session, "admin1")
        await _insert_template(db_session, name="tpl-base")
        # Act
        resp = await client.post(
            "/api/v1/models/templates",
            json=VALID_CREATE_PAYLOAD,
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    async def test_create_template_is_default_clears_existing_default(
        self,
        client,
        db_session,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        # Arrange：同类型已存在一个默认模板
        _, token = await _admin_token(client, db_session, "admin1")
        await _insert_template(db_session, name="old-default", is_default=True)
        payload = {**VALID_CREATE_PAYLOAD, "name": "new-default", "is_default": True}
        # Act
        resp = await client.post(
            "/api/v1/models/templates",
            json=payload,
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 201
        assert resp.json()["is_default"] is True
        async with session_factory() as fresh:
            row = await fresh.execute(
                select(PresetTemplate).where(PresetTemplate.name == "old-default")
            )
            assert row.scalar_one().is_default is False

    async def test_create_template_invalid_type_rejected(self, client, db_session):
        # Arrange：template_type 非合法枚举值。路由内 TemplateType(data.template_type)
        # 抛 ValueError 且未被异常处理器捕获；ServerErrorMiddleware 在发送 500 后会重新
        # 抛出该异常，故 ASGITransport 直接上抛 ValueError（生产环境表现为 HTTP 500）。
        # 备注：此处属于 API 未优雅校验枚举的已知缺口，理想应返回 400/422。
        _, token = await _admin_token(client, db_session, "admin1")
        payload = {
            **VALID_CREATE_PAYLOAD,
            "name": "bad-type",
            "template_type": "not_a_type",
        }
        # Act / Assert：非法枚举不被优雅处理，直接抛 ValueError
        with pytest.raises(ValueError, match="not_a_type"):
            await client.post(
                "/api/v1/models/templates",
                json=payload,
                headers=_auth_headers(token),
            )

    async def test_create_template_non_admin_returns_403(self, client, db_session):
        # Arrange：普通职工登录
        token = await _staff_token(client, db_session, "staff1")
        # Act
        resp = await client.post(
            "/api/v1/models/templates",
            json=VALID_CREATE_PAYLOAD,
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_create_template_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post("/api/v1/models/templates", json=VALID_CREATE_PAYLOAD)
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    # ---------- GET /models/templates ----------

    async def test_list_templates_returns_all(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        await _insert_template(db_session, name="c1")
        await _insert_template(db_session, name="c2")
        # Act
        resp = await client.get(
            "/api/v1/models/templates", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert {it["name"] for it in body["items"]} == {"c1", "c2"}

    async def test_list_templates_filter_by_type(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        await _insert_template(db_session, name="c1", template_type=TemplateType.CHAT)
        await _insert_template(db_session, name="c2", template_type=TemplateType.CHAT)
        await _insert_template(
            db_session, name="s1", template_type=TemplateType.SYSTEM_PROMPT
        )
        # Act
        resp = await client.get(
            "/api/v1/models/templates",
            params={"template_type": "system_prompt"},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 200
        names = [it["name"] for it in resp.json()["items"]]
        assert names == ["s1"]

    async def test_list_templates_filter_by_is_active(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        await _insert_template(db_session, name="active1", is_active=True)
        await _insert_template(db_session, name="inactive1", is_active=False)
        # Act
        resp = await client.get(
            "/api/v1/models/templates",
            params={"is_active": "true"},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert [it["name"] for it in items] == ["active1"]
        assert all(it["is_active"] for it in items)

    async def test_list_templates_pagination(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        for i in range(3):
            await _insert_template(db_session, name=f"t{i}")
        # Act
        resp = await client.get(
            "/api/v1/models/templates",
            params={"page": 1, "page_size": 2},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert len(body["items"]) == 2

    async def test_list_templates_non_admin_returns_403(self, client, db_session):
        # Arrange
        token = await _staff_token(client, db_session, "staff1")
        # Act
        resp = await client.get(
            "/api/v1/models/templates", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_list_templates_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/models/templates")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    # ---------- GET /models/templates/{id} ----------

    async def test_get_template_success(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        tpl = await _insert_template(db_session, name="g1", category="cat-x")
        # Act
        resp = await client.get(
            f"/api/v1/models/templates/{tpl.id}", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == tpl.id
        assert data["name"] == "g1"
        assert data["category"] == "cat-x"

    async def test_get_template_not_found_returns_404(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        # Act
        resp = await client.get(
            f"/api/v1/models/templates/{DUMMY_ID}", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    async def test_get_template_non_admin_returns_403(self, client, db_session):
        # Arrange
        token = await _staff_token(client, db_session, "staff1")
        # Act
        resp = await client.get(
            f"/api/v1/models/templates/{DUMMY_ID}", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_get_template_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get(f"/api/v1/models/templates/{DUMMY_ID}")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    # ---------- PUT /models/templates/{id} ----------

    async def test_update_template_success(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        tpl = await _insert_template(db_session, name="up1")
        # Act
        resp = await client.put(
            f"/api/v1/models/templates/{tpl.id}",
            json={"name": "up1-renamed", "description": "updated"},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "up1-renamed"
        assert data["description"] == "updated"

    async def test_update_template_not_found_returns_404(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        # Act
        resp = await client.put(
            f"/api/v1/models/templates/{DUMMY_ID}",
            json={"name": "x"},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    async def test_update_template_duplicate_name_returns_400(self, client, db_session):
        # Arrange：两个模板，把第二个改名成第一个的名字
        _, token = await _admin_token(client, db_session, "admin1")
        await _insert_template(db_session, name="dup-a")
        tpl_b = await _insert_template(db_session, name="dup-b")
        # Act
        resp = await client.put(
            f"/api/v1/models/templates/{tpl_b.id}",
            json={"name": "dup-a"},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    async def test_update_template_set_default_clears_others(
        self,
        client,
        db_session,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        await _insert_template(db_session, name="d1", is_default=True)
        tpl_b = await _insert_template(db_session, name="d2", is_default=False)
        # Act
        resp = await client.put(
            f"/api/v1/models/templates/{tpl_b.id}",
            json={"is_default": True},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True
        async with session_factory() as fresh:
            row = await fresh.execute(
                select(PresetTemplate).where(PresetTemplate.name == "d1")
            )
            assert row.scalar_one().is_default is False

    async def test_update_template_deactivate(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        tpl = await _insert_template(db_session, name="deact1")
        # Act
        resp = await client.put(
            f"/api/v1/models/templates/{tpl.id}",
            json={"is_active": False},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_update_template_non_admin_returns_403(self, client, db_session):
        # Arrange
        token = await _staff_token(client, db_session, "staff1")
        # Act
        resp = await client.put(
            f"/api/v1/models/templates/{DUMMY_ID}",
            json={"name": "x"},
            headers=_auth_headers(token),
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_update_template_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.put(
            f"/api/v1/models/templates/{DUMMY_ID}", json={"name": "x"}
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    # ---------- DELETE /models/templates/{id} ----------

    async def test_delete_template_success_returns_204(
        self,
        client,
        db_session,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        tpl = await _insert_template(db_session, name="del1", is_default=False)
        # Act
        resp = await client.delete(
            f"/api/v1/models/templates/{tpl.id}", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 204
        async with session_factory() as fresh:
            row = await fresh.execute(
                select(PresetTemplate).where(PresetTemplate.id == tpl.id)
            )
            assert row.scalar_one_or_none() is None

    async def test_delete_template_not_found_returns_404(self, client, db_session):
        # Arrange
        _, token = await _admin_token(client, db_session, "admin1")
        # Act
        resp = await client.delete(
            f"/api/v1/models/templates/{DUMMY_ID}", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    async def test_delete_default_template_returns_400(self, client, db_session):
        # Arrange：默认模板不可删除
        _, token = await _admin_token(client, db_session, "admin1")
        tpl = await _insert_template(db_session, name="defdel", is_default=True)
        # Act
        resp = await client.delete(
            f"/api/v1/models/templates/{tpl.id}", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    async def test_delete_template_non_admin_returns_403(self, client, db_session):
        # Arrange
        token = await _staff_token(client, db_session, "staff1")
        # Act
        resp = await client.delete(
            f"/api/v1/models/templates/{DUMMY_ID}", headers=_auth_headers(token)
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_delete_template_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.delete(f"/api/v1/models/templates/{DUMMY_ID}")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"
