"""
公告管理 API 集成测试。

覆盖 /api/v1/announcements 下各端点：list / create / get / update / delete / publish，
使用真实测试库验证 SQL（create 端点验证落库），mock 外部依赖
（LLM/Milvus/Vault 由 conftest autouse fixture 注入）。所有端点均要求 admin
（require_admin）。遵循 AAA 模式，每测试独立内存库，函数体 <=50 行。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import get_password_hash
from app.models.announcement import Announcement, AnnouncementStatus, AnnouncementType
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
class TestAnnouncementAPI:
    """公告管理接口集成测试。"""

    # ---------- GET /announcements（列表） ----------

    async def test_list_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/announcements")
        # Assert
        assert resp.status_code == 401

    async def test_list_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/announcements", headers=headers)
        # Assert
        assert resp.status_code == 403

    async def test_list_admin_returns_empty(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/announcements", headers=headers)
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_list_invalid_page_returns_422(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/announcements?page=0", headers=headers)
        # Assert
        assert resp.status_code == 422

    # ---------- POST /announcements（创建） ----------

    async def test_create_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/announcements",
            json={"title": "标题", "content": "内容"},
        )
        # Assert
        assert resp.status_code == 401

    async def test_create_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/announcements",
            json={"title": "标题", "content": "内容"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 403

    async def test_create_admin_success_persists_to_db(
        self,
        client,
        db_session,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        # Arrange
        headers = await _admin_headers(client, db_session)
        payload = {"title": "新公告", "content": "公告内容"}
        # Act
        resp = await client.post("/api/v1/announcements", json=payload, headers=headers)
        # Assert
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == "新公告"
        assert data["content"] == "公告内容"
        assert data["status"] == "draft"
        assert data["pinned"] is False
        assert "hashed_password" not in data
        # 验证落库
        async with session_factory() as fresh:
            result = await fresh.execute(
                select(Announcement).where(Announcement.title == "新公告")
            )
            persisted = result.scalar_one()
            assert persisted.status == AnnouncementStatus.DRAFT

    async def test_create_duplicate_title_returns_400(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # 先直接写入同名公告
        ann = Announcement(
            title="重复标题",
            content="内容",
            type=AnnouncementType.NOTICE,
            status=AnnouncementStatus.DRAFT,
        )
        db_session.add(ann)
        await db_session.commit()
        # Act
        resp = await client.post(
            "/api/v1/announcements",
            json={"title": "重复标题", "content": "新内容"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    async def test_create_short_content_returns_422(self, client, db_session):
        # Arrange：content 为必填，min_length=1
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/announcements",
            json={"title": "标题", "content": ""},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    # ---------- GET /announcements/{id}（详情） ----------

    async def test_get_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/announcements/some-id")
        # Assert
        assert resp.status_code == 401

    async def test_get_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/announcements/some-id", headers=headers)
        # Assert
        assert resp.status_code == 403

    async def test_get_admin_returns_404_for_missing(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/announcements/nonexistent", headers=headers)
        # Assert
        assert resp.status_code == 404

    async def test_get_admin_returns_announcement(self, client, db_session):
        # Arrange：先创建一条公告
        headers = await _admin_headers(client, db_session)
        create_resp = await client.post(
            "/api/v1/announcements",
            json={"title": "详情公告", "content": "内容"},
            headers=headers,
        )
        ann_id = create_resp.json()["id"]
        # Act
        resp = await client.get(f"/api/v1/announcements/{ann_id}", headers=headers)
        # Assert
        assert resp.status_code == 200
        assert resp.json()["title"] == "详情公告"

    # ---------- PUT /announcements/{id}（更新） ----------

    async def test_update_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.put("/api/v1/announcements/some-id", json={})
        # Assert
        assert resp.status_code == 401

    async def test_update_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/announcements/some-id", json={}, headers=headers
        )
        # Assert
        assert resp.status_code == 403

    async def test_update_missing_returns_404(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/announcements/missing",
            json={"title": "新标题"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 404

    async def test_update_admin_success(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        create_resp = await client.post(
            "/api/v1/announcements",
            json={"title": "原标题", "content": "原内容"},
            headers=headers,
        )
        ann_id = create_resp.json()["id"]
        # Act
        resp = await client.put(
            f"/api/v1/announcements/{ann_id}",
            json={"title": "新标题", "pinned": True},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "新标题"
        assert body["pinned"] is True
        assert body["content"] == "原内容"  # 未更新的字段保持不变

    # ---------- DELETE /announcements/{id}（删除） ----------

    async def test_delete_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.delete("/api/v1/announcements/some-id")
        # Assert
        assert resp.status_code == 401

    async def test_delete_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.delete("/api/v1/announcements/some-id", headers=headers)
        # Assert
        assert resp.status_code == 403

    async def test_delete_missing_returns_404(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.delete("/api/v1/announcements/missing", headers=headers)
        # Assert
        assert resp.status_code == 404

    async def test_delete_admin_returns_204(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        create_resp = await client.post(
            "/api/v1/announcements",
            json={"title": "待删公告", "content": "内容"},
            headers=headers,
        )
        ann_id = create_resp.json()["id"]
        # Act
        resp = await client.delete(f"/api/v1/announcements/{ann_id}", headers=headers)
        # Assert
        assert resp.status_code == 204

    # ---------- PUT /announcements/{id}/publish（发布） ----------

    async def test_publish_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.put("/api/v1/announcements/some-id/publish")
        # Assert
        assert resp.status_code == 401

    async def test_publish_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/announcements/some-id/publish", headers=headers
        )
        # Assert
        assert resp.status_code == 403

    async def test_publish_missing_returns_404(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/announcements/missing/publish", headers=headers
        )
        # Assert
        assert resp.status_code == 404

    async def test_publish_draft_turns_to_published(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        create_resp = await client.post(
            "/api/v1/announcements",
            json={"title": "草稿公告", "content": "内容"},
            headers=headers,
        )
        ann_id = create_resp.json()["id"]
        # Act
        resp = await client.put(
            f"/api/v1/announcements/{ann_id}/publish", headers=headers
        )
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "published"
        assert body["published_at"] is not None
