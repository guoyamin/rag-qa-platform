"""
聊天 API 集成测试。

覆盖 /api/v1/chat 下的 completions / stream / sessions / feedback / ws，
使用真实测试库验证 SQL，mock 外部依赖（LLM/Milvus/Vault 由 conftest autouse fixture 注入；
RAG Pipeline 注入 mock LLM 实例，Milvus 经 conftest 全局 mock）。遵循 AAA 模式，
每测试独立内存库。

WebSocket 测试说明：httpx 不支持 WS，starlette TestClient 在独立 portal 事件循环上运行
ASGI 应用而 aiosqlite 连接绑定创建它的循环（conftest 已实测死锁）。故 _WSSession 在
测试同一事件循环内直接调用 app(scope, receive, send)，绕过 portal，避免跨循环死锁。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.llm.base import LLMResponse
from app.main import app
from app.models.user import User, UserAuthType, UserRole, UserStatus
from app.rag.pipeline import RAGPipeline

VALID_PASSWORD = "Passw0rd!"
_STREAM_CHUNKS = ("模拟", "回答", "内容")


async def _create_user_and_token(
    db_session: AsyncSession,
    username: str = "chatuser",
    status: UserStatus = UserStatus.ACTIVE,
) -> tuple[User, str]:
    """在测试库创建用户并签发 access token。"""
    user = User(
        username=username,
        display_name=username,
        hashed_password=get_password_hash(VALID_PASSWORD),
        auth_type=UserAuthType.LOCAL,
        role=UserRole.STAFF,
        status=status,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, create_access_token(user.id)


@pytest.fixture
def mock_llm() -> MagicMock:
    """Mock LLM：chat 返回固定回答，chat_stream 返回固定分块，embedding 返回固定向量。"""
    llm = MagicMock()
    llm.chat = AsyncMock(
        return_value=LLMResponse(content="这是模拟回答", total_tokens=42)
    )
    llm.embedding = AsyncMock(return_value=[[0.1] * 1536])

    async def _fake_stream(*_args: Any, **_kwargs: Any) -> Any:
        for chunk in _STREAM_CHUNKS:
            yield chunk

    llm.chat_stream = MagicMock(side_effect=_fake_stream)
    return llm


@pytest.fixture
def rag_pipeline(monkeypatch: pytest.MonkeyPatch, mock_llm: MagicMock) -> RAGPipeline:
    """注入带 mock LLM 的 RAGPipeline 作为 chat 模块单例（Milvus 由 conftest mock）。"""
    pipeline = RAGPipeline(llm=mock_llm)
    monkeypatch.setattr("app.api.v1.chat._rag_pipeline", pipeline)
    return pipeline


class _WSSession:
    """轻量 ASGI WebSocket 测试客户端：同事件循环内直接调用 app(scope, receive, send)。"""

    def __init__(self, path: str, query: str = "") -> None:
        self._inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._outbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self.close_code: int | None = None
        self.accepted: bool = False
        self.scope: dict[str, Any] = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 0),
            "server": ("test", 80),
            "subprotocols": [],
            "state": {},
            "extensions": {},
        }

    async def _receive(self) -> dict[str, Any]:
        return await self._inbox.get()

    async def _send(self, message: dict[str, Any]) -> None:
        await self._outbox.put(message)

    async def _recv(self) -> dict[str, Any]:
        """从 outbox 取一条消息；超时则检查 app 任务是否已异常退出。"""
        try:
            return await asyncio.wait_for(self._outbox.get(), timeout=10.0)
        except TimeoutError:
            if self._task is not None and self._task.done():
                exc = self._task.exception()
                if exc:
                    raise exc from None
            raise

    async def connect(self) -> _WSSession:
        await self._inbox.put({"type": "websocket.connect"})
        self._task = asyncio.create_task(app(self.scope, self._receive, self._send))
        msg = await self._recv()
        if msg["type"] == "websocket.close":
            self.close_code = msg.get("code", 1000)
            assert self._task is not None
            await self._task
            return self
        assert msg["type"] == "websocket.accept", f"unexpected: {msg}"
        self.accepted = True
        return self

    async def send_json(self, data: Any) -> None:
        await self._inbox.put(
            {"type": "websocket.receive", "text": json.dumps(data, ensure_ascii=False)}
        )

    async def receive_json(self) -> dict[str, Any]:
        msg = await self._recv()
        if msg["type"] == "websocket.close":
            self.close_code = msg.get("code", 1000)
            raise ConnectionError(f"websocket closed: {self.close_code}")
        assert msg["type"] == "websocket.send", f"unexpected: {msg}"
        return json.loads(msg["text"])

    async def close(self) -> None:
        if self._task is None:
            return
        await self._inbox.put({"type": "websocket.disconnect", "code": 1000})
        with contextlib.suppress(Exception):
            await self._task


@pytest.mark.integration
class TestChatAPI:
    """聊天接口集成测试。"""

    # --- POST /chat/completions ---

    async def test_completion_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/chat/completions", json={"message": "公司制度怎么查"}
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_completion_invalid_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/chat/completions",
            json={"message": "知识库"},
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_completion_disabled_user_returns_403(self, client, db_session):
        # Arrange
        _, token = await _create_user_and_token(
            db_session, username="disabled", status=UserStatus.DISABLED
        )
        # Act
        resp = await client.post(
            "/api/v1/chat/completions",
            json={"message": "知识库"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTHORIZATION_ERROR"

    async def test_completion_success_returns_answer(
        self, client, db_session, rag_pipeline
    ):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="chatter")
        # Act
        resp = await client.post(
            "/api/v1/chat/completions",
            json={"message": "公司制度怎么查"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["answer"] == "这是模拟回答"
        assert data["sources"] == []
        assert data["tokens_used"] == 42
        assert isinstance(data["latency_ms"], int)

    async def test_completion_empty_message_returns_422(
        self, client, db_session, rag_pipeline
    ):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="empty")
        # Act
        resp = await client.post(
            "/api/v1/chat/completions",
            json={"message": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 422

    async def test_completion_message_too_long_returns_422(
        self, client, db_session, rag_pipeline
    ):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="toolong")
        # Act
        resp = await client.post(
            "/api/v1/chat/completions",
            json={"message": "x" * 5001},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 422

    async def test_completion_with_kb_ids_success(
        self, client, db_session, rag_pipeline
    ):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="kbuser")
        # Act
        resp = await client.post(
            "/api/v1/chat/completions",
            json={
                "message": "知识库",
                "kb_ids": ["550e8400-e29b-41d4-a716-446655440000"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 200
        assert resp.json()["data"]["answer"] == "这是模拟回答"

    # --- POST /chat/completions/stream ---

    async def test_stream_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/chat/completions/stream", json={"message": "知识库"}
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_stream_success_returns_sse_events(
        self, client, db_session, rag_pipeline
    ):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="streamer")
        # Act
        resp = await client.post(
            "/api/v1/chat/completions/stream",
            json={"message": "知识库"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 200
        text = resp.text
        assert "data: " in text
        assert '"type": "sources"' in text
        assert '"type": "chunk"' in text
        assert '"type": "done"' in text
        assert "data: [DONE]" in text

    # --- GET /chat/sessions ---

    async def test_list_sessions_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.get("/api/v1/chat/sessions")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_list_sessions_returns_empty(self, client, db_session):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="sessions")
        # Act
        resp = await client.get(
            "/api/v1/chat/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["total"] == 0

    # --- DELETE /chat/sessions/{session_id} ---

    async def test_delete_session_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.delete("/api/v1/chat/sessions/some-id")
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_delete_session_returns_success(self, client, db_session):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="deleter")
        # Act
        resp = await client.delete(
            "/api/v1/chat/sessions/some-id",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 200
        assert resp.json()["message"] == "删除成功"

    # --- POST /chat/feedback ---

    async def test_feedback_without_token_returns_401(self, client):
        # Arrange / Act
        resp = await client.post(
            "/api/v1/chat/feedback",
            json={"message_id": "msg-1", "is_liked": True},
        )
        # Assert
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTHENTICATION_ERROR"

    async def test_feedback_success_returns_message(self, client, db_session):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="feedback")
        # Act
        resp = await client.post(
            "/api/v1/chat/feedback",
            json={"message_id": "msg-1", "is_liked": True, "feedback": "很有帮助"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 200
        assert resp.json()["message"] == "反馈提交成功"

    async def test_feedback_missing_message_id_returns_422(self, client, db_session):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="fb422")
        # Act
        resp = await client.post(
            "/api/v1/chat/feedback",
            json={"is_liked": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Assert
        assert resp.status_code == 422

    # --- WS /chat/ws ---

    async def test_ws_without_token_closes_4001(self):
        # Arrange / Act
        ws = _WSSession("/api/v1/chat/ws")
        await ws.connect()
        # Assert
        assert not ws.accepted
        assert ws.close_code == 4001

    async def test_ws_invalid_token_closes_4001(self):
        # Arrange / Act
        ws = _WSSession("/api/v1/chat/ws", query="token=invalid.token.here")
        await ws.connect()
        # Assert
        assert not ws.accepted
        assert ws.close_code == 4001

    async def test_ws_valid_token_streams_response(
        self, client, db_session, rag_pipeline
    ):
        # Arrange
        _, token = await _create_user_and_token(db_session, username="wsuser")
        ws = _WSSession("/api/v1/chat/ws", query=f"token={token}")
        await ws.connect()
        # Act
        await ws.send_json({"message": "公司制度怎么查"})
        sources = await ws.receive_json()
        chunks = [(await ws.receive_json())["content"] for _ in _STREAM_CHUNKS]
        done = await ws.receive_json()
        await ws.close()
        # Assert
        assert ws.accepted
        assert sources["type"] == "sources"
        assert sources["data"] == []
        assert chunks == list(_STREAM_CHUNKS)
        assert done["type"] == "done"
        assert isinstance(done["tokens_used"], int)
        assert done["tokens_used"] > 0
