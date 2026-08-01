from __future__ import annotations

import time
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.model_instance import ModelInstance, ModelProvider, ModelStatus
from app.schemas.model import (
    ModelCompareRequest,
    ModelCompareResponse,
    ModelCompareResult,
    ModelInstanceCreate,
    ModelInstanceUpdate,
)
from app.services.api_key_service import ApiKeyService
from app.services.llm_manager import LLMManager

logger = structlog.get_logger(__name__)

# Type alias defined at module scope so ``list`` resolves to the builtin
# rather than being shadowed by :meth:`ModelService.list`.
ModelInstanceList = list[ModelInstance]


class ModelService:
    """模型实例管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.api_key_service = ApiKeyService(db)
        self.llm_manager = LLMManager.get_instance()

    async def create(
        self,
        data: ModelInstanceCreate,
        user_id: str | None = None,
    ) -> ModelInstance:
        """创建模型实例"""
        # 验证 API Key 存在
        if data.api_key_id:
            await self.api_key_service.get(data.api_key_id)

        # 创建实例
        instance = ModelInstance(
            name=data.name,
            provider=ModelProvider(data.provider.value),
            model_type=data.model_type,
            api_key_id=data.api_key_id,
            config=data.config.model_dump(),
            status=ModelStatus.ACTIVE,  # 默认启用，创建后即可使用
            description=data.description,
            created_by=user_id,
        )

        # Embedding 模型需要维度
        if data.model_type == "embedding":
            # 从配置中获取或使用默认值
            extra = getattr(data.config, "extra", None) or {}
            instance.embedding_dimension = extra.get("dimension", 1536)

        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)

        # 预热 LLMManager 缓存（优化首次访问；未配置 API Key 等情况失败时不阻塞创建）
        try:
            await self.llm_manager.get_llm(instance.id)
        except Exception as e:
            logger.warning("llm_preload_skipped", instance_id=instance.id, error=str(e))

        logger.info(
            "model_instance_created",
            instance_id=instance.id,
            name=instance.name,
        )
        return instance

    async def get(self, model_id: str) -> ModelInstance:
        """获取模型实例"""
        result = await self.db.execute(
            select(ModelInstance).where(ModelInstance.id == model_id)
        )
        instance = result.scalar_one_or_none()
        if not instance:
            raise NotFoundError("模型实例不存在")
        return instance

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        provider: str | None = None,
        model_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[ModelInstance], int]:
        """列出模型实例"""
        query = select(ModelInstance)

        if provider:
            query = query.where(ModelInstance.provider == ModelProvider(provider))
        if model_type:
            query = query.where(ModelInstance.model_type == model_type)
        if status:
            query = query.where(ModelInstance.status == ModelStatus(status))

        # 统计总数
        from sqlalchemy import func

        count_result = await self.db.execute(
            select(func.count(ModelInstance.id)).select_from(ModelInstance)
        )
        total = count_result.scalar() or 0

        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update(
        self,
        model_id: str,
        data: ModelInstanceUpdate,
    ) -> ModelInstance:
        """更新模型实例"""
        instance = await self.get(model_id)

        if data.name is not None:
            instance.name = data.name

        if data.api_key_id is not None:
            if data.api_key_id:
                await self.api_key_service.get(data.api_key_id)
            instance.api_key_id = data.api_key_id

        if data.status is not None:
            instance.status = ModelStatus(data.status.value)

        if data.config is not None:
            instance.config = data.config.model_dump()
            if instance.model_type == "embedding":
                extra = getattr(data.config, "extra", None) or {}
                instance.embedding_dimension = extra.get("dimension")

        if data.description is not None:
            instance.description = data.description

        await self.db.commit()
        await self.db.refresh(instance)

        # 刷新缓存
        await self.llm_manager.reload_llm(model_id)

        logger.info("model_instance_updated", instance_id=model_id)
        return instance

    async def toggle_status(self, model_id: str) -> ModelInstance:
        """切换模型状态"""
        instance = await self.get(model_id)

        if instance.status == ModelStatus.ACTIVE:
            instance.status = ModelStatus.INACTIVE
        else:
            instance.status = ModelStatus.ACTIVE

        await self.db.commit()
        await self.db.refresh(instance)

        # 刷新缓存
        await self.llm_manager.reload_llm(model_id)

        logger.info(
            "model_status_toggled",
            instance_id=model_id,
            new_status=instance.status.value,
        )
        return instance

    async def delete(self, model_id: str) -> None:
        """删除模型实例"""
        instance = await self.get(model_id)

        # 从缓存移除
        await self.llm_manager.remove_llm(model_id)

        # 删除记录
        await self.db.delete(instance)
        await self.db.commit()

        logger.info("model_instance_deleted", instance_id=model_id)

    async def compare_models(
        self,
        data: ModelCompareRequest,
        user_id: str | None = None,
    ) -> ModelCompareResponse:
        """对比多个模型"""
        started_at = datetime.now()
        results: list[ModelCompareResult] = []

        for model_id in data.model_ids:
            result = ModelCompareResult(
                model_id=model_id,
                model_name="",
                response="",
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                success=False,
            )

            try:
                # 获取模型实例
                instance = await self.get(model_id)
                result.model_name = instance.name

                # 获取 LLM
                llm = await self.llm_manager.get_llm(model_id)

                # 调用模型
                start_time = time.time()
                from app.llm.base import Message

                response = await llm.chat(
                    messages=[Message(role="user", content=data.question)]
                )
                latency_ms = int((time.time() - start_time) * 1000)

                result.response = response.content
                result.latency_ms = latency_ms
                result.input_tokens = response.prompt_tokens or 0
                result.output_tokens = response.completion_tokens or 0
                result.success = True

            except Exception as e:
                logger.warning("model_compare_failed", model_id=model_id, error=str(e))
                result.error = str(e)

            results.append(result)

        completed_at = datetime.now()

        return ModelCompareResponse(
            question=data.question,
            results=results,
            started_at=started_at,
            completed_at=completed_at,
        )

    async def get_active_models(self, model_type: str = "chat") -> ModelInstanceList:
        """获取所有活跃的模型"""
        result = await self.db.execute(
            select(ModelInstance).where(
                ModelInstance.model_type == model_type,
                ModelInstance.status == ModelStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())
