"""
智能问答平台 - 知识库模型
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus(str, PyEnum):
    """文档状态"""

    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 处理失败


class DocumentType(str, PyEnum):
    """文档类型"""

    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    MARKDOWN = "markdown"
    TXT = "txt"
    HTML = "html"
    URL = "url"


class KnowledgeBase(Base):
    """知识库模型"""

    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="知识库名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="描述",
    )
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        comment="创建者ID",
    )
    document_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="文档数量",
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="分块数量",
    )


class Document(Base):
    """文档模型"""

    __tablename__ = "documents"

    kb_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_bases.id"),
        nullable=False,
        comment="所属知识库ID",
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="文档标题",
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        nullable=False,
        comment="文档类型",
    )
    file_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="文件路径",
    )
    file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="文件大小(字节)",
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="文档内容",
    )
    status: Mapped[DocumentStatus] = mapped_column(
        default=DocumentStatus.PENDING,
        nullable=False,
        comment="处理状态",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="分块数量",
    )
    vector_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="向量数量",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="处理完成时间",
    )


class DocumentChunk(Base):
    """文档分块模型"""

    __tablename__ = "document_chunks"

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id"),
        nullable=False,
        comment="文档ID",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="分块序号",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="分块内容",
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Token数",
    )
    vector_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Milvus向量ID",
    )
