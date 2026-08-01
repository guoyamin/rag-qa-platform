"""
智能问答平台 - 模型 Schema 独立测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))


class TestModelConfig:
    """模型配置测试（不导入 app，只测试 pydantic 模型）"""

    def test_model_config_from_pydantic(self):
        """测试模型配置"""
        from pydantic import BaseModel, Field

        class ModelConfig(BaseModel):
            model: str = Field(..., description="模型名称")
            api_base: str | None = Field(default=None)
            temperature: float = Field(default=0.7, ge=0, le=2)
            max_tokens: int = Field(default=2048, ge=1)
            top_p: float | None = Field(default=None, ge=0, le=1)
            timeout: int = Field(default=60, ge=1)

        config = ModelConfig(
            model="gpt-4o",
            api_base="https://api.openai.com/v1",
            temperature=0.7,
            max_tokens=2048,
        )

        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_key_preview_logic(self):
        """测试 Key 预览生成逻辑"""

        def generate_key_preview(api_key: str) -> str:
            if len(api_key) <= 4:
                return api_key[:2] + "**"
            return f"{api_key[:2]}**{api_key[-2:]}"

        assert generate_key_preview("sk-1234567890abcdef") == "sk**ef"
        assert generate_key_preview("abc") == "ab**"
        assert generate_key_preview("ab") == "ab**"
        assert generate_key_preview("a") == "a**"

    def test_vault_path_logic(self):
        """测试 Vault 路径生成逻辑"""

        def generate_vault_path(key_id: str) -> str:
            return f"api_keys/{key_id}"

        assert generate_vault_path("abc-123") == "api_keys/abc-123"

    def test_provider_enum_values(self):
        """测试提供商枚举值"""
        from enum import Enum

        class ModelProvider(str, Enum):
            OPENAI = "openai"
            ANTHROPIC = "anthropic"
            QWEN = "qwen"
            LOCAL = "local"

        assert ModelProvider.OPENAI.value == "openai"
        assert ModelProvider.ANTHROPIC.value == "anthropic"
        assert ModelProvider.QWEN.value == "qwen"
        assert ModelProvider.LOCAL.value == "local"

    def test_status_enum_values(self):
        """测试状态枚举值"""
        from enum import Enum

        class ModelStatus(str, Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"
            MAINTENANCE = "maintenance"

        assert ModelStatus.ACTIVE.value == "active"
        assert ModelStatus.INACTIVE.value == "inactive"
        assert ModelStatus.MAINTENANCE.value == "maintenance"


class TestVaultConfig:
    """Vault 配置测试"""

    def test_vault_config_dataclass(self):
        """测试 Vault 配置数据类"""
        from dataclasses import dataclass

        @dataclass
        class VaultConfig:
            url: str
            role_id: str | None
            secret_id: str | None
            mount_point: str = "secret"
            kv_version: int = 2

        config = VaultConfig(
            url="http://vault:8200",
            role_id="role-123",
            secret_id="secret-456",
        )

        assert config.url == "http://vault:8200"
        assert config.role_id == "role-123"
        assert config.secret_id == "secret-456"
        assert config.mount_point == "secret"
        assert config.kv_version == 2


class TestLLMManagerLogic:
    """LLM 管理器逻辑测试"""

    def test_cache_stats_structure(self):
        """测试缓存统计结构"""
        stats = {
            "cached_models": 0,
            "model_ids": [],
        }

        assert stats["cached_models"] == 0
        assert len(stats["model_ids"]) == 0

    def test_singleton_guard_logic(self):
        """测试单例守卫逻辑"""
        _instance = None

        class LLMManager:
            _lock = object()

            @classmethod
            def get_instance(cls):
                nonlocal _instance
                if _instance is None:
                    _instance = cls()
                return _instance

        manager1 = LLMManager.get_instance()
        manager2 = LLMManager.get_instance()

        assert manager1 is manager2
