"""
智能问答平台 - 数据库基础
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column


# 为 Base 添加通用字段
def id_column() -> MappedColumn[Any]:
    return mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )


def timestamp_columns() -> tuple[MappedColumn[Any], MappedColumn[Any]]:
    return (
        mapped_column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
        mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )


def soft_delete_column() -> MappedColumn[Any]:
    return mapped_column(default=False, nullable=False)


class Base(AsyncAttrs, DeclarativeBase):
    """SQLAlchemy基础模型"""

    # 通用字段
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
