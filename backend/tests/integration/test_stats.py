"""
用量统计 API 集成测试。

覆盖 /api/v1/stats 下的 usage / models/ranking / users/ranking，使用真实测试库验证
SQL 聚合，mock 外部依赖（LLM/Milvus/Vault 由 conftest autouse fixture 注入）。
遵循 AAA 模式，每测试独立（独立内存库），函数体 <=50 行。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.usage_log import ModelUsageLog
from app.models.user import User, UserAuthType, UserRole, UserStatus

VALID_PASSWORD = "Passw0rd!"


async def _create_user(
    db_session: AsyncSession,
    username: str,
    role: UserRole,
    password: str = VALID_PASSWORD,
) -> User:
    """在测试库创建本地认证用户。"""
    user = User(
        username=username,
        display_name=username,
        hashed_password=get_password_hash(password),
        auth_type=UserAuthType.LOCAL,
        role=role,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client, username: str, password: str = VALID_PASSWORD) -> str:
    """登录并返回 access_token。"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "auth_type": "local"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    """构造 Bearer 认证头。"""
    return {"Authorization": f"Bearer {token}"}


async def _create_admin(client, db_session, username: str = "admin") -> str:
    """创建管理员并登录，返回 access_token。"""
    await _create_user(db_session, username=username, role=UserRole.ADMIN)
    return await _login(client, username)


async def _log(
    db_session: AsyncSession,
    *,
    model_id: str = "model-1",
    user_id: str | None = "user-1",
    input_tokens: int = 100,
    output_tokens: int = 50,
    total_tokens: int | None = None,
    success: bool = True,
    cost: Decimal = Decimal("0.001"),
    created_at: datetime | None = None,
) -> ModelUsageLog:
    """插入一条用量日志并提交。"""
    tokens = total_tokens if total_tokens is not None else input_tokens + output_tokens
    log = ModelUsageLog(
        model_id=model_id,
        user_id=user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=tokens,
        success=success,
        cost=cost,
        created_at=created_at or datetime.now(),
    )
    db_session.add(log)
    await db_session.commit()
    return log


@pytest.mark.integration
class TestStatsAPI:
    """用量统计接口集成测试。"""

    # ===== 权限：未认证 =====

    async def test_usage_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/stats/usage")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_model_ranking_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/stats/models/ranking")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_user_ranking_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/stats/users/ranking")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    # ===== 权限：非管理员 =====

    async def test_usage_non_admin_returns_403(self, client, db_session):
        # Arrange
        await _create_user(db_session, username="staff", role=UserRole.STAFF)
        token = await _login(client, "staff")
        # Act
        resp = await client.get("/api/v1/stats/usage", headers=_auth(token))
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_model_ranking_non_admin_returns_403(self, client, db_session):
        # Arrange
        await _create_user(db_session, username="staff", role=UserRole.STAFF)
        token = await _login(client, "staff")
        # Act
        resp = await client.get("/api/v1/stats/models/ranking", headers=_auth(token))
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_user_ranking_non_admin_returns_403(self, client, db_session):
        # Arrange
        await _create_user(db_session, username="staff", role=UserRole.STAFF)
        token = await _login(client, "staff")
        # Act
        resp = await client.get("/api/v1/stats/users/ranking", headers=_auth(token))
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    # ===== /usage 成功与边界 =====

    async def test_usage_empty_returns_zeros(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        # Act
        resp = await client.get("/api/v1/stats/usage", headers=_auth(token))
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tokens"] == 0
        assert data["input_tokens"] == 0
        assert data["output_tokens"] == 0
        assert data["total_cost"] == 0
        assert data["total_calls"] == 0
        assert data["success_calls"] == 0
        assert data["failed_calls"] == 0

    async def test_usage_aggregates_multiple_logs(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(
            db_session, input_tokens=100, output_tokens=50, cost=Decimal("0.010")
        )
        await _log(
            db_session, input_tokens=200, output_tokens=100, cost=Decimal("0.020")
        )
        # Act
        resp = await client.get("/api/v1/stats/usage", headers=_auth(token))
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tokens"] == 450
        assert data["input_tokens"] == 300
        assert data["output_tokens"] == 150
        assert data["total_calls"] == 2
        assert data["success_calls"] == 2
        assert data["failed_calls"] == 0
        assert data["total_cost"] == pytest.approx(0.030)

    async def test_usage_filters_by_model_id(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(db_session, model_id="m-a")
        await _log(db_session, model_id="m-a")
        await _log(db_session, model_id="m-b")
        # Act
        resp = await client.get(
            "/api/v1/stats/usage?model_id=m-a", headers=_auth(token)
        )
        # Assert
        assert resp.status_code == 200
        assert resp.json()["total_calls"] == 2

    async def test_usage_filters_by_user_id(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(db_session, user_id="u-1")
        await _log(db_session, user_id="u-2")
        # Act
        resp = await client.get("/api/v1/stats/usage?user_id=u-1", headers=_auth(token))
        # Assert
        assert resp.status_code == 200
        assert resp.json()["total_calls"] == 1

    async def test_usage_counts_success_and_failed(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(db_session, success=True)
        await _log(db_session, success=False)
        await _log(db_session, success=True)
        # Act
        resp = await client.get("/api/v1/stats/usage", headers=_auth(token))
        # Assert
        data = resp.json()
        assert data["total_calls"] == 3
        assert data["success_calls"] == 2
        assert data["failed_calls"] == 1

    async def test_usage_days_filter_excludes_old_logs(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(db_session, created_at=datetime.now())
        await _log(db_session, created_at=datetime.now() - timedelta(days=50))
        # Act：days=7 应排除 50 天前的日志
        resp = await client.get("/api/v1/stats/usage?days=7", headers=_auth(token))
        # Assert
        assert resp.status_code == 200
        assert resp.json()["total_calls"] == 1

    async def test_usage_days_param_validation(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        # Act / Assert：days 下界（ge=1）
        resp_low = await client.get("/api/v1/stats/usage?days=0", headers=_auth(token))
        assert resp_low.status_code == 422
        # Act / Assert：days 上界（le=90）
        resp_high = await client.get(
            "/api/v1/stats/usage?days=91", headers=_auth(token)
        )
        assert resp_high.status_code == 422

    # ===== /models/ranking 成功与边界 =====

    async def test_model_ranking_empty_returns_empty_list(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        # Act
        resp = await client.get("/api/v1/stats/models/ranking", headers=_auth(token))
        # Assert
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_model_ranking_orders_by_cost_desc(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(db_session, model_id="m-a", cost=Decimal("0.010"))
        await _log(db_session, model_id="m-b", cost=Decimal("0.030"))
        await _log(db_session, model_id="m-c", cost=Decimal("0.020"))
        # Act
        resp = await client.get("/api/v1/stats/models/ranking", headers=_auth(token))
        # Assert
        items = resp.json()["items"]
        assert [i["model_id"] for i in items] == ["m-b", "m-c", "m-a"]

    async def test_model_ranking_respects_limit(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(db_session, model_id="m-a", cost=Decimal("0.010"))
        await _log(db_session, model_id="m-b", cost=Decimal("0.030"))
        await _log(db_session, model_id="m-c", cost=Decimal("0.020"))
        # Act
        resp = await client.get(
            "/api/v1/stats/models/ranking?limit=2", headers=_auth(token)
        )
        # Assert
        items = resp.json()["items"]
        assert len(items) == 2
        assert items[0]["model_id"] == "m-b"

    async def test_model_ranking_days_filter_excludes_old_logs(
        self, client, db_session
    ):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(
            db_session,
            model_id="m-old",
            cost=Decimal("0.030"),
            created_at=datetime.now() - timedelta(days=50),
        )
        await _log(db_session, model_id="m-new", cost=Decimal("0.010"))
        # Act：days=7 排除 50 天前日志
        resp = await client.get(
            "/api/v1/stats/models/ranking?days=7", headers=_auth(token)
        )
        # Assert
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["model_id"] == "m-new"

    async def test_model_ranking_limit_param_validation(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        # Act / Assert：limit 下界（ge=1）
        resp_low = await client.get(
            "/api/v1/stats/models/ranking?limit=0", headers=_auth(token)
        )
        assert resp_low.status_code == 422
        # Act / Assert：limit 上界（le=50）
        resp_high = await client.get(
            "/api/v1/stats/models/ranking?limit=51", headers=_auth(token)
        )
        assert resp_high.status_code == 422

    # ===== /users/ranking 成功与边界 =====

    async def test_user_ranking_empty_returns_empty_list(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        # Act
        resp = await client.get("/api/v1/stats/users/ranking", headers=_auth(token))
        # Assert
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_user_ranking_orders_by_cost_desc(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(db_session, user_id="u-a", cost=Decimal("0.010"))
        await _log(db_session, user_id="u-b", cost=Decimal("0.030"))
        # Act
        resp = await client.get("/api/v1/stats/users/ranking", headers=_auth(token))
        # Assert
        items = resp.json()["items"]
        assert [i["user_id"] for i in items] == ["u-b", "u-a"]

    async def test_user_ranking_respects_limit(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        await _log(db_session, user_id="u-a", cost=Decimal("0.010"))
        await _log(db_session, user_id="u-b", cost=Decimal("0.030"))
        await _log(db_session, user_id="u-c", cost=Decimal("0.020"))
        # Act
        resp = await client.get(
            "/api/v1/stats/users/ranking?limit=2", headers=_auth(token)
        )
        # Assert
        items = resp.json()["items"]
        assert len(items) == 2
        assert items[0]["user_id"] == "u-b"

    async def test_user_ranking_limit_param_validation(self, client, db_session):
        # Arrange
        token = await _create_admin(client, db_session)
        # Act / Assert：limit 下界（ge=1）
        resp_low = await client.get(
            "/api/v1/stats/users/ranking?limit=0", headers=_auth(token)
        )
        assert resp_low.status_code == 422
        # Act / Assert：limit 上界（le=50）
        resp_high = await client.get(
            "/api/v1/stats/users/ranking?limit=51", headers=_auth(token)
        )
        assert resp_high.status_code == 422
