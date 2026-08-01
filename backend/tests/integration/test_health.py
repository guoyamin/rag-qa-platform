"""
健康检查 API 集成测试。

覆盖 /api/v1/health 下的 models / models/{id} / summary，使用真实测试库验证 SQL，
mock 外部依赖（LLM/Milvus/Vault 由 conftest autouse fixture 注入；httpx 网络探测
由本地 mock_httpx fixture 注入，避免真实网络）。遵循 AAA 模型，每测试独立内存库，
函数体 <=50 行。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.health_log import ModelHealthLog
from app.models.model_instance import ModelInstance, ModelProvider, ModelStatus
from app.models.user import User, UserAuthType, UserRole, UserStatus

VALID_PASSWORD = "Passw0rd!"


# ==================== 辅助函数 ====================


async def _create_user(
    db_session: AsyncSession,
    username: str = "admin",
    password: str = VALID_PASSWORD,
    role: UserRole = UserRole.ADMIN,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """在测试库创建用户（commit 后释放连接，避免与请求争用单连接）。"""
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


async def _login_token(client, username: str, password: str = VALID_PASSWORD) -> str:
    """登录并返回 access_token。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "auth_type": "local"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


async def _admin_headers(
    client,
    db_session: AsyncSession,
    username: str = "admin",
) -> dict[str, str]:
    """创建管理员用户并返回带 access_token 的请求头。"""
    await _create_user(db_session, username=username, role=UserRole.ADMIN)
    token = await _login_token(client, username)
    return {"Authorization": f"Bearer {token}"}


async def _create_model(
    db_session: AsyncSession,
    name: str,
    provider: ModelProvider = ModelProvider.LOCAL,
    status: ModelStatus = ModelStatus.ACTIVE,
    config: dict | None = None,
) -> ModelInstance:
    """在测试库创建模型实例。"""
    model = ModelInstance(
        name=name,
        provider=provider,
        model_type="chat",
        api_key_id=None,
        config=config or {"api_base": "http://localhost:8000/v1", "timeout": 5},
        status=status,
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


# ==================== httpx mock ====================


class _HttpxController:
    """控制 fake httpx 客户端的探测结果。

    - succeed()/fail()：所有探测统一成功/失败。
    - sequence(*outcomes)：按调用顺序依次返回结果，末位结果重复用于后续调用。
    """

    def __init__(self) -> None:
        self._outcomes: list[bool] = [True]

    def succeed(self) -> None:
        self._outcomes = [True]

    def fail(self) -> None:
        self._outcomes = [False]

    def sequence(self, *outcomes: bool) -> None:
        self._outcomes = list(outcomes) or [True]

    def next_outcome(self) -> bool:
        if len(self._outcomes) > 1:
            return self._outcomes.pop(0)
        return self._outcomes[0]


@pytest.fixture
def mock_httpx(monkeypatch: pytest.MonkeyPatch) -> _HttpxController:
    """Patch httpx.AsyncClient，使健康探测不触达真实网络。

    返回控制器：succeed()/fail()/sequence() 设定探测结果。
    """
    controller = _HttpxController()

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info) -> bool:
            return False

        async def get(self, *args, **kwargs):
            if not controller.next_outcome():
                raise httpx.ConnectError("connection refused")
            return _FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    return controller


# ==================== 测试 ====================


@pytest.mark.integration
class TestHealthAPI:
    """健康检查接口集成测试。"""

    async def test_models_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/health/models")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_models_with_staff_token_returns_403(self, client, db_session):
        # Arrange：普通职工无管理员权限
        await _create_user(db_session, username="staff1", role=UserRole.STAFF)
        token = await _login_token(client, "staff1")
        # Act
        resp = await client.get(
            "/api/v1/health/models",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_models_empty_when_no_active_models(
        self, client, db_session, mock_httpx
    ):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/health/models", headers=headers)
        # Assert
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_models_returns_healthy_for_active_local_model(
        self, client, db_session, mock_httpx
    ):
        # Arrange
        headers = await _admin_headers(client, db_session)
        model = await _create_model(db_session, name="local-1")
        mock_httpx.succeed()
        # Act
        resp = await client.get("/api/v1/health/models", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["model_id"] == model.id
        assert data[0]["status"] == "healthy"
        assert data[0]["latency_ms"] is not None
        assert data[0]["error_message"] is None

    async def test_models_returns_unhealthy_when_ping_fails(
        self, client, db_session, mock_httpx
    ):
        # Arrange
        headers = await _admin_headers(client, db_session)
        model = await _create_model(db_session, name="down-1")
        mock_httpx.fail()
        # Act
        resp = await client.get("/api/v1/health/models", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["model_id"] == model.id
        assert data[0]["status"] == "unhealthy"
        assert data[0]["error_message"] is not None

    async def test_models_skips_inactive_models(self, client, db_session, mock_httpx):
        # Arrange：一个活跃、一个停用，仅活跃模型被检查
        headers = await _admin_headers(client, db_session)
        active = await _create_model(
            db_session, name="active", status=ModelStatus.ACTIVE
        )
        await _create_model(db_session, name="inactive", status=ModelStatus.INACTIVE)
        mock_httpx.succeed()
        # Act
        resp = await client.get("/api/v1/health/models", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["model_id"] == active.id

    async def test_models_persists_health_logs(
        self, client, db_session, session_factory, mock_httpx
    ):
        # Arrange
        headers = await _admin_headers(client, db_session)
        model = await _create_model(db_session, name="logged")
        mock_httpx.succeed()
        # Act
        resp = await client.get("/api/v1/health/models", headers=headers)
        # Assert：响应成功且真实写入健康日志到测试库
        assert resp.status_code == 200
        async with session_factory() as fresh:
            result = await fresh.execute(select(ModelHealthLog))
            logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].model_id == model.id
        assert logs[0].status == "healthy"

    async def test_single_model_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/health/models/some-id")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_single_model_healthy_local(self, client, db_session, mock_httpx):
        # Arrange
        headers = await _admin_headers(client, db_session)
        model = await _create_model(db_session, name="single-ok")
        mock_httpx.succeed()
        # Act
        resp = await client.get(f"/api/v1/health/models/{model.id}", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_id"] == model.id
        assert data["status"] == "healthy"
        assert data["latency_ms"] is not None

    async def test_single_model_unknown_when_not_found(
        self, client, db_session, mock_httpx
    ):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act：不存在的 model_id
        resp = await client.get("/api/v1/health/models/nonexistent-id", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unknown"
        assert data["error_message"] == "模型不存在"

    async def test_single_model_unhealthy_when_ping_fails(
        self, client, db_session, mock_httpx
    ):
        # Arrange
        headers = await _admin_headers(client, db_session)
        model = await _create_model(db_session, name="single-down")
        mock_httpx.fail()
        # Act
        resp = await client.get(f"/api/v1/health/models/{model.id}", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["error_message"] is not None

    async def test_single_model_healthy_cloud(self, client, db_session, mock_httpx):
        # Arrange：云端提供商，api_key_id 为 None（_get_api_key 直接返回空串，不触碰 Vault）
        headers = await _admin_headers(client, db_session)
        model = await _create_model(
            db_session,
            name="cloud-1",
            provider=ModelProvider.OPENAI,
            config={"api_base": "https://api.openai.com/v1"},
        )
        mock_httpx.succeed()
        # Act
        resp = await client.get(f"/api/v1/health/models/{model.id}", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_id"] == model.id
        assert data["status"] == "healthy"

    async def test_summary_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/health/summary")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_summary_empty_when_no_models(self, client, db_session, mock_httpx):
        # Arrange
        headers = await _admin_headers(client, db_session)
        # Act
        resp = await client.get("/api/v1/health/summary", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_models"] == 0
        assert data["healthy_count"] == 0
        assert data["degraded_count"] == 0
        assert data["unhealthy_count"] == 0
        assert data["unknown_count"] == 0

    async def test_summary_counts_mixed_statuses(self, client, db_session, mock_httpx):
        # Arrange：两个活跃模型，探测结果一成一败
        headers = await _admin_headers(client, db_session)
        await _create_model(db_session, name="sum-ok")
        await _create_model(db_session, name="sum-bad")
        mock_httpx.sequence(True, False)
        # Act
        resp = await client.get("/api/v1/health/summary", headers=headers)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_models"] == 2
        assert data["healthy_count"] == 1
        assert data["unhealthy_count"] == 1
        assert data["degraded_count"] == 0
        assert data["unknown_count"] == 0
