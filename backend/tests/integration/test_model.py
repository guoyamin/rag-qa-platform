"""
模型管理 API 集成测试。

覆盖 /api/v1/models 下的 API Key 管理（创建/列表/详情/更新/删除/轮换/Vault 健康检查）
与模型实例管理（创建/列表/详情/更新/状态切换/删除/对比）接口。使用真实测试库验证
SQL 与 service 逻辑，mock 外部依赖（LLM/Milvus/Vault 由 conftest autouse fixture 注入）。
遵循 AAA 模式，每测试独立（独立内存库），函数体 <=50 行。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.llm.base import LLMResponse
from app.models.api_key import ApiKey, ApiKeyStatus, ApiKeyUsage
from app.models.model_instance import ModelInstance, ModelProvider, ModelStatus
from app.models.user import User, UserAuthType, UserRole, UserStatus
from app.services.llm_manager import get_llm_manager
from app.services.vault_client import get_vault_client

VALID_PASSWORD = "Passw0rd!"

# 复用的合法请求体
_KEY_PAYLOAD = {
    "name": "my-key",
    "provider": "openai",
    "api_key": "sk-testkey123456",
    "usage": "llm",
}
_MODEL_PAYLOAD = {
    "name": "my-model",
    "provider": "openai",
    "model_type": "chat",
    "config": {
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 2048,
        "timeout": 60,
    },
}


async def _create_user(
    db_session: AsyncSession,
    username: str = "adminuser",
    password: str = VALID_PASSWORD,
    role: UserRole = UserRole.ADMIN,
) -> User:
    """在测试库创建本地认证用户（commit 后供请求侧 get_current_user 读取）。"""
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
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    """构造 Bearer 认证头。"""
    return {"Authorization": f"Bearer {token}"}


async def _admin_auth(client, db_session, username: str = "admin") -> dict[str, str]:
    """创建管理员并登录，返回认证头。"""
    await _create_user(db_session, username=username, role=UserRole.ADMIN)
    return _auth(await _login(client, username))


async def _staff_auth(client, db_session, username: str = "staff") -> dict[str, str]:
    """创建普通职工并登录，返回认证头（用于权限校验）。"""
    await _create_user(db_session, username=username, role=UserRole.STAFF)
    return _auth(await _login(client, username))


async def _create_api_key(
    db_session: AsyncSession,
    name: str = "test-key",
    provider: str = "openai",
    usage: ApiKeyUsage = ApiKeyUsage.LLM,
    status: ApiKeyStatus = ApiKeyStatus.ACTIVE,
) -> ApiKey:
    """直接向测试库插入一条 API Key 元信息（不经 Vault/路由）。"""
    key = ApiKey(
        name=name,
        provider=provider,
        vault_path=f"api_keys/{uuid.uuid4()}",
        key_preview="sk**ab",
        usage=usage,
        status=status,
    )
    db_session.add(key)
    await db_session.commit()
    await db_session.refresh(key)
    return key


async def _create_model(
    db_session: AsyncSession,
    name: str = "test-model",
    provider: ModelProvider = ModelProvider.OPENAI,
    status: ModelStatus = ModelStatus.ACTIVE,
    api_key_id: str | None = None,
    model_type: str = "chat",
) -> ModelInstance:
    """直接向测试库插入一条模型实例。"""
    inst = ModelInstance(
        name=name,
        provider=provider,
        model_type=model_type,
        api_key_id=api_key_id,
        config={
            "model": "gpt-4o",
            "temperature": 0.7,
            "max_tokens": 2048,
            "timeout": 60,
        },
        status=status,
    )
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)
    return inst


def _mock_llm_chat(content: str = "mock回答") -> None:
    """配置 LLMManager.get_llm 返回假 LLM，其 chat 返回固定 LLMResponse。"""
    fake_llm = AsyncMock()
    fake_llm.chat.return_value = LLMResponse(
        content=content, prompt_tokens=5, completion_tokens=3
    )
    get_llm_manager().get_llm.return_value = fake_llm


@pytest.mark.integration
class TestModelAPI:
    """模型管理接口集成测试。"""

    # ========== API Key: 创建 ==========

    async def test_create_api_key_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/models/keys", json=_KEY_PAYLOAD, headers=headers
        )
        # Assert：明文 Key 仅创建时返回，预览为前后各 2 位
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"]
        assert body["name"] == "my-key"
        assert body["provider"] == "openai"
        assert body["api_key"] == "sk-testkey123456"
        assert body["key_preview"] == "sk**56"

    async def test_create_api_key_missing_fields_returns_422(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act：缺 name 与 api_key
        resp = await client.post(
            "/api/v1/models/keys", json={"provider": "openai"}, headers=headers
        )
        # Assert
        assert resp.status_code == 422

    async def test_create_api_key_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post("/api/v1/models/keys", json=_KEY_PAYLOAD)
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_create_api_key_staff_forbidden(self, client, db_session):
        # Arrange
        headers = await _staff_auth(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/models/keys", json=_KEY_PAYLOAD, headers=headers
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    # ========== API Key: 列表 ==========

    async def test_list_api_keys_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        await _create_api_key(db_session, name="k1")
        await _create_api_key(db_session, name="k2")
        # Act
        resp = await client.get("/api/v1/models/keys", headers=headers)
        # Assert：列表不含明文 Key
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        assert "api_key" not in items[0]

    async def test_list_api_keys_provider_filter(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        await _create_api_key(db_session, name="oai", provider="openai")
        await _create_api_key(db_session, name="ant", provider="anthropic")
        # Act
        resp = await client.get("/api/v1/models/keys?provider=openai", headers=headers)
        # Assert
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["provider"] == "openai"

    async def test_list_api_keys_pagination(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        for i in range(3):
            await _create_api_key(db_session, name=f"k{i}")
        # Act
        page1 = await client.get(
            "/api/v1/models/keys?page=1&page_size=2", headers=headers
        )
        page2 = await client.get(
            "/api/v1/models/keys?page=2&page_size=2", headers=headers
        )
        # Assert
        assert page1.status_code == 200
        assert len(page1.json()) == 2
        assert page2.status_code == 200
        assert len(page2.json()) == 1

    # ========== API Key: 详情 ==========

    async def test_get_api_key_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        key = await _create_api_key(db_session, name="detail-key")
        # Act
        resp = await client.get(f"/api/v1/models/keys/{key.id}", headers=headers)
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == key.id
        assert body["name"] == "detail-key"
        assert "api_key" not in body

    async def test_get_api_key_not_found(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.get("/api/v1/models/keys/nonexistent-id", headers=headers)
        # Assert
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    # ========== API Key: 更新 ==========

    async def test_update_api_key_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        key = await _create_api_key(db_session, name="old-name")
        # Act
        resp = await client.put(
            f"/api/v1/models/keys/{key.id}",
            json={"name": "new-name", "description": "updated"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "new-name"
        assert body["description"] == "updated"

    async def test_update_api_key_not_found(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/models/keys/nonexistent-id",
            json={"name": "x"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 404

    # ========== API Key: 删除 ==========

    async def test_delete_api_key_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        key = await _create_api_key(db_session, name="del-key")
        # Act
        resp = await client.delete(f"/api/v1/models/keys/{key.id}", headers=headers)
        # Assert：删除后再查应 404
        assert resp.status_code == 204
        follow = await client.get(f"/api/v1/models/keys/{key.id}", headers=headers)
        assert follow.status_code == 404

    async def test_delete_api_key_not_found(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.delete(
            "/api/v1/models/keys/nonexistent-id", headers=headers
        )
        # Assert
        assert resp.status_code == 404

    # ========== API Key: 轮换 ==========

    async def test_rotate_api_key_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        key = await _create_api_key(db_session, name="rot-key")
        # Act
        resp = await client.post(
            f"/api/v1/models/keys/{key.id}/rotate", headers=headers
        )
        # Assert：返回新明文 Key（sk- 前缀），预览已变更
        assert resp.status_code == 200
        body = resp.json()
        assert body["api_key"].startswith("sk-")
        assert body["key_preview"] != "sk**ab"

    async def test_rotate_api_key_not_found(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/models/keys/nonexistent-id/rotate", headers=headers
        )
        # Assert
        assert resp.status_code == 404

    # ========== Vault 健康检查 ==========

    async def test_vault_health_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        get_vault_client().health_check.return_value = {"status": "healthy"}
        # Act
        resp = await client.get("/api/v1/models/vault/health", headers=headers)
        # Assert
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    # ========== 模型实例: 创建 ==========

    async def test_create_model_instance_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.post("/api/v1/models", json=_MODEL_PAYLOAD, headers=headers)
        # Assert：默认启用
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"]
        assert body["name"] == "my-model"
        assert body["provider"] == "openai"
        assert body["status"] == "active"
        assert body["config"]["model"] == "gpt-4o"

    async def test_create_model_instance_with_api_key(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        key = await _create_api_key(db_session)
        payload = {**_MODEL_PAYLOAD, "api_key_id": key.id}
        # Act
        resp = await client.post("/api/v1/models", json=payload, headers=headers)
        # Assert
        assert resp.status_code == 201
        assert resp.json()["api_key_id"] == key.id

    async def test_create_model_instance_nonexistent_api_key_404(
        self, client, db_session
    ):
        # Arrange
        headers = await _admin_auth(client, db_session)
        payload = {**_MODEL_PAYLOAD, "api_key_id": "nonexistent-key-id"}
        # Act
        resp = await client.post("/api/v1/models", json=payload, headers=headers)
        # Assert
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    async def test_create_model_instance_missing_config_returns_422(
        self, client, db_session
    ):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act：缺必填 config
        resp = await client.post(
            "/api/v1/models",
            json={"name": "m", "provider": "openai"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    async def test_create_model_instance_staff_forbidden(self, client, db_session):
        # Arrange
        headers = await _staff_auth(client, db_session)
        # Act
        resp = await client.post("/api/v1/models", json=_MODEL_PAYLOAD, headers=headers)
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    # ========== 模型实例: 列表 ==========

    async def test_list_model_instances_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        await _create_model(db_session, name="m1")
        await _create_model(db_session, name="m2")
        # Act
        resp = await client.get("/api/v1/models", headers=headers)
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        assert body["page"] == 1
        assert body["page_size"] == 20

    async def test_list_model_instances_provider_filter(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        await _create_model(db_session, name="oai", provider=ModelProvider.OPENAI)
        await _create_model(db_session, name="qwen", provider=ModelProvider.QWEN)
        # Act
        resp = await client.get("/api/v1/models?provider=openai", headers=headers)
        # Assert
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["provider"] == "openai"

    # ========== 模型实例: 详情 ==========

    async def test_get_model_instance_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        model = await _create_model(db_session, name="detail-model")
        # Act
        resp = await client.get(f"/api/v1/models/{model.id}", headers=headers)
        # Assert
        assert resp.status_code == 200
        assert resp.json()["name"] == "detail-model"

    async def test_get_model_instance_not_found(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.get("/api/v1/models/nonexistent-id", headers=headers)
        # Assert
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    # ========== 模型实例: 更新 ==========

    async def test_update_model_instance_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        model = await _create_model(db_session, name="old-model")
        # Act
        resp = await client.put(
            f"/api/v1/models/{model.id}",
            json={"name": "new-model", "description": "upd"},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "new-model"
        assert body["description"] == "upd"

    async def test_update_model_instance_not_found(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.put(
            "/api/v1/models/nonexistent-id", json={"name": "x"}, headers=headers
        )
        # Assert
        assert resp.status_code == 404

    # ========== 模型实例: 状态切换 ==========

    async def test_toggle_active_to_inactive(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        model = await _create_model(db_session, name="tg", status=ModelStatus.ACTIVE)
        # Act
        resp = await client.post(f"/api/v1/models/{model.id}/toggle", headers=headers)
        # Assert
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    async def test_toggle_inactive_to_active(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        model = await _create_model(db_session, name="tg2", status=ModelStatus.INACTIVE)
        # Act
        resp = await client.post(f"/api/v1/models/{model.id}/toggle", headers=headers)
        # Assert
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_toggle_model_not_found(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.post(
            "/api/v1/models/nonexistent-id/toggle", headers=headers
        )
        # Assert
        assert resp.status_code == 404

    # ========== 模型实例: 删除 ==========

    async def test_delete_model_instance_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        model = await _create_model(db_session, name="del-model")
        # Act
        resp = await client.delete(f"/api/v1/models/{model.id}", headers=headers)
        # Assert：删除后再查应 404
        assert resp.status_code == 204
        follow = await client.get(f"/api/v1/models/{model.id}", headers=headers)
        assert follow.status_code == 404

    async def test_delete_model_instance_not_found(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act
        resp = await client.delete("/api/v1/models/nonexistent-id", headers=headers)
        # Assert
        assert resp.status_code == 404

    # ========== 模型实例: 对比 ==========

    async def test_compare_models_success(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        m1 = await _create_model(db_session, name="cmp1")
        m2 = await _create_model(db_session, name="cmp2")
        _mock_llm_chat("mock回答")
        # Act
        resp = await client.post(
            "/api/v1/models/compare",
            json={"question": "你好", "model_ids": [m1.id, m2.id]},
            headers=headers,
        )
        # Assert：两模型均成功，返回 mock 回答与 token 统计
        assert resp.status_code == 200
        body = resp.json()
        assert body["question"] == "你好"
        assert len(body["results"]) == 2
        for r in body["results"]:
            assert r["success"] is True
            assert r["response"] == "mock回答"
            assert r["input_tokens"] == 5
            assert r["output_tokens"] == 3

    async def test_compare_models_too_few_ids_returns_422(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        # Act：model_ids 少于 2 个
        resp = await client.post(
            "/api/v1/models/compare",
            json={"question": "hi", "model_ids": ["only-one"]},
            headers=headers,
        )
        # Assert
        assert resp.status_code == 422

    async def test_compare_models_with_nonexistent_model(self, client, db_session):
        # Arrange
        headers = await _admin_auth(client, db_session)
        existing = await _create_model(db_session, name="cmp-ok")
        _mock_llm_chat("ok")
        # Act：含一个不存在的模型 ID
        resp = await client.post(
            "/api/v1/models/compare",
            json={"question": "hi", "model_ids": [existing.id, "nonexistent-id"]},
            headers=headers,
        )
        # Assert：整体 200，存在的模型成功，不存在的失败并带 error
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 2
        ok = next(r for r in results if r["model_id"] == existing.id)
        bad = next(r for r in results if r["model_id"] == "nonexistent-id")
        assert ok["success"] is True
        assert bad["success"] is False
        assert bad["error"]
