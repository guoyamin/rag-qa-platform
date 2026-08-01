"""
智能问答平台 - Vault 客户端单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.model import ApiKeyCreate, ApiKeyUpdate, KeyStatus, KeyUsage
from app.services.api_key_service import ApiKeyService
from app.services.vault_client import (
    VaultClient,
    VaultConfig,
    get_vault_client,
    init_vault_client,
)


class TestVaultClient:
    """Vault 客户端测试"""

    @pytest.fixture
    def vault_client(self):
        """创建 Vault 客户端（Mock）"""
        with patch("app.services.vault_client.hvac") as mock_hvac:
            mock_client = MagicMock()
            mock_hvac.Client.return_value = mock_client

            client = VaultClient(
                url="http://localhost:8200",
                role_id=None,
                secret_id=None,
                mount_point="secret",
                kv_version=2,
            )
            client._client = mock_client
            return client

    # === Schema / 配置测试（已有，保留） ===

    def test_generate_key_preview(self):
        """测试 Key 预览生成"""
        from app.services.api_key_service import ApiKeyService

        # 正常长度
        assert ApiKeyService._generate_key_preview("sk-1234567890abcdef") == "sk**ef"

        # 短 Key
        assert ApiKeyService._generate_key_preview("abc") == "ab**"

        # 最小长度
        assert ApiKeyService._generate_key_preview("ab") == "ab**"

    def test_generate_vault_path(self):
        """测试 Vault 路径生成"""
        from app.services.api_key_service import ApiKeyService

        assert ApiKeyService._generate_vault_path("abc-123") == "api_keys/abc-123"

    def test_vault_config(self):
        """测试 Vault 配置"""
        from app.services.vault_client import VaultConfig

        config = VaultConfig(
            url="http://vault:8200",
            role_id="role-123",
            secret_id="secret-456",
            mount_point="secret",
            kv_version=2,
        )

        assert config.url == "http://vault:8200"
        assert config.role_id == "role-123"
        assert config.secret_id == "secret-456"
        assert config.mount_point == "secret"
        assert config.kv_version == 2

    # === VaultClient 初始化测试 ===

    def test_init_with_explicit_params_uses_given_values(self):
        """测试 __init__ 显式传参 使用传入值"""
        client = VaultClient(
            url="http://custom:8200",
            role_id="role-x",
            secret_id="secret-x",
            mount_point="kv",
            kv_version=1,
        )

        assert client.url == "http://custom:8200"
        assert client.role_id == "role-x"
        assert client.secret_id == "secret-x"
        assert client.mount_point == "kv"
        assert client.kv_version == 1
        assert client._client is None

    def test_init_defaults_kv_version_is_two(self):
        """测试 __init__ 默认参数 kv_version为2"""
        with patch.dict("os.environ", {"VAULT_ADDR": "http://env:8200"}, clear=False):
            client = VaultClient()

            assert client.url == "http://env:8200"
            assert client.kv_version == 2
            assert client.mount_point == "secret"

    # === client 属性测试 ===

    def test_client_property_lazy_init_creates_hvac_client(self):
        """测试 client属性 延迟初始化 创建hvac客户端"""
        with patch("app.services.vault_client.hvac") as mock_hvac:
            mock_client = MagicMock()
            mock_hvac.Client.return_value = mock_client

            client = VaultClient(url="http://test:8200", role_id=None, secret_id=None)
            assert client._client is None

            result = client.client

            assert result is mock_client
            mock_hvac.Client.assert_called_once_with(url="http://test:8200")

    def test_client_property_returns_existing_client(self):
        """测试 client属性 已有客户端 返回同一实例"""
        client = VaultClient(url="http://test:8200")
        mock_client = MagicMock()
        client._client = mock_client

        result = client.client

        assert result is mock_client

    # === _authenticate 测试 ===

    def test_authenticate_approle_calls_auth_approle(self):
        """测试 _authenticate AppRole凭证 调用_auth_approle"""
        client = VaultClient(url="http://test:8200", role_id="r", secret_id="s")
        client._client = MagicMock()

        with patch.object(client, "_auth_approle") as mock_auth:
            client._authenticate()
            mock_auth.assert_called_once()

    def test_authenticate_token_env_sets_client_token(self):
        """测试 _authenticate VAULT_TOKEN环境变量 设置客户端token"""
        env = {"VAULT_TOKEN": "tok-123", "VAULT_ROLE_ID": "", "VAULT_SECRET_ID": ""}
        with patch.dict("os.environ", env):
            client = VaultClient(url="http://test:8200", role_id=None, secret_id=None)
            mock_client = MagicMock()
            client._client = mock_client

            client._authenticate()

            assert mock_client.token == "tok-123"

    def test_authenticate_no_auth_does_not_set_token(self):
        """测试 _authenticate 无认证 不设置token"""
        env = {"VAULT_TOKEN": "", "VAULT_ROLE_ID": "", "VAULT_SECRET_ID": ""}
        with patch.dict("os.environ", env):
            client = VaultClient(url="http://test:8200", role_id=None, secret_id=None)
            mock_client = MagicMock()
            client._client = mock_client

            client._authenticate()

            mock_client.approle_login.assert_not_called()

    # === _auth_approle 测试 ===

    def test_auth_approle_success_calls_approle_login(self):
        """测试 _auth_approle 凭证完整 调用approle_login"""
        client = VaultClient(url="http://test:8200", role_id="r", secret_id="s")
        mock_client = MagicMock()
        client._client = mock_client

        client._auth_approle()

        mock_client.approle_login.assert_called_once_with(role_id="r", secret_id="s")

    def test_auth_approle_missing_credentials_raises_validation_error(self):
        """测试 _auth_approle 缺少凭证 抛出ValidationError"""
        client = VaultClient(url="http://test:8200", role_id=None, secret_id=None)

        with pytest.raises(ValidationError, match="role_id 和 secret_id"):
            client._auth_approle()

    def test_auth_approle_failure_reraises(self):
        """测试 _auth_approle 认证异常 重新抛出"""
        client = VaultClient(url="http://test:8200", role_id="r", secret_id="s")
        mock_client = MagicMock()
        mock_client.approle_login.side_effect = RuntimeError("auth failed")
        client._client = mock_client

        with pytest.raises(RuntimeError, match="auth failed"):
            client._auth_approle()

    # === is_authenticated 测试 ===

    def test_is_authenticated_no_client_returns_false(self):
        """测试 is_authenticated 无客户端 返回False"""
        client = VaultClient(url="http://test:8200")
        assert client._client is None
        assert client.is_authenticated() is False

    def test_is_authenticated_client_returns_true(self):
        """测试 is_authenticated 客户端已认证 返回True"""
        client = VaultClient(url="http://test:8200")
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        client._client = mock_client

        assert client.is_authenticated() is True

    def test_is_authenticated_client_raises_returns_false(self):
        """测试 is_authenticated 客户端异常 返回False"""
        client = VaultClient(url="http://test:8200")
        mock_client = MagicMock()
        mock_client.is_authenticated.side_effect = RuntimeError("network error")
        client._client = mock_client

        assert client.is_authenticated() is False

    # === write_secret 测试 ===

    def test_write_secret_v2_simple_path_adds_data_prefix(self, vault_client):
        """测试 write_secret KVv2简单路径 添加data前缀"""
        mock_v2 = vault_client.client.secrets.kv.v2
        mock_v2.create_or_update_secret.return_value = {"version": 1}

        result = vault_client.write_secret("api_keys/test", {"key": "val"})

        assert result == {"version": 1}
        mock_v2.create_or_update_secret.assert_called_once_with(
            path="data/api_keys/test",
            secret={"key": "val"},
            mount_point="secret",
            metadata=None,
        )

    def test_write_secret_v2_data_prefix_not_duplicated(self, vault_client):
        """测试 write_secret KVv2已有data前缀 不重复添加"""
        mock_v2 = vault_client.client.secrets.kv.v2
        mock_v2.create_or_update_secret.return_value = {"version": 1}

        vault_client.write_secret("data/api_keys/test", {"key": "val"})

        mock_v2.create_or_update_secret.assert_called_once_with(
            path="data/api_keys/test",
            secret={"key": "val"},
            mount_point="secret",
            metadata=None,
        )

    def test_write_secret_v1_no_prefix(self):
        """测试 write_secret KVv1 不添加data前缀"""
        with patch("app.services.vault_client.hvac"):
            client = VaultClient(url="http://test:8200", kv_version=1)
            client._client = MagicMock()
            mock_v1 = client.client.secrets.kv.v1
            mock_v1.create_or_update_secret.return_value = {"ok": True}

            result = client.write_secret("api_keys/test", {"key": "val"})

            assert result == {"ok": True}
            mock_v1.create_or_update_secret.assert_called_once_with(
                path="api_keys/test",
                secret={"key": "val"},
                mount_point="secret",
            )

    def test_write_secret_exception_reraises(self, vault_client):
        """测试 write_secret Vault异常 重新抛出"""
        vault_client.client.secrets.kv.v2.create_or_update_secret.side_effect = (
            RuntimeError("write failed")
        )

        with pytest.raises(RuntimeError, match="write failed"):
            vault_client.write_secret("api_keys/test", {"key": "val"})

    # === read_secret 测试 ===

    def test_read_secret_v2_returns_nested_data(self, vault_client):
        """测试 read_secret KVv2嵌套data 返回内层data"""
        vault_client.client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"api_key": "sk-xxx"}, "metadata": {}}
        }

        result = vault_client.read_secret("api_keys/test")

        assert result == {"api_key": "sk-xxx"}

    def test_read_secret_v2_with_data_prefix_not_duplicated(self, vault_client):
        """测试 read_secret KVv2已有data前缀 不重复添加"""
        vault_client.client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"api_key": "sk-xxx"}}
        }

        vault_client.read_secret("data/api_keys/test")

        vault_client.client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="data/api_keys/test",
            mount_point="secret",
            version=None,
        )

    def test_read_secret_v1_returns_data(self):
        """测试 read_secret KVv1 返回data"""
        with patch("app.services.vault_client.hvac"):
            client = VaultClient(url="http://test:8200", kv_version=1)
            client._client = MagicMock()
            client.client.secrets.kv.v1.read_secret.return_value = {
                "data": {"api_key": "sk-yyy"}
            }

            result = client.read_secret("api_keys/test")

            assert result == {"api_key": "sk-yyy"}

    def test_read_secret_exception_returns_none(self, vault_client):
        """测试 read_secret Vault异常 返回None"""
        vault_client.client.secrets.kv.v2.read_secret_version.side_effect = (
            RuntimeError("read failed")
        )

        result = vault_client.read_secret("api_keys/test")

        assert result is None

    # === delete_secret 测试 ===

    def test_delete_secret_v2_adds_data_prefix(self, vault_client):
        """测试 delete_secret KVv2 添加data前缀"""
        vault_client.client.secrets.kv.v2.delete_metadata_and_all_versions.return_value = {
            "deleted": True
        }

        result = vault_client.delete_secret("api_keys/test")

        assert result == {"deleted": True}

    def test_delete_secret_v1_no_prefix(self):
        """测试 delete_secret KVv1 不添加前缀"""
        with patch("app.services.vault_client.hvac"):
            client = VaultClient(url="http://test:8200", kv_version=1)
            client._client = MagicMock()
            client.client.secrets.kv.v1.delete_secret.return_value = {"ok": True}

            result = client.delete_secret("api_keys/test")

            assert result == {"ok": True}
            client.client.secrets.kv.v1.delete_secret.assert_called_once_with(
                path="api_keys/test",
                mount_point="secret",
            )

    def test_delete_secret_exception_reraises(self, vault_client):
        """测试 delete_secret Vault异常 重新抛出"""
        vault_client.client.secrets.kv.v2.delete_metadata_and_all_versions.side_effect = RuntimeError(
            "delete failed"
        )

        with pytest.raises(RuntimeError, match="delete failed"):
            vault_client.delete_secret("api_keys/test")

    # === list_secrets 测试 ===

    def test_list_secrets_v2_adds_metadata_prefix(self, vault_client):
        """测试 list_secrets KVv2 添加metadata前缀"""
        vault_client.client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": ["key1", "key2/", "key3"]}
        }

        result = vault_client.list_secrets("api_keys")

        assert result == ["key1", "key2", "key3"]

    def test_list_secrets_v2_empty_path_uses_metadata(self, vault_client):
        """测试 list_secrets KVv2空路径 使用metadata"""
        vault_client.client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": []}
        }

        vault_client.list_secrets()

        vault_client.client.secrets.kv.v2.list_secrets.assert_called_once_with(
            path="metadata",
            mount_point="secret",
        )

    def test_list_secrets_v1_no_prefix(self):
        """测试 list_secrets KVv1 不添加前缀"""
        with patch("app.services.vault_client.hvac"):
            client = VaultClient(url="http://test:8200", kv_version=1)
            client._client = MagicMock()
            client.client.secrets.kv.v1.list_secrets.return_value = {
                "data": {"keys": ["a", "b"]}
            }

            result = client.list_secrets("api_keys")

            assert result == ["a", "b"]

    def test_list_secrets_exception_returns_empty(self, vault_client):
        """测试 list_secrets Vault异常 返回空列表"""
        vault_client.client.secrets.kv.v2.list_secrets.side_effect = RuntimeError(
            "list failed"
        )

        result = vault_client.list_secrets("api_keys")

        assert result == []

    # === health_check 测试 ===

    def test_health_check_healthy_returns_status(self, vault_client):
        """测试 health_check Vault正常 返回healthy"""
        vault_client.client.sys.read_health_status.return_value = {
            "version": "1.15.0",
            "leader": "true",
        }

        result = vault_client.health_check()

        assert result["status"] == "healthy"
        assert result["version"] == "1.15.0"
        assert result["leader"] == "true"

    def test_health_check_unhealthy_returns_error(self, vault_client):
        """测试 health_check Vault异常 返回unhealthy"""
        vault_client.client.sys.read_health_status.side_effect = RuntimeError(
            "connection refused"
        )

        result = vault_client.health_check()

        assert result["status"] == "unhealthy"
        assert "connection refused" in result["error"]

    # === 单例 / 初始化函数测试 ===

    def test_get_vault_client_singleton_returns_same_instance(self):
        """测试 get_vault_client 多次调用 返回同一实例"""
        with (
            patch("app.services.vault_client.hvac"),
            patch("app.services.vault_client._vault_client", None),
        ):
            client1 = get_vault_client()
            client2 = get_vault_client()

            assert client1 is client2

    def test_init_vault_client_returns_configured_client(self):
        """测试 init_vault_client 注入配置 返回配置后的客户端"""
        with patch("app.services.vault_client.hvac"):
            config = VaultConfig(
                url="http://vault:8200",
                role_id="role-123",
                secret_id="secret-456",
                mount_point="custom",
                kv_version=1,
            )

            client = init_vault_client(config)

            assert client.url == "http://vault:8200"
            assert client.role_id == "role-123"
            assert client.mount_point == "custom"
            assert client.kv_version == 1


class TestApiKeyService:
    """API Key 服务测试"""

    @pytest.fixture
    def mock_db(self):
        """Mock 数据库会话"""
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.delete = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def mock_vault(self):
        """Mock Vault 客户端"""
        with patch("app.services.api_key_service.get_vault_client") as mock:
            vault = MagicMock()
            mock.return_value = vault
            yield vault

    @staticmethod
    def _make_api_key(**overrides):
        """构造 mock ApiKey 对象"""
        defaults = {
            "id": "key-123",
            "name": "test-key",
            "provider": "openai",
            "vault_path": "api_keys/key-123",
            "key_preview": "sk**90",
            "usage": MagicMock(),
            "status": MagicMock(),
            "expires_at": None,
            "description": None,
            "created_by": None,
            "use_count": 0,
            "last_used_at": None,
            "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 1, 1),
        }
        defaults.update(overrides)
        mock_key = MagicMock()
        for k, v in defaults.items():
            setattr(mock_key, k, v)
        return mock_key

    # === Schema / 静态方法测试（已有，保留） ===

    def test_generate_key_preview(self, mock_db, mock_vault):
        """测试 Key 预览生成"""
        from app.services.api_key_service import ApiKeyService

        service = ApiKeyService(mock_db)

        # 测试各种长度的 Key
        assert service._generate_key_preview("sk-1234567890") == "sk**90"
        assert service._generate_key_preview("abc") == "ab**"
        assert service._generate_key_preview("ab") == "ab**"
        assert service._generate_key_preview("a") == "a**"

    def test_generate_key_preview_boundary_len_five(self):
        """测试 _generate_key_preview 长度5边界 返回前后各2位"""
        assert ApiKeyService._generate_key_preview("abcde") == "ab**de"

    def test_generate_key_preview_boundary_len_four(self):
        """测试 _generate_key_preview 长度4边界 返回前2位加星号"""
        assert ApiKeyService._generate_key_preview("abcd") == "ab**"

    def test_generate_vault_path_formats_correctly(self):
        """测试 _generate_vault_path 正常UUID 格式化为api_keys路径"""
        assert ApiKeyService._generate_vault_path("abc-123") == "api_keys/abc-123"

    # === create 测试 ===

    async def test_create_normal_creation_returns_response(self, mock_db, mock_vault):
        """测试 create 正常创建 返回响应"""
        data = ApiKeyCreate(
            name="test-key",
            provider="openai",
            api_key="sk-test1234567890",
            usage=KeyUsage.LLM,
        )

        async def mock_refresh(obj):
            obj.created_at = datetime(2026, 1, 1)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        service = ApiKeyService(mock_db)
        result = await service.create(data, user_id="user-1")

        assert result.name == "test-key"
        assert result.provider == "openai"
        assert result.api_key == "sk-test1234567890"
        assert result.key_preview == "sk**90"
        mock_vault.write_secret.assert_called_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    # === get 测试 ===

    async def test_get_key_exists_returns_apikey(self, mock_db, mock_vault):
        """测试 get Key存在 返回ApiKey"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)
        result = await service.get("key-123")

        assert result is mock_key

    async def test_get_key_not_found_raises_notfounderror(self, mock_db, mock_vault):
        """测试 get Key不存在 抛出NotFoundError"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)

        with pytest.raises(NotFoundError, match="不存在"):
            await service.get("missing-key")

    # === get_decrypted_key 测试 ===

    async def test_get_decrypted_key_secret_found_returns_key(
        self, mock_db, mock_vault
    ):
        """测试 get_decrypted_key Secret存在 返回解密Key"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_vault.read_secret.return_value = {"api_key": "sk-decrypted"}

        service = ApiKeyService(mock_db)
        result = await service.get_decrypted_key("key-123")

        assert result == "sk-decrypted"

    async def test_get_decrypted_key_secret_missing_raises_notfounderror(
        self, mock_db, mock_vault
    ):
        """测试 get_decrypted_key Secret不存在 抛出NotFoundError"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_vault.read_secret.return_value = None

        service = ApiKeyService(mock_db)

        with pytest.raises(NotFoundError, match="已失效"):
            await service.get_decrypted_key("key-123")

    # === list 测试 ===

    async def test_list_no_filters_returns_items_and_total(self, mock_db, mock_vault):
        """测试 list 无过滤 返回条目和总数"""
        mock_key1 = self._make_api_key(id="k1")
        mock_key2 = self._make_api_key(id="k2")

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = [
            mock_key1,
            mock_key2,
        ]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_items_result])

        service = ApiKeyService(mock_db)
        items, total = await service.list()

        assert total == 2
        assert len(items) == 2

    async def test_list_with_filters_applies_provider_filter(self, mock_db, mock_vault):
        """测试 list 带provider过滤 返回过滤结果"""
        mock_key = self._make_api_key()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = [mock_key]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_items_result])

        service = ApiKeyService(mock_db)
        items, total = await service.list(provider="openai")

        assert total == 1
        assert len(items) == 1

    async def test_list_count_zero_returns_empty(self, mock_db, mock_vault):
        """测试 list 无数据 返回空列表和零总数"""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_items_result])

        service = ApiKeyService(mock_db)
        items, total = await service.list(page=1, page_size=10)

        assert total == 0
        assert items == []

    # === update 测试 ===

    async def test_update_name_changes_name(self, mock_db, mock_vault):
        """测试 update 修改name 更新成功"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)
        result = await service.update("key-123", ApiKeyUpdate(name="new-name"))

        assert result.name == "new-name"
        mock_db.commit.assert_awaited_once()

    async def test_update_api_key_rewrites_vault_and_preview(self, mock_db, mock_vault):
        """测试 update 修改api_key 重写Vault并更新预览"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)
        await service.update("key-123", ApiKeyUpdate(api_key="sk-new1234567890"))

        mock_vault.write_secret.assert_called_once_with(
            path="api_keys/key-123",
            secret={"api_key": "sk-new1234567890"},
        )
        assert mock_key.key_preview == "sk**90"

    async def test_update_status_changes_status(self, mock_db, mock_vault):
        """测试 update 修改status 更新成功"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)
        await service.update("key-123", ApiKeyUpdate(status=KeyStatus.INACTIVE))

        assert mock_key.status is not None

    async def test_update_no_fields_only_commits(self, mock_db, mock_vault):
        """测试 update 无修改字段 仅提交"""
        mock_key = self._make_api_key(name="original")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)
        result = await service.update("key-123", ApiKeyUpdate())

        assert result.name == "original"
        mock_vault.write_secret.assert_not_called()
        mock_db.commit.assert_awaited_once()

    # === delete 测试 ===

    async def test_delete_success_removes_from_vault_and_db(self, mock_db, mock_vault):
        """测试 delete 正常删除 从Vault和DB删除"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)
        await service.delete("key-123")

        mock_vault.delete_secret.assert_called_once_with("api_keys/key-123")
        mock_db.delete.assert_awaited_once_with(mock_key)
        mock_db.commit.assert_awaited_once()

    async def test_delete_vault_failure_continues_db_deletion(
        self, mock_db, mock_vault
    ):
        """测试 delete Vault删除失败 仍删除DB记录"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_vault.delete_secret.side_effect = RuntimeError("vault error")

        service = ApiKeyService(mock_db)
        await service.delete("key-123")

        mock_db.delete.assert_awaited_once_with(mock_key)
        mock_db.commit.assert_awaited_once()

    # === rotate_key 测试 ===

    async def test_rotate_key_success_returns_new_key(self, mock_db, mock_vault):
        """测试 rotate_key 正常轮换 返回新Key"""
        mock_key = self._make_api_key()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_refresh(obj):
            obj.created_at = datetime(2026, 1, 1)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        service = ApiKeyService(mock_db)
        result = await service.rotate_key("key-123")

        assert result.id == "key-123"
        assert result.api_key.startswith("sk-")
        mock_vault.write_secret.assert_called_once()

    # === record_usage 测试 ===

    async def test_record_usage_success_increments_count(self, mock_db, mock_vault):
        """测试 record_usage 正常记录 自增使用次数"""
        mock_key = self._make_api_key(use_count=5)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)
        await service.record_usage("key-123")

        assert mock_key.use_count == 6
        assert mock_key.last_used_at is not None
        mock_db.commit.assert_awaited_once()

    async def test_record_usage_key_not_found_raises(self, mock_db, mock_vault):
        """测试 record_usage Key不存在 抛出NotFoundError"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ApiKeyService(mock_db)

        with pytest.raises(NotFoundError, match="不存在"):
            await service.record_usage("missing-key")

    # === health_check 测试 ===

    async def test_health_check_delegates_to_vault(self, mock_db, mock_vault):
        """测试 health_check 正常调用 委托给Vault"""
        mock_vault.health_check.return_value = {"status": "healthy"}

        service = ApiKeyService(mock_db)
        result = await service.health_check()

        assert result == {"status": "healthy"}
        mock_vault.health_check.assert_called_once()
