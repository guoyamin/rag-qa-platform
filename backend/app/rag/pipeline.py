"""
智能问答平台 - RAG Pipeline
完整的RAG问答流程
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.llm.base import BaseLLM, LLMConfig, LLMFactory, Message
from app.rag.retriever import RAGRetriever, SearchResult


class RAGPipeline:
    """RAG Pipeline"""

    # 系统提示词模板 - 针对企业知识库问答场景
    SYSTEM_PROMPT_TEMPLATE = """你是企业知识库问答平台的智能助手，专门回答关于企业知识库的问题。

你的知识来源于以下官方文档，回答时请严格基于提供的参考资料，不要编造信息。

回答要求：
1. 使用中文回答，语言简洁专业
2. 回答需要基于提供的参考资料，如果参考资料不足以回答问题，请明确告知
3. 涉及具体政策、流程时，引用具体的条款编号或文件名称
4. 对于不确定的信息，说明"根据现有资料，该问题可能需要进一步确认"
5. 回答末尾列出引用的参考资料

当前时间：{current_time}
"""

    # 问答提示词模板
    QA_PROMPT_TEMPLATE = """请参考以下资料回答问题：

{context}

---

用户问题：{question}

请基于上述资料，提供专业、准确的回答。如果资料中没有相关信息，请明确说明。"""

    def __init__(self, llm: BaseLLM | None = None):
        self.llm = llm or self._create_default_llm()
        self.retriever = RAGRetriever(llm=self.llm)

    def _create_default_llm(self) -> BaseLLM:
        """创建默认LLM实例"""
        config = LLMConfig(
            provider=settings.LLM_PROVIDER,
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        return LLMFactory.create(config)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算文本 token 数（流式模式无 usage 返回时使用）"""
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            # tiktoken 不可用时退化为粗略估算
            return len(text) // 2

    async def query(
        self,
        question: str,
        kb_ids: list[str] | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        执行RAG查询（非流式）

        Returns:
            {
                "answer": str,  # 回答内容
                "sources": list[dict],  # 引用来源
                "tokens_used": int,  # Token使用量
                "latency_ms": int,  # 响应延迟
            }
        """
        start_time = datetime.now(UTC)

        # 1. 检索相关文档
        search_result = await self.retriever.search(question, kb_ids)

        # 2. 构建上下文
        context = self._build_context(search_result)

        # 3. 构建提示词
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
            current_time=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        )
        prompt = self.QA_PROMPT_TEMPLATE.format(
            context=context,
            question=question,
        )

        # 4. 调用LLM
        messages = [Message(role="user", content=prompt)]

        if history:
            # 添加历史对话
            hist_messages = [
                Message(role=msg["role"], content=msg["content"])
                for msg in history[-4:]  # 只取最近4轮
            ]
            messages = hist_messages + messages

        response = await self.llm.chat(messages, system_prompt=system_prompt)

        # 5. 计算延迟
        latency = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

        # 6. 构建来源信息
        sources = self._build_sources(search_result)

        return {
            "answer": response.content,
            "sources": sources,
            "tokens_used": response.total_tokens or 0,
            "latency_ms": latency,
        }

    async def query_stream(
        self,
        question: str,
        kb_ids: list[str] | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        执行RAG查询（流式）

        Yields:
            {"type": "chunk", "content": str}  # 内容块
            {"type": "sources", "data": list[dict]}  # 来源信息
            {"type": "done", "tokens_used": int, "latency_ms": int}  # 完成
        """
        start_time = datetime.now(UTC)

        # 1. 检索相关文档
        search_result = await self.retriever.search(question, kb_ids)

        # 先发送来源信息
        sources = self._build_sources(search_result)
        yield {"type": "sources", "data": sources}

        # 2. 构建上下文
        context = self._build_context(search_result)

        # 3. 构建提示词
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
            current_time=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        )
        prompt = self.QA_PROMPT_TEMPLATE.format(
            context=context,
            question=question,
        )

        # 4. 流式调用LLM
        messages = [Message(role="user", content=prompt)]

        if history:
            hist_messages = [
                Message(role=msg["role"], content=msg["content"])
                for msg in history[-4:]
            ]
            messages = hist_messages + messages

        full_content = ""
        async for chunk in self.llm.chat_stream(messages, system_prompt=system_prompt):
            full_content += chunk
            yield {"type": "chunk", "content": chunk}

        # 5. 计算延迟
        latency = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

        # 发送完成信息（流式无 usage，用 tiktoken 估算）
        yield {
            "type": "done",
            "tokens_used": self.estimate_tokens(full_content),
            "latency_ms": latency,
        }

    def _build_context(self, search_result: SearchResult) -> str:
        """构建检索上下文"""
        if not search_result.chunks:
            return "未找到相关资料。"

        context_parts = []
        for i, chunk in enumerate(search_result.chunks, 1):
            context_parts.append(
                f"[资料 {i}] (来源: 文档ID {chunk.document_id}, 相似度: {chunk.score:.3f})\n"
                f"{chunk.content}\n"
            )

        return "\n".join(context_parts)

    def _build_sources(self, search_result: SearchResult) -> list[dict[str, Any]]:
        """构建来源信息"""
        sources = []
        for chunk in search_result.chunks:
            sources.append(
                {
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "score": round(chunk.score, 3),
                    "content_preview": (
                        chunk.content[:200] + "..."
                        if len(chunk.content) > 200
                        else chunk.content
                    ),
                }
            )
        return sources
