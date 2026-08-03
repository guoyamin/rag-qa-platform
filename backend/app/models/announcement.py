"""
智能问答平台 - 公告模型
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnnouncementType(str, PyEnum):
    """公告类型"""

    NOTICE = "notice"  # 普通通知
    MAINTENANCE = "maintenance"  # 维护通知
    UPDATE = "update"  # 更新公告


class AnnouncementStatus(str, PyEnum):
    """公告状态"""

    DRAFT = "draft"  # 草稿
    PUBLISHED = "published"  # 已发布
    ARCHIVED = "archived"  # 已归档


class Announcement(Base):
    """公告"""

    __tablename__ = "announcements"

    # 内容
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="公告标题",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="公告正文",
    )

    # 类型与状态
    type: Mapped[AnnouncementType] = mapped_column(
        default=AnnouncementType.NOTICE,
        nullable=False,
        comment="公告类型",
    )
    status: Mapped[AnnouncementStatus] = mapped_column(
        default=AnnouncementStatus.DRAFT,
        nullable=False,
        comment="公告状态",
    )

    # 展示控制
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否置顶",
    )

    # 发布时间
    published_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="发布时间",
    )

    def __repr__(self) -> str:
        return f"<Announcement {self.title} ({self.status.value})>"
