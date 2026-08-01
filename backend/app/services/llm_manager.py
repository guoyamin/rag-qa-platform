from __future__ import annotations

import asyncio
import threading
from typing import Any

import structlog

from app.core.exceptions import ServiceUnavailableError
from app.llm.base import BaseLLM, LLMConfig, LLMFactory

logger = structlog.get_logger(__name__)


class LLMManager:
    """
    LLM 运行时管理器

    功能：
    1. 单例模式管理所有 LLM 实例
    2. 运行时缓存，支持热更新
    3. 线程安全

    热更新机制：
    - 配置变更时调用 reload_llm() 刷新缓存
    - 下次调用 get_llm() 时会加载新配置
    - 无需重启服务
    """

    _instance: LLMManager | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._llm_cache: dict[str, BaseLLM] = {}
        self._config_cache: dict[str, dict[str, Any]] = {}
        self._cache_lock = asyncio.Lock()
        self._db_session = None
        logger.info("llm_manager_initialized")

    @classmethod
    def get_instance(cls) -> LLMManager:
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def _load_config_from_db(self, model_id: str) -> dict[str, Any] | None:
        """
        从数据库加载模型配置

        Args:
            model_id: 模型实例 ID

        Returns:
            模型配置字典，失败返回 None
        """
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.model_instance import ModelInstance, ModelStatus

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ModelInstance).where(
                    ModelInstance.id == model_id,
                    ModelInstance.status == ModelStatus.ACTIVE,
                )
            )
            instance = result.scalar_one_or_none()

            if not instance:
                logger.warning("model_not_found_or_inactive", model_id=model_id)
                return None

            # 获取 API Key
            api_key = None
            if instance.api_key_id:
                from app.models.api_key import ApiKey, ApiKeyStatus
                from app.services.vault_client import get_vault_client

                api_key_result = await db.execute(
                    select(ApiKey).where(
                        ApiKey.id == instance.api_key_id,
                        ApiKey.status == ApiKeyStatus.ACTIVE,
                    )
                )
                api_key_record = api_key_result.scalar_one_or_none()

                if api_key_record:
                    vault = get_vault_client()
                    secret = vault.read_secret(api_key_record.vault_path)
                    if secret:
                        api_key = secret.get("api_key")

            return {
                "provider": instance.provider.value,
                "model": instance.config.get("model"),
                "api_key": api_key,
                "api_base": instance.config.get("api_base"),
                "temperature": instance.config.get("temperature", 0.7),
                "max_tokens": instance.config.get("max_tokens", 2048),
                "top_p": instance.config.get("top_p"),
                "timeout": instance.config.get("timeout", 60),
            }

    async def get_llm(self, model_id: str) -> BaseLLM:
        """
        获取 LLM 实例

        1. 先检查内存缓存
        2. 缓存未命中则从数据库加载配置
        3. 创建 LLM 实例并缓存

        Args:
            model_id: 模型实例 ID

        Returns:
            LLM 实例

        Raises:
            ServiceUnavailableError: 模型不可用
        """
        async with self._cache_lock:
            # 检查缓存
            if model_id in self._llm_cache:
                return self._llm_cache[model_id]

            # 从数据库加载配置
            config_dict = await self._load_config_from_db(model_id)
            if not config_dict:
                raise ServiceUnavailableError(f"模型 {model_id} 不可用")

            # 创建 LLM 配置
            llm_config = LLMConfig(
                provider=config_dict["provider"],
                api_key=config_dict.get("api_key"),
                api_base=config_dict.get("api_base"),
                model=config_dict["model"],
                temperature=config_dict.get("temperature", 0.7),
                max_tokens=config_dict.get("max_tokens", 2048),
                top_p=config_dict.get("top_p"),
                timeout=config_dict.get("timeout", 60),
            )

            # 创建 LLM 实例
            llm = LLMFactory.create(llm_config)

            # 缓存
            self._llm_cache[model_id] = llm
            self._config_cache[model_id] = config_dict

            logger.info(
                "llm_instance_created", model_id=model_id, provider=llm_config.provider
            )
            return llm

    async def reload_llm(self, model_id: str) -> None:
        """
        刷新 LLM 实例缓存

        下次调用 get_llm() 时会重新加载配置

        Args:
            model_id: 模型实例 ID
        """
        async with self._cache_lock:
            if model_id in self._llm_cache:
                del self._llm_cache[model_id]
            if model_id in self._config_cache:
                del self._config_cache[model_id]
            logger.info("llm_cache_reloaded", model_id=model_id)

    async def remove_llm(self, model_id: str) -> None:
        """
        移除 LLM 实例

        Args:
            model_id: 模型实例 ID
        """
        async with self._cache_lock:
            self._llm_cache.pop(model_id, None)
            self._config_cache.pop(model_id, None)
            logger.info("llm_instance_removed", model_id=model_id)

    async def clear_cache(self) -> None:
        """清空所有缓存"""
        async with self._cache_lock:
            self._llm_cache.clear()
            self._config_cache.clear()
            logger.info("llm_cache_cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        return {
            "cached_models": len(self._llm_cache),
            "model_ids": list(self._llm_cache.keys()),
        }

    async def preload_models(self, model_ids: list[str]) -> int:
        """
        预加载多个模型

        Args:
            model_ids: 模型 ID 列表

        Returns:
            成功加载的数量
        """
        loaded = 0
        for model_id in model_ids:
            try:
                await self.get_llm(model_id)
                loaded += 1
            except Exception as e:
                logger.warning("preload_failed", model_id=model_id, error=str(e))

        logger.info("models_preloaded", total=len(model_ids), loaded=loaded)
        return loaded

    async def update_config(self, model_id: str, config: LLMConfig) -> None:
        """
        直接更新配置（用于测试或配置注入）

        Args:
            model_id: 模型实例 ID
            config: 新的配置
        """
        async with self._cache_lock:
            llm = LLMFactory.create(config)
            self._llm_cache[model_id] = llm
            self._config_cache[model_id] = config.model_dump()
            logger.info("llm_config_updated", model_id=model_id)


# 便捷函数
def get_llm_manager() -> LLMManager:
    """获取 LLM 管理器实例"""
    return LLMManager.get_instance()
