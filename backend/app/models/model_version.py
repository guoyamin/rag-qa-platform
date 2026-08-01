"""
智能问答平台 - 模型版本管理

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VersionStatus(str, PyEnum):
    """版本状态"""

    DRAFT = "draft"  # 草稿，未发布
    ROLLING_OUT = "rolling_out"  # 灰度发布中
    ACTIVE = "active"  # 正式启用
    DEPRECATED = "deprecated"  # 已废弃


class ReleaseType(str, PyEnum):
    """发布类型"""

    ROLLOUT = "rollout"  # 灰度发布
    ROLLBACK = "rollback"  # 回滚
    FULL = "full"  # 全量发布


class ModelVersion(Base):
    """模型版本"""

    __tablename__ = "model_versions"

    # 关联信息
    model_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="模型实例ID",
    )

    # 版本信息
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="版本号：v1.0",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="版本说明",
    )

    # 配置快照
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="完整配置快照",
    )

    # 状态
    status: Mapped[VersionStatus] = mapped_column(
        String(20),
        default=VersionStatus.DRAFT,
        nullable=False,
        comment="状态",
    )

    rollout_percentage: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="灰度发布百分比",
    )

    # 元数据
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="创建人",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        comment="创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<ModelVersion {self.model_id} {self.version}>"


class VersionRelease(Base):
    """版本发布记录"""

    __tablename__ = "version_releases"

    version_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="版本ID",
    )

    release_type: Mapped[ReleaseType] = mapped_column(
        String(20),
        nullable=False,
        comment="发布类型",
    )

    from_percentage: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="发布前百分比",
    )

    to_percentage: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="发布后百分比",
    )

    released_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="发布人",
    )

    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        comment="发布时间",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="发布备注",
    )

    def __repr__(self) -> str:
        return f"<VersionRelease {self.version_id} {self.release_type.value}>"
