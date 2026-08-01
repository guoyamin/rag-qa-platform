"""
文档管理 API 集成测试。

覆盖 /api/v1/documents 下的 list / upload / get / delete / reindex，
使用真实测试库验证 SQL（用户认证经 get_current_user 走真实库），mock 外部依赖
（LLM/Milvus/Vault 由 conftest autouse fixture 注入）。当前 document 路由为
TODO 桩实现，业务逻辑尚未落地，故用例聚焦于权限边界、入参校验与响应契约
（桩实现的真实行为），遵循 AAA 模式，每测试独立内存库，函数体 <=50 行。
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User, UserAuthType, UserRole, UserStatus

VALID_PASSWORD = "Passw0rd!"
DUMMY_ID = "00000000-0000-0000-0000-000000000000"


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
class TestDocumentAPI:
    """文档管理接口集成测试。"""

    # ---------- GET /documents（列表） ----------

    async def test_list_documents_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/documents")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_list_documents_staff_returns_empty(self, client, db_session):
        # Arrange：list 仅需活跃用户（get_current_active_user），普通职工可访问
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/documents", headers=headers)
        # Assert：当前为 TODO 桩实现，返回空列表
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["data"] == []
        assert body["total"] == 0

    async def test_list_documents_invalid_page_returns_422(self, client, db_session):
        # Arrange：PaginationParams.page 必须 >=1
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/documents?page=0", headers=headers)
        # Assert
        assert resp.status_code == 422

    async def test_list_documents_invalid_page_size_returns_422(
        self, client, db_session
    ):
        # Arrange：PaginationParams.page_size 上限 100
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/documents?page_size=101", headers=headers)
        # Assert
        assert resp.status_code == 422

    async def test_list_documents_with_kb_id_param_accepted(self, client, db_session):
        # Arrange：kb_id 为可选过滤参数，传入合法值不应报错
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get(
            "/api/v1/documents", params={"kb_id": DUMMY_ID}, headers=headers
        )
        # Assert：桩实现忽略过滤，仍返回空列表
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    # ---------- POST /documents/upload（上传，仅管理员） ----------

    async def test_upload_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/documents/upload",
            params={"kb_id": DUMMY_ID},
            files={"file": ("t.pdf", b"data", "application/pdf")},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_upload_non_admin_returns_403(self, client, db_session):
        # Arrange：upload 要求 require_admin，普通职工应被拒
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/documents/upload",
            params={"kb_id": DUMMY_ID},
            files={"file": ("t.pdf", b"data", "application/pdf")},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_upload_admin_success_returns_pending(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/documents/upload",
            params={"kb_id": DUMMY_ID},
            files={"file": ("policy.pdf", b"%PDF-1.4", "application/pdf")},
            headers=headers,
        )
        # Assert：桩实现返回 pending 占位响应，title 取上传文件名
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "temp"
        assert data["title"] == "policy.pdf"
        assert data["status"] == "pending"
        assert data["message"] == "文档已接收，正在处理中"

    async def test_upload_missing_file_returns_422(self, client, db_session):
        # Arrange：file 为必填 UploadFile。发送 multipart 但不含 "file" 字段
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/documents/upload",
            params={"kb_id": DUMMY_ID},
            files={"note": ("note.txt", b"ignore", "text/plain")},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    async def test_upload_missing_kb_id_returns_422(self, client, db_session):
        # Arrange：kb_id 为必填查询参数，缺失应 422
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("t.pdf", b"data", "application/pdf")},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    # ---------- GET /documents/{doc_id}（详情，仅需活跃用户） ----------

    async def test_get_document_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get(f"/api/v1/documents/{DUMMY_ID}")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_get_document_staff_returns_null(self, client, db_session):
        # Arrange：get 仅需活跃用户，普通职工可访问
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.get(f"/api/v1/documents/{DUMMY_ID}", headers=headers)
        # Assert：当前为 TODO 桩实现，统一返回 data=null
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    # ---------- DELETE /documents/{doc_id}（删除，仅管理员） ----------

    async def test_delete_document_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.delete(f"/api/v1/documents/{DUMMY_ID}")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_delete_document_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.delete(f"/api/v1/documents/{DUMMY_ID}", headers=headers)
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_delete_document_admin_returns_success(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.delete(f"/api/v1/documents/{DUMMY_ID}", headers=headers)
        # Assert：桩实现返回成功
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["message"] == "删除成功"

    # ---------- POST /documents/{doc_id}/reindex（重建索引，仅管理员） ----------

    async def test_reindex_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(f"/api/v1/documents/{DUMMY_ID}/reindex")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_reindex_non_admin_returns_403(self, client, db_session):
        # Arrange
        headers = await _staff_headers(client, db_session)
        # Act
        resp = await client.post(
            f"/api/v1/documents/{DUMMY_ID}/reindex", headers=headers
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_reindex_admin_returns_success(self, client, db_session):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.post(
            f"/api/v1/documents/{DUMMY_ID}/reindex", headers=headers
        )
        # Assert：桩实现返回成功
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SUCCESS"
        assert body["message"] == "重新索引任务已提交"
