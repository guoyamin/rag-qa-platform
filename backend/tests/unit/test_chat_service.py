"""
聊天服务单元测试。
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User, UserAuthType, UserRole, UserStatus
from app.services.chat_service import ChatService


def _make_result(
    *,
    one_or_none: object = None,
    scalar: object = None,
    scalars_all: list[object] | None = None,
) -> MagicMock:
    """构造一个模拟的 SQLAlchemy Result 对象。"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = one_or_none
    result.scalar.return_value = scalar
    if scalars_all is not None:
        result.scalars.return_value.all.return_value = scalars_all
    return result


def _make_service() -> tuple[ChatService, MagicMock]:
    """构造一个带有 Mock AsyncSession 的 ChatService。"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return ChatService(db), db


def _make_user(uid: str = "user-1") -> User:
    user = User(
        username="tester",
        auth_type=UserAuthType.LOCAL,
        role=UserRole.STAFF,
        status=UserStatus.ACTIVE,
    )
    user.id = uid
    return user


def _make_session(
    sid: str = "sess-1", uid: str = "user-1", **overrides: object
) -> ChatSession:
    defaults: dict[str, object] = {
        "user_id": uid,
        "title": None,
        "kb_ids": None,
        "message_count": 0,
    }
    defaults.update(overrides)
    session = ChatSession(**defaults)  # type: ignore[arg-type]
    session.id = sid
    session.created_at = datetime.now(UTC)
    session.updated_at = datetime.now(UTC)
    return session


def _make_message(
    mid: str = "msg-1", sid: str = "sess-1", **overrides: object
) -> ChatMessage:
    defaults: dict[str, object] = {
        "session_id": sid,
        "role": "assistant",
        "content": "回答内容",
        "sources": None,
        "tokens_used": 10,
        "latency_ms": 100,
        "is_liked": None,
        "feedback": None,
    }
    defaults.update(overrides)
    message = ChatMessage(**defaults)  # type: ignore[arg-type]
    message.id = mid
    message.created_at = datetime.now(UTC)
    message.updated_at = datetime.now(UTC)
    return message


class TestGetOrCreateSession:
    """get_or_create_session 单元测试。"""

    async def test_no_session_id_creates_new_session(self):
        # Arrange
        service, db = _make_service()

        async def _refresh_set_id(obj: ChatSession) -> None:
            obj.id = "new-sess"

        db.refresh = AsyncMock(side_effect=_refresh_set_id)

        # Act
        result = await service.get_or_create_session(user_id="user-1", kb_ids=["kb-1"])

        # Assert
        assert result.id == "new-sess"
        assert result.user_id == "user-1"
        assert result.kb_ids == "kb-1"
        db.add.assert_called_once()
        assert db.commit.await_count == 1

    async def test_existing_session_id_returns_it(self):
        # Arrange
        service, db = _make_service()
        session = _make_session(sid="sess-1", uid="user-1")
        db.execute = AsyncMock(return_value=_make_result(one_or_none=session))

        # Act
        result = await service.get_or_create_session(
            user_id="user-1", session_id="sess-1"
        )

        # Assert
        assert result is session
        db.add.assert_not_called()

    async def test_session_id_not_found_raises(self):
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.get_or_create_session(user_id="user-1", session_id="missing")


class TestAddMessage:
    """add_message 单元测试。"""

    async def test_creates_message_and_increments_count(self):
        # Arrange
        service, db = _make_service()
        session = _make_session(sid="sess-1", message_count=3)
        db.execute = AsyncMock(return_value=_make_result(one_or_none=session))

        async def _refresh_set_id(obj: ChatMessage) -> None:
            obj.id = "new-msg"

        db.refresh = AsyncMock(side_effect=_refresh_set_id)

        # Act
        result = await service.add_message(
            session_id="sess-1", role="user", content="你好"
        )

        # Assert
        assert result.id == "new-msg"
        assert result.role == "user"
        assert result.content == "你好"
        assert session.message_count == 4  # 3 -> 4
        db.add.assert_called_once()
        assert db.commit.await_count == 1

    async def test_creates_message_with_sources_serialized(self):
        # Arrange
        service, db = _make_service()
        session = _make_session()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=session))
        db.refresh = AsyncMock()

        # Act
        await service.add_message(
            session_id="sess-1",
            role="assistant",
            content="回答",
            sources=[{"document_id": "d1", "score": 0.9}],
        )

        # Assert
        added = db.add.call_args[0][0]
        assert added.sources is not None
        assert "document_id" in added.sources  # JSON 字符串


class TestSaveFeedback:
    """save_feedback 单元测试。"""

    async def test_success_updates_is_liked_and_feedback(self):
        # Arrange
        service, db = _make_service()
        message = _make_message(mid="msg-1", is_liked=None, feedback=None)
        db.execute = AsyncMock(return_value=_make_result(one_or_none=message))
        db.refresh = AsyncMock()

        # Act
        result = await service.save_feedback(
            message_id="msg-1",
            user_id="user-1",
            is_liked=True,
            feedback="有帮助",
        )

        # Assert
        assert result.is_liked is True
        assert result.feedback == "有帮助"
        assert db.commit.await_count == 1

    async def test_message_not_found_or_not_owned_raises(self):
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.save_feedback(
                message_id="missing", user_id="user-1", is_liked=False
            )


class TestListSessions:
    """list_sessions 单元测试。"""

    async def test_returns_user_sessions(self):
        # Arrange
        service, db = _make_service()
        s1 = _make_session(sid="s1", uid="user-1")
        s2 = _make_session(sid="s2", uid="user-1")
        db.execute = AsyncMock(return_value=_make_result(scalars_all=[s1, s2]))

        # Act
        result = await service.list_sessions(user_id="user-1")

        # Assert
        assert len(result) == 2
        assert result[0].id == "s1"


class TestDeleteSession:
    """delete_session 单元测试。"""

    async def test_success_soft_deletes_session_and_messages(self):
        # Arrange
        service, db = _make_service()
        session = _make_session(sid="sess-1", uid="user-1")
        msg1 = _make_message(mid="m1", sid="sess-1")
        msg2 = _make_message(mid="m2", sid="sess-1")
        db.execute = AsyncMock(
            side_effect=[
                _make_result(one_or_none=session),  # _get_session
                _make_result(scalars_all=[msg1, msg2]),  # messages
            ]
        )

        # Act
        await service.delete_session(session_id="sess-1", user_id="user-1")

        # Assert
        assert session.is_deleted is True
        assert msg1.is_deleted is True
        assert msg2.is_deleted is True
        assert db.commit.await_count == 1

    async def test_session_not_found_raises(self):
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.delete_session(session_id="missing", user_id="user-1")
