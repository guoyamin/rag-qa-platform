"""
智能问答平台 - 预设模板

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TemplateType(str, PyEnum):
    """模板类型"""

    CHAT = "chat"  # 对话模板
    SYSTEM_PROMPT = "system_prompt"  # 系统提示词
    RAG_QUERY = "rag_query"  # RAG 查询模板
    EMBEDDING = "embedding"  # Embedding 配置
    MODEL = "model"  # 模型配置


class PresetTemplate(Base):
    """预设模板"""

    __tablename__ = "preset_templates"

    # 基本信息
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="模板名称",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="模板描述",
    )

    template_type: Mapped[TemplateType] = mapped_column(
        nullable=False,
        comment="模板类型",
    )

    # 模板内容
    template: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="模板内容（JSON格式）",
    )

    # 配置
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否默认模板",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否启用",
    )

    # 元数据
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="标签",
    )

    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="分类",
    )

    version: Mapped[str] = mapped_column(
        String(20),
        default="v1.0",
        nullable=False,
        comment="模板版本",
    )

    # 创建人
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="创建人ID",
    )

    def __repr__(self) -> str:
        return f"<PresetTemplate {self.name} ({self.template_type.value})>"
