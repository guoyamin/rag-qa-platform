"""
智能问答平台 - 公告服务
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.announcement import Announcement, AnnouncementStatus, AnnouncementType

logger = structlog.get_logger(__name__)


class AnnouncementService:
    """公告服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        title: str,
        content: str,
        type_: AnnouncementType = AnnouncementType.NOTICE,
        pinned: bool = False,
    ) -> Announcement:
        """创建公告"""
        existing = await self._get_by_title(title)
        if existing:
            raise ValidationError(f"公告标题 '{title}' 已存在")

        announcement = Announcement(
            title=title,
            content=content,
            type=type_,
            pinned=pinned,
            status=AnnouncementStatus.DRAFT,
        )
        self.db.add(announcement)
        await self.db.commit()
        await self.db.refresh(announcement)

        logger.info(
            "announcement_created", announcement_id=announcement.id, title=title
        )
        return announcement

    async def get(self, announcement_id: str) -> Announcement:
        """获取公告"""
        result = await self.db.execute(
            select(Announcement).where(
                Announcement.id == announcement_id,
                Announcement.is_deleted.is_(False),
            )
        )
        announcement = result.scalar_one_or_none()

        if not announcement:
            raise NotFoundError("公告不存在")

        return announcement

    async def list_items(
        self,
        page: int = 1,
        page_size: int = 20,
        status: AnnouncementStatus | None = None,
        type_: AnnouncementType | None = None,
    ) -> tuple[list[Announcement], int]:
        """列出公告"""
        query = select(Announcement).where(Announcement.is_deleted.is_(False))

        if status is not None:
            query = query.where(Announcement.status == status)
        if type_ is not None:
            query = query.where(Announcement.type == type_)

        count_result = await self.db.execute(
            select(func.count(Announcement.id)).select_from(Announcement)
        )
        total = count_result.scalar() or 0

        query = query.order_by(
            Announcement.pinned.desc(),
            Announcement.created_at.desc(),
        )
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update(
        self,
        announcement_id: str,
        title: str | None = None,
        content: str | None = None,
        type_: AnnouncementType | None = None,
        status: AnnouncementStatus | None = None,
        pinned: bool | None = None,
    ) -> Announcement:
        """更新公告"""
        announcement = await self.get(announcement_id)

        if title is not None and title != announcement.title:
            existing = await self._get_by_title(title)
            if existing and existing.id != announcement_id:
                raise ValidationError(f"公告标题 '{title}' 已存在")
            announcement.title = title

        if content is not None:
            announcement.content = content

        if type_ is not None:
            announcement.type = type_

        if status is not None:
            announcement.status = status
            if status == AnnouncementStatus.PUBLISHED and not announcement.published_at:
                announcement.published_at = datetime.now(UTC)

        if pinned is not None:
            announcement.pinned = pinned

        await self.db.commit()
        await self.db.refresh(announcement)

        logger.info("announcement_updated", announcement_id=announcement_id)
        return announcement

    async def delete(self, announcement_id: str) -> None:
        """删除公告（软删）"""
        announcement = await self.get(announcement_id)
        announcement.is_deleted = True
        await self.db.commit()

        logger.info("announcement_deleted", announcement_id=announcement_id)

    async def publish(self, announcement_id: str) -> Announcement:
        """发布公告"""
        announcement = await self.get(announcement_id)
        announcement.status = AnnouncementStatus.PUBLISHED
        announcement.published_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(announcement)

        logger.info("announcement_published", announcement_id=announcement_id)
        return announcement

    async def _get_by_title(self, title: str) -> Announcement | None:
        """根据标题查询公告"""
        result = await self.db.execute(
            select(Announcement).where(
                Announcement.title == title,
                Announcement.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()
