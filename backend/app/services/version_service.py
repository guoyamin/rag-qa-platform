from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.model_instance import ModelInstance
from app.models.model_version import (
    ModelVersion,
    ReleaseType,
    VersionRelease,
    VersionStatus,
)

logger = structlog.get_logger(__name__)


class VersionService:
    """版本管理服务"""

    # 灰度发布阶段
    ROLLOUT_STAGES = [10, 30, 50, 100]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_version(
        self,
        model_id: str,
        version: str,
        config: dict[str, Any],
        description: str | None = None,
        user_id: str | None = None,
    ) -> ModelVersion:
        """创建新版本"""
        # 验证模型存在
        model = await self._get_model(model_id)
        if not model:
            raise NotFoundError("模型不存在")

        # 检查版本号是否重复
        existing = await self._get_version_by_number(model_id, version)
        if existing:
            raise ValidationError(f"版本 {version} 已存在")

        model_version = ModelVersion(
            model_id=model_id,
            version=version,
            description=description,
            config_snapshot=config,
            status=VersionStatus.DRAFT,
            rollout_percentage=0,
            created_by=user_id,
        )

        self.db.add(model_version)
        await self.db.commit()
        await self.db.refresh(model_version)

        logger.info("version_created", model_id=model_id, version=version)
        return model_version

    async def get_version(self, version_id: str) -> ModelVersion:
        """获取版本"""
        result = await self.db.execute(
            select(ModelVersion).where(ModelVersion.id == version_id)
        )
        version = result.scalar_one_or_none()
        if not version:
            raise NotFoundError("版本不存在")
        return version

    async def list_versions(
        self,
        model_id: str,
        status: VersionStatus | None = None,
    ) -> list[ModelVersion]:
        """列出模型的所有版本"""
        query = select(ModelVersion).where(ModelVersion.model_id == model_id)

        if status:
            query = query.where(ModelVersion.status == status)

        query = query.order_by(ModelVersion.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_version(self, model_id: str) -> ModelVersion | None:
        """获取当前活跃版本"""
        result = await self.db.execute(
            select(ModelVersion).where(
                ModelVersion.model_id == model_id,
                ModelVersion.status == VersionStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def rollout(
        self,
        version_id: str,
        percentage: int | None = None,
        user_id: str | None = None,
    ) -> ModelVersion:
        """
        灰度发布

        Args:
            version_id: 版本ID
            percentage: 目标百分比（10/30/50/100）
            user_id: 发布人
        """
        version = await self.get_version(version_id)

        # 确定发布百分比
        if percentage is None:
            # 自动推进到下一阶段
            percentage = self._get_next_stage(version.rollout_percentage)

        if percentage not in self.ROLLOUT_STAGES:
            raise ValidationError(f"灰度百分比必须是 {self.ROLLOUT_STAGES} 之一")

        # 更新版本状态
        old_percentage = version.rollout_percentage
        version.rollout_percentage = percentage

        if percentage == 100:
            version.status = VersionStatus.ACTIVE
        else:
            version.status = VersionStatus.ROLLING_OUT

        # 记录发布
        release = VersionRelease(
            version_id=version_id,
            release_type=ReleaseType.ROLLOUT,
            from_percentage=old_percentage,
            to_percentage=percentage,
            released_by=user_id,
        )
        self.db.add(release)

        # 如果是全量发布，废弃其他版本
        if percentage == 100:
            await self._deprecate_other_versions(version.model_id, version_id)

        await self.db.commit()
        await self.db.refresh(version)

        logger.info("version_rollout", version_id=version_id, percentage=percentage)
        return version

    async def rollback(
        self,
        version_id: str,
        user_id: str | None = None,
    ) -> ModelVersion:
        """
        回滚版本

        将版本状态设为 DEPRECATED
        """
        version = await self.get_version(version_id)

        if version.status == VersionStatus.ACTIVE:
            # 查找上一个版本
            previous = await self._get_previous_version(
                version.model_id, version.version
            )
            if previous:
                await self.rollout(previous.id, percentage=100, user_id=user_id)

        version.status = VersionStatus.DEPRECATED
        version.rollout_percentage = 0

        release = VersionRelease(
            version_id=version_id,
            release_type=ReleaseType.ROLLBACK,
            from_percentage=version.rollout_percentage,
            to_percentage=0,
            released_by=user_id,
        )
        self.db.add(release)

        await self.db.commit()
        await self.db.refresh(version)

        logger.info("version_rollback", version_id=version_id)
        return version

    async def delete_version(self, version_id: str) -> None:
        """删除版本（仅允许草稿版本）"""
        version = await self.get_version(version_id)

        if version.status != VersionStatus.DRAFT:
            raise ValidationError("只能删除草稿版本")

        await self.db.delete(version)
        await self.db.commit()

        logger.info("version_deleted", version_id=version_id)

    def _get_next_stage(self, current_percentage: int) -> int:
        """获取下一灰度阶段"""
        for stage in self.ROLLOUT_STAGES:
            if stage > current_percentage:
                return stage
        return 100

    async def _get_model(self, model_id: str) -> ModelInstance | None:
        """获取模型"""
        result = await self.db.execute(
            select(ModelInstance).where(ModelInstance.id == model_id)
        )
        return result.scalar_one_or_none()

    async def _get_version_by_number(
        self, model_id: str, version: str
    ) -> ModelVersion | None:
        """根据版本号获取版本"""
        result = await self.db.execute(
            select(ModelVersion).where(
                ModelVersion.model_id == model_id,
                ModelVersion.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def _get_previous_version(
        self, model_id: str, current_version: str
    ) -> ModelVersion | None:
        """获取上一个版本"""
        result = await self.db.execute(
            select(ModelVersion)
            .where(
                ModelVersion.model_id == model_id,
                ModelVersion.version < current_version,
                ModelVersion.status.in_(
                    [VersionStatus.ACTIVE, VersionStatus.ROLLING_OUT]
                ),
            )
            .order_by(ModelVersion.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _deprecate_other_versions(
        self, model_id: str, except_version_id: str
    ) -> None:
        """废弃其他版本"""
        from sqlalchemy import update

        await self.db.execute(
            update(ModelVersion)
            .where(
                ModelVersion.model_id == model_id,
                ModelVersion.id != except_version_id,
                ModelVersion.status != VersionStatus.DEPRECATED,
            )
            .values(status=VersionStatus.DEPRECATED)
        )
