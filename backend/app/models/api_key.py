"""
智能问答平台 - API Key 数据模型

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 功能描述: API Key 加密存储
- 版本: V1.0

修订记录:
- 2026-08-01 V1.0 初始版本（AI生成）
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiKeyStatus(str, PyEnum):
    """Key 状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


class ApiKeyUsage(str, PyEnum):
    """Key 用途"""

    LLM = "llm"
    EMBEDDING = "embedding"
    BOTH = "both"


class ApiKey(Base):
    """API Key 模型"""

    __tablename__ = "api_keys"

    # 基础信息
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Key 名称",
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="提供商名称",
    )

    # Vault 存储路径（不存储实际 Key）
    vault_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Vault 中 Secret 的路径",
    )

    # Key 预览（用于显示，不含敏感信息）
    key_preview: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Key 预览（显示前后各2位）",
    )

    # 使用配置
    usage: Mapped[ApiKeyUsage] = mapped_column(
        Enum(ApiKeyUsage),
        default=ApiKeyUsage.LLM,
        nullable=False,
        comment="用途",
    )

    # 状态与有效期
    status: Mapped[ApiKeyStatus] = mapped_column(
        Enum(ApiKeyStatus),
        default=ApiKeyStatus.ACTIVE,
        nullable=False,
        index=True,
        comment="状态",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="过期时间",
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
        Integer,
        default=0,
        nullable=False,
        comment="使用次数",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后使用时间",
    )

    def __repr__(self) -> str:
        return f"<ApiKey {self.name} ({self.provider})>"
