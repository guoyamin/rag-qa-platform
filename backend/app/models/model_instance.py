"""
智能问答平台 - 模型实例数据模型

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 功能描述: 模型实例配置
- 版本: V1.0

修订记录:
- 2026-08-01 V1.0 初始版本（AI生成）
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelProvider(str, PyEnum):
    """模型提供商"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    QWEN = "qwen"
    DOUBAO = "doubao"
    LOCAL = "local"
    OTHER = "other"


class ModelStatus(str, PyEnum):
    """模型状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class ModelInstance(Base):
    """模型实例模型"""

    __tablename__ = "model_instances"

    # 基础信息
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="实例名称",
    )
    provider: Mapped[ModelProvider] = mapped_column(
        Enum(ModelProvider),
        nullable=False,
        comment="提供商",
    )
    model_type: Mapped[str] = mapped_column(
        String(20),
        default="chat",
        nullable=False,
        comment="模型类型: chat/embedding",
    )

    # API Key 关联
    api_key_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="关联的 API Key ID",
    )

    # 模型配置（JSON 存储）
    config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="模型配置（温度、超时等）",
    )

    # 状态
    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus),
        default=ModelStatus.INACTIVE,
        nullable=False,
        index=True,
        comment="状态",
    )

    # 元数据
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="描述",
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="创建人 ID",
    )

    # 使用统计
    use_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="使用次数",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后使用时间",
    )

    # Embedding 专用配置
    embedding_dimension: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="向量维度（Embedding 模型专用）",
    )

    def __repr__(self) -> str:
        return f"<ModelInstance {self.name} ({self.provider.value})>"
