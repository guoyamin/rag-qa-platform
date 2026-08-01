"""
智能问答平台 - 模型服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.llm.base import LLMConfig
from app.models.model_instance import ModelProvider as ModelProviderEnum
from app.models.model_instance import ModelStatus as ModelStatusEnum
from app.schemas.model import (
    ModelCompareRequest,
    ModelConfig,
    ModelInstanceCreate,
    ModelInstanceUpdate,
    ModelProvider,
    ModelStatus,
)
from app.services.model_service import ModelService


class TestModelConfig:
    """模型配置测试"""

    def test_model_config_creation(self):
        """测试模型配置创建"""
        from app.schemas.model import ModelConfig

        config = ModelConfig(
            model="gpt-4o",
            api_base="https://api.openai.com/v1",
            temperature=0.7,
            max_tokens=2048,
            top_p=0.9,
            timeout=60,
        )

        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_model_config_defaults(self):
        """测试模型配置默认值"""
        from app.schemas.model import ModelConfig

        config = ModelConfig(model="gpt-4o")

        assert config.temperature == 0.7
        assert config.max_tokens == 2048
        assert config.top_p is None
        assert config.timeout == 60

    def test_model_config_validation(self):
        """测试模型配置参数验证"""
        from pydantic import ValidationError

        from app.schemas.model import ModelConfig

        # temperature 超出范围
        with pytest.raises(ValidationError):
            ModelConfig(model="gpt-4o", temperature=3.0)

        # max_tokens 小于 1
        with pytest.raises(ValidationError):
            ModelConfig(model="gpt-4o", max_tokens=0)


class TestApiKeySchemas:
    """API Key Schema 测试"""

    def test_api_key_create(self):
        """测试 API Key 创建 Schema"""
        from app.schemas.model import ApiKeyCreate, KeyUsage

        data = ApiKeyCreate(
            name="Test Key",
            provider="openai",
            api_key="sk-test123",
            usage=KeyUsage.LLM,
        )

        assert data.name == "Test Key"
        assert data.provider == "openai"
        assert data.api_key == "sk-test123"
        assert data.usage == KeyUsage.LLM

    def test_api_key_update(self):
        """测试 API Key 更新 Schema"""
        from app.schemas.model import ApiKeyUpdate, KeyStatus

        data = ApiKeyUpdate(
            name="Updated Key",
            status=KeyStatus.INACTIVE,
        )

        assert data.name == "Updated Key"
        assert data.status == KeyStatus.INACTIVE

    def test_api_key_response(self):
        """测试 API Key 响应 Schema"""
        from datetime import datetime

        from app.schemas.model import ApiKeyResponse, KeyStatus, KeyUsage

        response = ApiKeyResponse(
            id="test-id",
            name="Test Key",
            provider="openai",
            usage=KeyUsage.LLM,
            status=KeyStatus.ACTIVE,
            key_preview="sk**st",
            expires_at=None,
            description="Test description",
            created_by="user-1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.id == "test-id"
        assert response.key_preview == "sk**st"


class TestLLMManager:
    """LLM 管理器测试"""

    @pytest.fixture
    async def llm_manager(self):
        """创建 LLM 管理器实例"""
        from app.services.llm_manager import LLMManager

        # 重置单例
        LLMManager._instance = None
        manager = LLMManager.get_instance()
        yield manager
        # 清理
        await manager.clear_cache()
        LLMManager._instance = None

    def test_singleton_pattern(self):
        """测试单例模式"""
        from app.services.llm_manager import LLMManager

        # 重置单例
        LLMManager._instance = None

        manager1 = LLMManager.get_instance()
        manager2 = LLMManager.get_instance()

        assert manager1 is manager2

        # 清理
        LLMManager._instance = None

    async def test_cache_operations(self, llm_manager):
        """测试缓存操作"""
        # 初始状态
        stats = llm_manager.get_cache_stats()
        assert stats["cached_models"] == 0

        # 清理缓存
        await llm_manager.clear_cache()
        stats = llm_manager.get_cache_stats()
        assert stats["cached_models"] == 0

    async def test_reload_llm(self, llm_manager):
        """测试重新加载 LLM"""
        # 移除不存在的模型不应报错
        await llm_manager.reload_llm("non-existent-id")

        # 移除已缓存的模型
        await llm_manager.remove_llm("non-existent-id")

    # ===== _load_config_from_db 单元测试 =====

    async def test_load_config_with_api_key_returns_full_config(
        self,
        llm_manager,
    ):
        """有 api_key_id 且 vault 返回密钥时应返回完整配置"""
        # Arrange
        instance = _make_instance(
            id="m-1",
            api_key_id="key-1",
            config={
                "model": "gpt-4o",
                "api_base": "https://api.openai.com/v1",
                "temperature": 0.5,
                "max_tokens": 1024,
                "top_p": 0.9,
                "timeout": 30,
            },
        )
        api_key_record = MagicMock()
        api_key_record.vault_path = "api_keys/openai"

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(instance),
                _make_execute_result(api_key_record),
            ]
        )
        mock_vault = MagicMock()
        mock_vault.read_secret.return_value = {"api_key": "sk-secret"}

        with (
            patch(
                "app.db.session.AsyncSessionLocal",
            ) as mock_sl,
            patch(
                "app.services.vault_client.get_vault_client",
                return_value=mock_vault,
            ),
        ):
            mock_sl.return_value.__aenter__.return_value = mock_db

            # Act
            result = await llm_manager._load_config_from_db("m-1")

        # Assert
        assert result is not None
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4o"
        assert result["api_key"] == "sk-secret"
        assert result["api_base"] == "https://api.openai.com/v1"
        assert result["temperature"] == 0.5
        assert result["max_tokens"] == 1024
        assert result["top_p"] == 0.9
        assert result["timeout"] == 30

    async def test_load_config_without_api_key_returns_none_key(
        self,
        llm_manager,
    ):
        """无 api_key_id 时应跳过密钥查询，api_key 为 None"""
        # Arrange
        instance = _make_instance(
            id="m-1",
            api_key_id=None,
            config={"model": "gpt-4o"},
        )
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[_make_execute_result(instance)],
        )

        with patch(
            "app.db.session.AsyncSessionLocal",
        ) as mock_sl:
            mock_sl.return_value.__aenter__.return_value = mock_db

            # Act
            result = await llm_manager._load_config_from_db("m-1")

        # Assert
        assert result is not None
        assert result["api_key"] is None
        assert mock_db.execute.await_count == 1

    async def test_load_config_model_not_found_returns_none(
        self,
        llm_manager,
    ):
        """模型不存在或非活跃时应返回 None"""
        # Arrange
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            return_value=_make_execute_result(None),
        )

        with patch(
            "app.db.session.AsyncSessionLocal",
        ) as mock_sl:
            mock_sl.return_value.__aenter__.return_value = mock_db

            # Act
            result = await llm_manager._load_config_from_db("missing")

        # Assert
        assert result is None
        assert mock_db.execute.await_count == 1

    async def test_load_config_api_key_record_missing_returns_none_key(
        self,
        llm_manager,
    ):
        """api_key_id 有值但记录不存在时 api_key 应为 None"""
        # Arrange
        instance = _make_instance(
            id="m-1",
            api_key_id="key-1",
            config={"model": "gpt-4o"},
        )
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(instance),
                _make_execute_result(None),
            ]
        )

        with (
            patch(
                "app.db.session.AsyncSessionLocal",
            ) as mock_sl,
            patch(
                "app.services.vault_client.get_vault_client",
            ) as mock_get_vault,
        ):
            mock_sl.return_value.__aenter__.return_value = mock_db

            # Act
            result = await llm_manager._load_config_from_db("m-1")

        # Assert
        assert result is not None
        assert result["api_key"] is None
        mock_get_vault.assert_not_called()

    async def test_load_config_vault_secret_none_returns_none_key(
        self,
        llm_manager,
    ):
        """vault 返回 None 时 api_key 应为 None"""
        # Arrange
        instance = _make_instance(
            id="m-1",
            api_key_id="key-1",
            config={"model": "gpt-4o"},
        )
        api_key_record = MagicMock()
        api_key_record.vault_path = "api_keys/openai"

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_execute_result(instance),
                _make_execute_result(api_key_record),
            ]
        )
        mock_vault = MagicMock()
        mock_vault.read_secret.return_value = None

        with (
            patch(
                "app.db.session.AsyncSessionLocal",
            ) as mock_sl,
            patch(
                "app.services.vault_client.get_vault_client",
                return_value=mock_vault,
            ),
        ):
            mock_sl.return_value.__aenter__.return_value = mock_db

            # Act
            result = await llm_manager._load_config_from_db("m-1")

        # Assert
        assert result is not None
        assert result["api_key"] is None

    async def test_load_config_missing_fields_uses_defaults(
        self,
        llm_manager,
    ):
        """config 字典缺少可选字段时应使用默认值"""
        # Arrange
        instance = _make_instance(
            id="m-1",
            api_key_id=None,
            config={"model": "gpt-4o"},
        )
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=[_make_execute_result(instance)],
        )

        with patch(
            "app.db.session.AsyncSessionLocal",
        ) as mock_sl:
            mock_sl.return_value.__aenter__.return_value = mock_db

            # Act
            result = await llm_manager._load_config_from_db("m-1")

        # Assert
        assert result is not None
        assert result["temperature"] == 0.7
        assert result["max_tokens"] == 2048
        assert result["top_p"] is None
        assert result["timeout"] == 60
        assert result["api_base"] is None

    # ===== get_llm 单元测试 =====

    async def test_get_llm_cache_hit_returns_cached_instance(
        self,
        llm_manager,
    ):
        """缓存命中时应直接返回已缓存实例，不访问数据库"""
        # Arrange
        mock_llm = MagicMock()
        llm_manager._llm_cache["m-1"] = mock_llm
        llm_manager._load_config_from_db = AsyncMock()

        # Act
        result = await llm_manager.get_llm("m-1")

        # Assert
        assert result is mock_llm
        llm_manager._load_config_from_db.assert_not_awaited()

    async def test_get_llm_cache_miss_creates_and_caches(
        self,
        llm_manager,
    ):
        """缓存未命中时应从数据库加载配置并创建 LLM 实例"""
        # Arrange
        config_dict = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "sk-xxx",
            "api_base": "https://api.openai.com/v1",
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": None,
            "timeout": 60,
        }
        mock_llm = MagicMock()
        llm_manager._load_config_from_db = AsyncMock(return_value=config_dict)

        with patch(
            "app.services.llm_manager.LLMFactory",
        ) as mock_factory:
            mock_factory.create.return_value = mock_llm

            # Act
            result = await llm_manager.get_llm("m-1")

        # Assert
        assert result is mock_llm
        mock_factory.create.assert_called_once()
        assert llm_manager._llm_cache["m-1"] is mock_llm
        assert llm_manager._config_cache["m-1"] == config_dict

    async def test_get_llm_unavailable_raises_service_unavailable(
        self,
        llm_manager,
    ):
        """数据库返回 None 时应抛出 ServiceUnavailableError"""
        # Arrange
        llm_manager._load_config_from_db = AsyncMock(return_value=None)

        # Act / Assert
        with pytest.raises(ServiceUnavailableError, match="不可用"):
            await llm_manager.get_llm("missing")

    async def test_get_llm_second_call_uses_cache_not_db(
        self,
        llm_manager,
    ):
        """第二次调用应命中缓存，不重复加载配置和创建实例"""
        # Arrange
        config_dict = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": None,
            "api_base": None,
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": None,
            "timeout": 60,
        }
        mock_llm = MagicMock()
        load_mock = AsyncMock(return_value=config_dict)
        llm_manager._load_config_from_db = load_mock

        with patch(
            "app.services.llm_manager.LLMFactory",
        ) as mock_factory:
            mock_factory.create.return_value = mock_llm

            # Act
            result1 = await llm_manager.get_llm("m-1")
            result2 = await llm_manager.get_llm("m-1")

        # Assert
        assert result1 is result2 is mock_llm
        load_mock.assert_awaited_once()
        mock_factory.create.assert_called_once()

    # ===== reload_llm / remove_llm / clear_cache / get_cache_stats =====

    async def test_reload_llm_removes_cached_instance(
        self,
        llm_manager,
    ):
        """刷新已缓存的模型应移除其缓存"""
        # Arrange
        llm_manager._llm_cache["m-1"] = MagicMock()
        llm_manager._config_cache["m-1"] = {"provider": "openai"}

        # Act
        await llm_manager.reload_llm("m-1")

        # Assert
        assert "m-1" not in llm_manager._llm_cache
        assert "m-1" not in llm_manager._config_cache

    async def test_remove_llm_removes_cached_instance(
        self,
        llm_manager,
    ):
        """移除已缓存的模型应清除其缓存"""
        # Arrange
        llm_manager._llm_cache["m-1"] = MagicMock()
        llm_manager._config_cache["m-1"] = {"provider": "openai"}

        # Act
        await llm_manager.remove_llm("m-1")

        # Assert
        assert "m-1" not in llm_manager._llm_cache
        assert "m-1" not in llm_manager._config_cache

    async def test_clear_cache_removes_all_cached(
        self,
        llm_manager,
    ):
        """清空缓存应移除所有已缓存模型"""
        # Arrange
        llm_manager._llm_cache["m-1"] = MagicMock()
        llm_manager._llm_cache["m-2"] = MagicMock()
        llm_manager._config_cache["m-1"] = {}
        llm_manager._config_cache["m-2"] = {}

        # Act
        await llm_manager.clear_cache()

        # Assert
        assert len(llm_manager._llm_cache) == 0
        assert len(llm_manager._config_cache) == 0

    def test_get_cache_stats_reports_cached_count_and_ids(
        self,
        llm_manager,
    ):
        """缓存统计应正确反映已缓存模型数量和 ID 列表"""
        # Arrange
        llm_manager._llm_cache["m-1"] = MagicMock()
        llm_manager._llm_cache["m-2"] = MagicMock()

        # Act
        stats = llm_manager.get_cache_stats()

        # Assert
        assert stats["cached_models"] == 2
        assert set(stats["model_ids"]) == {"m-1", "m-2"}

    # ===== preload_models 单元测试 =====

    async def test_preload_models_all_succeed_returns_count(
        self,
        llm_manager,
    ):
        """所有模型预加载成功时应返回成功数量"""
        # Arrange
        mock_llm = MagicMock()
        llm_manager.get_llm = AsyncMock(return_value=mock_llm)

        # Act
        result = await llm_manager.preload_models(["m-1", "m-2", "m-3"])

        # Assert
        assert result == 3
        assert llm_manager.get_llm.await_count == 3

    async def test_preload_models_partial_failure_returns_partial_count(
        self,
        llm_manager,
    ):
        """部分模型加载失败时应返回成功数量，不抛异常"""
        # Arrange
        mock_llm = MagicMock()
        llm_manager.get_llm = AsyncMock(
            side_effect=[mock_llm, RuntimeError("timeout"), mock_llm],
        )

        # Act
        result = await llm_manager.preload_models(["m-1", "m-2", "m-3"])

        # Assert
        assert result == 2

    async def test_preload_models_empty_list_returns_zero(
        self,
        llm_manager,
    ):
        """空模型列表应返回 0"""
        # Arrange
        llm_manager.get_llm = AsyncMock()

        # Act
        result = await llm_manager.preload_models([])

        # Assert
        assert result == 0
        llm_manager.get_llm.assert_not_awaited()

    async def test_preload_models_all_fail_returns_zero(
        self,
        llm_manager,
    ):
        """所有模型加载失败时应返回 0，不抛异常"""
        # Arrange
        llm_manager.get_llm = AsyncMock(
            side_effect=ServiceUnavailableError("不可用"),
        )

        # Act
        result = await llm_manager.preload_models(["m-1", "m-2"])

        # Assert
        assert result == 0

    # ===== update_config 单元测试 =====

    async def test_update_config_creates_and_caches_llm(
        self,
        llm_manager,
    ):
        """直接更新配置应创建 LLM 实例并写入缓存"""
        # Arrange
        mock_llm = MagicMock()
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="sk-xxx",
        )

        with patch(
            "app.services.llm_manager.LLMFactory",
        ) as mock_factory:
            mock_factory.create.return_value = mock_llm

            # Act
            await llm_manager.update_config("m-1", config)

        # Assert
        mock_factory.create.assert_called_once_with(config)
        assert llm_manager._llm_cache["m-1"] is mock_llm
        assert llm_manager._config_cache["m-1"] == config.model_dump()

    async def test_update_config_overwrites_existing_cached(
        self,
        llm_manager,
    ):
        """更新已缓存的模型应覆盖旧实例"""
        # Arrange
        old_llm = MagicMock()
        llm_manager._llm_cache["m-1"] = old_llm
        new_llm = MagicMock()
        config = LLMConfig(provider="qwen", model="qwen-max")

        with patch(
            "app.services.llm_manager.LLMFactory",
        ) as mock_factory:
            mock_factory.create.return_value = new_llm

            # Act
            await llm_manager.update_config("m-1", config)

        # Assert
        assert llm_manager._llm_cache["m-1"] is new_llm
        assert llm_manager._llm_cache["m-1"] is not old_llm

    # ===== get_llm_manager 便捷函数 =====

    def test_get_llm_manager_returns_singleton(self):
        """get_llm_manager 应返回与 get_instance 相同的单例"""
        # Arrange
        from app.services.llm_manager import LLMManager, get_llm_manager

        LLMManager._instance = None

        # Act
        manager = get_llm_manager()

        # Assert
        assert manager is LLMManager.get_instance()

        # Cleanup
        LLMManager._instance = None


class TestModelProviderEnum:
    """模型提供商枚举测试"""

    def test_provider_values(self):
        """测试提供商枚举值"""
        from app.schemas.model import ModelProvider

        assert ModelProvider.OPENAI.value == "openai"
        assert ModelProvider.ANTHROPIC.value == "anthropic"
        assert ModelProvider.QWEN.value == "qwen"
        assert ModelProvider.LOCAL.value == "local"

    def test_status_values(self):
        """测试状态枚举值"""
        from app.schemas.model import ModelStatus

        assert ModelStatus.ACTIVE.value == "active"
        assert ModelStatus.INACTIVE.value == "inactive"
        assert ModelStatus.MAINTENANCE.value == "maintenance"


# ========== Service 层单元测试 ==========


def _make_mock_db() -> MagicMock:
    """Create a mock AsyncSession with async methods configured."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.delete = AsyncMock()
    return db


def _make_execute_result(scalar_value):
    """Create a mock for db.execute() result with scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_value
    return result


def _make_instance(**kwargs) -> MagicMock:
    """Create a mock ModelInstance with sensible defaults."""
    inst = MagicMock()
    inst.id = kwargs.get("id", "model-1")
    inst.name = kwargs.get("name", "test-model")
    inst.provider = kwargs.get("provider", ModelProviderEnum.OPENAI)
    inst.model_type = kwargs.get("model_type", "chat")
    inst.api_key_id = kwargs.get("api_key_id")
    inst.config = kwargs.get("config", {"model": "gpt-4o"})
    inst.status = kwargs.get("status", ModelStatusEnum.ACTIVE)
    inst.description = kwargs.get("description")
    inst.created_by = kwargs.get("created_by")
    inst.embedding_dimension = kwargs.get("embedding_dimension")
    inst.created_at = kwargs.get("created_at", datetime.now())
    inst.updated_at = kwargs.get("updated_at", datetime.now())
    return inst


def _make_create_data(**kwargs) -> ModelInstanceCreate:
    """Create a ModelInstanceCreate schema with defaults."""
    return ModelInstanceCreate(
        name=kwargs.get("name", "test-model"),
        provider=kwargs.get("provider", ModelProvider.OPENAI),
        api_key_id=kwargs.get("api_key_id"),
        model_type=kwargs.get("model_type", "chat"),
        config=kwargs.get("config", ModelConfig(model="gpt-4o")),
        description=kwargs.get("description"),
    )


@pytest.fixture
def service_factory():
    """Return a factory that creates a ModelService with mocked deps.

    Usage::

        svc, mock_api, mock_llm = service_factory(mock_db)
    """

    def _factory(db: MagicMock):
        with (
            patch("app.services.model_service.ApiKeyService") as mock_api_cls,
            patch("app.services.model_service.LLMManager") as mock_llm_cls,
        ):
            mock_api = AsyncMock()
            mock_api_cls.return_value = mock_api
            mock_llm = AsyncMock()
            mock_llm_cls.get_instance.return_value = mock_llm
            svc = ModelService(db)
            return svc, mock_api, mock_llm

    return _factory


class TestModelServiceCreate:
    """ModelService.create 单元测试"""

    async def test_create_with_api_key_returns_instance(self, service_factory):
        """有 api_key_id 时应验证 key 并创建实例"""
        # Arrange
        db = _make_mock_db()
        data = _make_create_data(api_key_id="key-1")

        async def _refresh(obj, *a, **kw):
            obj.id = "new-id"

        db.refresh.side_effect = _refresh

        # Act
        svc, mock_api, mock_llm = service_factory(db)
        result = await svc.create(data, user_id="user-1")

        # Assert
        mock_api.get.assert_awaited_once_with("key-1")
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        assert mock_llm.get_llm.await_count == 1
        assert result.name == "test-model"
        assert result.status == ModelStatusEnum.ACTIVE

    async def test_create_without_api_key_skips_validation(self, service_factory):
        """无 api_key_id 时不应调用 api_key_service.get"""
        # Arrange
        db = _make_mock_db()
        data = _make_create_data(api_key_id=None)

        async def _refresh(obj, *a, **kw):
            obj.id = "new-id"

        db.refresh.side_effect = _refresh

        # Act
        svc, mock_api, mock_llm = service_factory(db)
        await svc.create(data)

        # Assert
        mock_api.get.assert_not_awaited()

    async def test_create_embedding_sets_dimension_default(self, service_factory):
        """embedding 类型无 extra 时应使用默认维度 1536"""
        # Arrange
        db = _make_mock_db()
        data = _make_create_data(model_type="embedding")

        async def _refresh(obj, *a, **kw):
            obj.id = "new-id"

        db.refresh.side_effect = _refresh

        # Act
        svc, mock_api, mock_llm = service_factory(db)
        result = await svc.create(data)

        # Assert
        assert result.embedding_dimension == 1536

    async def test_create_api_key_not_found_raises(self, service_factory):
        """api_key_service.get 抛 NotFoundError 时应向上传播"""
        # Arrange
        db = _make_mock_db()
        data = _make_create_data(api_key_id="missing-key")

        # Act
        svc, mock_api, mock_llm = service_factory(db)
        mock_api.get.side_effect = NotFoundError("API Key 不存在")

        # Assert
        with pytest.raises(NotFoundError):
            await svc.create(data)


class TestModelServiceGet:
    """ModelService.get 单元测试"""

    async def test_get_found_returns_instance(self, service_factory):
        """存在的模型 ID 应返回实例"""
        # Arrange
        db = _make_mock_db()
        expected = _make_instance(id="m-1", name="my-model")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected
        db.execute.return_value = mock_result

        # Act
        svc, _, _ = service_factory(db)
        result = await svc.get("m-1")

        # Assert
        assert result is expected

    async def test_get_not_found_raises_error(self, service_factory):
        """不存在的模型 ID 应抛出 NotFoundError"""
        # Arrange
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        # Act / Assert
        svc, _, _ = service_factory(db)
        with pytest.raises(NotFoundError, match="模型实例不存在"):
            await svc.get("missing-id")


class TestModelServiceList:
    """ModelService.list 单元测试"""

    async def test_list_no_filters_returns_items_and_total(self, service_factory):
        """无筛选条件应返回分页结果和总数"""
        # Arrange
        db = _make_mock_db()
        inst1 = _make_instance(id="m-1")
        inst2 = _make_instance(id="m-2")
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [inst1, inst2]
        db.execute.side_effect = [count_result, list_result]

        # Act
        svc, _, _ = service_factory(db)
        items, total = await svc.list(page=1, page_size=10)

        # Assert
        assert len(items) == 2
        assert total == 2

    async def test_list_empty_returns_empty_list(self, service_factory):
        """空结果应返回空列表和总数 0"""
        # Arrange
        db = _make_mock_db()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []
        db.execute.side_effect = [count_result, list_result]

        # Act
        svc, _, _ = service_factory(db)
        items, total = await svc.list()

        # Assert
        assert items == []
        assert total == 0

    async def test_list_with_filters_calls_execute_twice(self, service_factory):
        """带筛选条件应正常执行查询"""
        # Arrange
        db = _make_mock_db()
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [_make_instance(id="m-1")]
        db.execute.side_effect = [count_result, list_result]

        # Act
        svc, _, _ = service_factory(db)
        items, total = await svc.list(
            provider="openai", model_type="chat", status="active"
        )

        # Assert
        assert total == 1
        assert len(items) == 1


class TestModelServiceUpdate:
    """ModelService.update 单元测试"""

    async def test_update_name_changes_name(self, service_factory):
        """更新 name 字段应修改实例名称"""
        # Arrange
        db = _make_mock_db()
        instance = _make_instance(id="m-1", name="old-name")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        db.execute.return_value = mock_result
        data = ModelInstanceUpdate(name="new-name")

        # Act
        svc, _, _ = service_factory(db)
        result = await svc.update("m-1", data)

        # Assert
        assert result.name == "new-name"
        db.commit.assert_awaited_once()

    async def test_update_status_sets_new_status(self, service_factory):
        """更新 status 应修改实例状态"""
        # Arrange
        db = _make_mock_db()
        instance = _make_instance(id="m-1", status=ModelStatusEnum.ACTIVE)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        db.execute.return_value = mock_result
        data = ModelInstanceUpdate(status=ModelStatus.MAINTENANCE)

        # Act
        svc, _, _ = service_factory(db)
        result = await svc.update("m-1", data)

        # Assert
        assert result.status == ModelStatusEnum.MAINTENANCE

    async def test_update_api_key_id_validates_new_key(self, service_factory):
        """更新 api_key_id 为新值时应验证 key 存在"""
        # Arrange
        db = _make_mock_db()
        instance = _make_instance(id="m-1", api_key_id=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        db.execute.return_value = mock_result
        data = ModelInstanceUpdate(api_key_id="new-key")

        # Act
        svc, mock_api, _ = service_factory(db)
        await svc.update("m-1", data)

        # Assert
        mock_api.get.assert_awaited_once_with("new-key")

    async def test_update_api_key_id_to_none_clears_key(self, service_factory):
        """更新 api_key_id 为空字符串时不应验证 key 但应清空关联"""
        # Arrange
        db = _make_mock_db()
        instance = _make_instance(id="m-1", api_key_id="old-key")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        db.execute.return_value = mock_result
        data = ModelInstanceUpdate(api_key_id="")

        # Act
        svc, mock_api, _ = service_factory(db)
        result = await svc.update("m-1", data)

        # Assert
        mock_api.get.assert_not_awaited()
        assert result.api_key_id == ""

    async def test_update_not_found_raises(self, service_factory):
        """更新不存在的模型应抛出 NotFoundError"""
        # Arrange
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        data = ModelInstanceUpdate(name="x")

        # Act / Assert
        svc, _, _ = service_factory(db)
        with pytest.raises(NotFoundError):
            await svc.update("missing", data)

    async def test_update_reload_llm_called(self, service_factory):
        """更新后应刷新 LLM 缓存"""
        # Arrange
        db = _make_mock_db()
        instance = _make_instance(id="m-1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        db.execute.return_value = mock_result
        data = ModelInstanceUpdate(name="new")

        # Act
        svc, _, mock_llm = service_factory(db)
        await svc.update("m-1", data)

        # Assert
        mock_llm.reload_llm.assert_awaited_once_with("m-1")


class TestModelServiceToggleStatus:
    """ModelService.toggle_status 单元测试"""

    async def test_toggle_active_to_inactive(self, service_factory):
        """活跃模型切换后应变为禁用"""
        # Arrange
        db = _make_mock_db()
        instance = _make_instance(id="m-1", status=ModelStatusEnum.ACTIVE)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        db.execute.return_value = mock_result

        # Act
        svc, _, _ = service_factory(db)
        result = await svc.toggle_status("m-1")

        # Assert
        assert result.status == ModelStatusEnum.INACTIVE

    async def test_toggle_inactive_to_active(self, service_factory):
        """禁用模型切换后应变为活跃"""
        # Arrange
        db = _make_mock_db()
        instance = _make_instance(id="m-1", status=ModelStatusEnum.INACTIVE)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        db.execute.return_value = mock_result

        # Act
        svc, _, _ = service_factory(db)
        result = await svc.toggle_status("m-1")

        # Assert
        assert result.status == ModelStatusEnum.ACTIVE

    async def test_toggle_not_found_raises(self, service_factory):
        """切换不存在的模型应抛出 NotFoundError"""
        # Arrange
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        # Act / Assert
        svc, _, _ = service_factory(db)
        with pytest.raises(NotFoundError):
            await svc.toggle_status("missing")


class TestModelServiceDelete:
    """ModelService.delete 单元测试"""

    async def test_delete_existing_removes_instance(self, service_factory):
        """删除存在的模型应调用 db.delete 和 commit"""
        # Arrange
        db = _make_mock_db()
        instance = _make_instance(id="m-1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        db.execute.return_value = mock_result

        # Act
        svc, _, mock_llm = service_factory(db)
        await svc.delete("m-1")

        # Assert
        mock_llm.remove_llm.assert_awaited_once_with("m-1")
        db.delete.assert_awaited_once_with(instance)
        db.commit.assert_awaited_once()

    async def test_delete_not_found_raises(self, service_factory):
        """删除不存在的模型应抛出 NotFoundError"""
        # Arrange
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        # Act / Assert
        svc, _, _ = service_factory(db)
        with pytest.raises(NotFoundError):
            await svc.delete("missing")


class TestModelServiceCompareModels:
    """ModelService.compare_models 单元测试"""

    async def test_compare_all_succeed_returns_response(self, service_factory):
        """所有模型调用成功应返回成功结果"""
        # Arrange
        db = _make_mock_db()
        inst1 = _make_instance(id="m-1", name="model-a")
        inst2 = _make_instance(id="m-2", name="model-b")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [inst1, inst2]
        db.execute.return_value = mock_result

        llm_mock = AsyncMock()
        llm_mock.chat.return_value = MagicMock(
            content="answer",
            prompt_tokens=10,
            completion_tokens=20,
        )

        data = ModelCompareRequest(question="hello", model_ids=["m-1", "m-2"])

        # Act
        svc, _, mock_llm = service_factory(db)
        mock_llm.get_llm.return_value = llm_mock
        result = await svc.compare_models(data)

        # Assert
        assert len(result.results) == 2
        assert all(r.success for r in result.results)
        assert result.results[0].model_name == "model-a"
        assert result.results[0].response == "answer"
        assert result.results[0].input_tokens == 10
        assert result.results[0].output_tokens == 20

    async def test_compare_model_not_found_records_error(self, service_factory):
        """模型不存在时该模型结果应为失败并记录错误"""
        # Arrange
        db = _make_mock_db()
        inst1 = _make_instance(id="m-1", name="model-a")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [
            inst1,
            None,
        ]
        db.execute.return_value = mock_result

        llm_mock = AsyncMock()
        llm_mock.chat.return_value = MagicMock(
            content="answer", prompt_tokens=5, completion_tokens=5
        )

        data = ModelCompareRequest(question="hello", model_ids=["m-1", "missing"])

        # Act
        svc, _, mock_llm = service_factory(db)
        mock_llm.get_llm.return_value = llm_mock
        result = await svc.compare_models(data)

        # Assert
        assert result.results[0].success is True
        assert result.results[1].success is False
        assert result.results[1].error is not None

    async def test_compare_llm_failure_records_error(self, service_factory):
        """LLM 调用失败时该模型结果应为失败"""
        # Arrange
        db = _make_mock_db()
        inst = _make_instance(id="m-1", name="model-a")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inst
        db.execute.return_value = mock_result

        data = ModelCompareRequest(question="hello", model_ids=["m-1", "m-2"])
        inst2 = _make_instance(id="m-2", name="model-b")
        mock_result.scalar_one_or_none.side_effect = [inst, inst2]

        llm_ok = AsyncMock()
        llm_ok.chat.return_value = MagicMock(
            content="ok", prompt_tokens=1, completion_tokens=1
        )
        llm_fail = AsyncMock()
        llm_fail.chat.side_effect = RuntimeError("timeout")

        # Act
        svc, _, mock_llm = service_factory(db)
        mock_llm.get_llm.side_effect = [llm_ok, llm_fail]
        result = await svc.compare_models(data)

        # Assert
        assert result.results[0].success is True
        assert result.results[1].success is False
        assert "timeout" in result.results[1].error


class TestModelServiceGetActiveModels:
    """ModelService.get_active_models 单元测试"""

    async def test_get_active_returns_matching_models(self, service_factory):
        """应返回所有活跃模型"""
        # Arrange
        db = _make_mock_db()
        inst1 = _make_instance(id="m-1", status=ModelStatusEnum.ACTIVE)
        inst2 = _make_instance(id="m-2", status=ModelStatusEnum.ACTIVE)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [inst1, inst2]
        db.execute.return_value = mock_result

        # Act
        svc, _, _ = service_factory(db)
        result = await svc.get_active_models("chat")

        # Assert
        assert len(result) == 2

    async def test_get_active_empty_returns_empty_list(self, service_factory):
        """无活跃模型时应返回空列表"""
        # Arrange
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        # Act
        svc, _, _ = service_factory(db)
        result = await svc.get_active_models()

        # Assert
        assert result == []
