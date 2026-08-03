"""
智能问答平台 - 聊天服务

负责会话/消息持久化与消息反馈落库。
"""

import json

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.chat import ChatMessage, ChatSession

logger = structlog.get_logger(__name__)


class ChatService:
    """聊天会话与消息服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_session(
        self,
        user_id: str,
        session_id: str | None = None,
        kb_ids: list[str] | None = None,
    ) -> ChatSession:
        """获取已有会话或新建会话。

        session_id 非空时按 id + user_id 校验归属，不存在或不归属则 NotFoundError。
        """
        if session_id:
            session = await self._get_session(session_id, user_id)
            return session

        session = ChatSession(
            user_id=user_id,
            kb_ids=",".join(kb_ids) if kb_ids else None,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info("chat_session_created", session_id=session.id, user_id=user_id)
        return session

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: list[dict[str, object]] | None = None,
        tokens_used: int | None = None,
        latency_ms: int | None = None,
    ) -> ChatMessage:
        """追加一条消息到会话，并递增会话消息计数。"""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources=(
                json.dumps(sources, ensure_ascii=False) if sources is not None else None
            ),
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
        self.db.add(message)

        # 递增会话消息计数
        session = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        sess = session.scalar_one_or_none()
        if sess is not None:
            sess.message_count = (sess.message_count or 0) + 1

        await self.db.commit()
        await self.db.refresh(message)

        logger.info(
            "chat_message_added",
            message_id=message.id,
            session_id=session_id,
            role=role,
        )
        return message

    async def save_feedback(
        self,
        message_id: str,
        user_id: str,
        is_liked: bool,
        feedback: str | None = None,
    ) -> ChatMessage:
        """保存消息反馈（点赞/点踩 + 文字反馈）。

        通过 join 会话校验消息归属当前用户，防越权改别人消息。
        """
        result = await self.db.execute(
            select(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(
                ChatMessage.id == message_id,
                ChatSession.user_id == user_id,
                ChatMessage.is_deleted.is_(False),
                ChatSession.is_deleted.is_(False),
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            raise NotFoundError("消息不存在或无权操作")

        message.is_liked = is_liked
        message.feedback = feedback
        await self.db.commit()
        await self.db.refresh(message)

        logger.info(
            "chat_feedback_saved",
            message_id=message_id,
            user_id=user_id,
            is_liked=is_liked,
        )
        return message

    async def list_sessions(self, user_id: str) -> list[ChatSession]:
        """列出当前用户的会话（按更新时间倒序）。"""
        result = await self.db.execute(
            select(ChatSession)
            .where(
                ChatSession.user_id == user_id,
                ChatSession.is_deleted.is_(False),
            )
            .order_by(ChatSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def delete_session(self, session_id: str, user_id: str) -> None:
        """软删会话及其消息。"""
        session = await self._get_session(session_id, user_id)
        session.is_deleted = True

        # 级联软删消息
        result = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == session_id,
                ChatMessage.is_deleted.is_(False),
            )
        )
        for msg in result.scalars().all():
            msg.is_deleted = True

        await self.db.commit()
        logger.info("chat_session_deleted", session_id=session_id, user_id=user_id)

    async def _get_session(self, session_id: str, user_id: str) -> ChatSession:
        """按 id + user_id 查会话，不存在或不归属则 NotFoundError。"""
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
                ChatSession.is_deleted.is_(False),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("会话不存在或无权操作")
        return session
