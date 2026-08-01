"""
智能问答平台 - 聊天API路由
"""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db, get_ws_user
from app.models.user import User
from app.rag.pipeline import RAGPipeline
from app.schemas import (
    ChatFeedbackRequest,
    ChatRequest,
    DataResponse,
    ListResponse,
    ResponseBase,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["智能问答"])

# 懒加载 RAG Pipeline（避免启动时就需要 LLM API Key）
_rag_pipeline: RAGPipeline | None = None


def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


@router.post("/completions", response_model=DataResponse)
async def chat_completion(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
) -> DataResponse:
    """
    智能问答（非流式）

    - **message**: 用户问题
    - **session_id**: 会话ID，为空则新建会话
    - **kb_ids**: 指定知识库ID列表
    """
    result = await get_rag_pipeline().query(
        question=request.message,
        kb_ids=request.kb_ids,
    )

    return DataResponse(data=result)


@router.post("/completions/stream")
async def chat_completion_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """
    智能问答（流式）
    使用SSE格式返回
    """

    async def event_generator() -> AsyncIterator[str]:
        async for chunk in get_rag_pipeline().query_stream(
            question=request.message,
            kb_ids=request.kb_ids,
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket) -> None:
    """WebSocket聊天接口"""
    user = await get_ws_user(websocket)
    if not user:
        await websocket.close(code=4001, reason="未授权")
        return

    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            kb_ids = data.get("kb_ids")

            # 发送来源信息
            pipeline = get_rag_pipeline()
            search_result = await pipeline.retriever.search(message, kb_ids)
            sources = pipeline._build_sources(search_result)
            await websocket.send_json({"type": "sources", "data": sources})

            # 流式返回回答
            context = pipeline._build_context(search_result)
            system_prompt = pipeline.SYSTEM_PROMPT_TEMPLATE.format(
                current_time=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            )
            prompt = pipeline.QA_PROMPT_TEMPLATE.format(
                context=context,
                question=message,
            )

            from app.llm.base import Message

            messages = [Message(role="user", content=prompt)]

            full_content = ""
            stream = pipeline.llm.chat_stream(messages, system_prompt=system_prompt)
            async for chunk in stream:
                full_content += chunk
                await websocket.send_json({"type": "chunk", "content": chunk})

            await websocket.send_json(
                {"type": "done", "tokens_used": pipeline.estimate_tokens(full_content)}
            )

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("websocket_chat_error")
        await websocket.send_json(
            {"type": "error", "message": "服务处理出错，请稍后重试"}
        )
        await websocket.close()


@router.get("/sessions", response_model=ListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ListResponse:
    """获取用户会话列表"""
    # TODO: 实现会话查询
    return ListResponse(data=[], total=0)


@router.delete("/sessions/{session_id}", response_model=ResponseBase)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseBase:
    """删除会话"""
    # TODO: 实现删除
    return ResponseBase(message="删除成功")


@router.post("/feedback", response_model=ResponseBase)
async def submit_feedback(
    feedback: ChatFeedbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseBase:
    """提交消息反馈"""
    # TODO: 保存反馈
    return ResponseBase(message="反馈提交成功")
