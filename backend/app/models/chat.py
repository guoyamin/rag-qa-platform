"""
智能问答平台 - 聊天会话与消息模型
"""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatSession(Base):
    """对话会话模型"""

    __tablename__ = "chat_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        comment="用户ID",
    )
    title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="会话标题",
    )
    kb_ids: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="关联知识库ID列表（逗号分隔）",
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="消息数量",
    )

    def __repr__(self) -> str:
        return f"<ChatSession {self.id} user={self.user_id}>"


class ChatMessage(Base):
    """聊天消息模型"""

    __tablename__ = "chat_messages"

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id"),
        nullable=False,
        comment="会话ID",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="角色: user/assistant/system",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息内容",
    )
    sources: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="引用来源(JSON)",
    )
    tokens_used: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="使用Token数",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="响应延迟(ms)",
    )
    is_liked: Mapped[bool | None] = mapped_column(
        nullable=True,
        comment="用户点赞",
    )
    feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="用户反馈",
    )

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} role={self.role} session={self.session_id}>"
