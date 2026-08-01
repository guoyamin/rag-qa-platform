"""
RAG Pipeline单元测试
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.llm.base import LLMResponse
from app.rag.pipeline import RAGPipeline
from app.rag.retriever import DocumentChunk, SearchResult


async def _async_gen(items):
    """将列表包装为异步生成器，用于模拟 chat_stream。"""
    for item in items:
        yield item


class _RaisingAsyncIter:
    """首次 __anext__ 即抛出异常的异步迭代器，用于模拟流式错误。"""

    def __init__(self, exc):
        self._exc = exc

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise self._exc


class TestRAGPipeline:
    """RAG Pipeline测试"""

    @pytest.fixture
    def mock_llm(self):
        """模拟LLM"""
        llm = MagicMock()
        llm.chat = AsyncMock()
        llm.chat_stream = AsyncMock()
        llm.embedding = AsyncMock()
        return llm

    @pytest.fixture
    def mock_retriever(self):
        """模拟检索器"""
        retriever = MagicMock()
        retriever.search = AsyncMock()
        return retriever

    @pytest.fixture
    def pipeline(self, mock_llm, mock_retriever):
        """构造注入 mock 依赖的 pipeline 实例"""
        p = RAGPipeline(llm=mock_llm)
        p.retriever = mock_retriever
        return p

    @pytest.mark.asyncio
    async def test_query_with_results(self, mock_llm, mock_retriever):
        """测试有检索结果的查询"""
        # 模拟检索结果
        chunk = DocumentChunk(
            id="chunk-1",
            content="查询制度需要登录权限",
            document_id="doc-1",
            chunk_index=0,
            score=0.95,
        )
        search_result = SearchResult(chunks=[chunk], total=1)
        mock_retriever.search.return_value = search_result

        # 模拟LLM响应
        mock_llm.chat.return_value = LLMResponse(
            content="根据资料，查询制度需要登录权限。",
            total_tokens=100,
        )

        pipeline = RAGPipeline(llm=mock_llm)
        pipeline.retriever = mock_retriever

        result = await pipeline.query("如何查询公司制度？")

        assert "answer" in result
        assert "sources" in result
        assert result["tokens_used"] == 100
        assert len(result["sources"]) == 1

    @pytest.mark.asyncio
    async def test_query_without_results(self, mock_llm, mock_retriever):
        """测试无检索结果的查询"""
        search_result = SearchResult(chunks=[], total=0)
        mock_retriever.search.return_value = search_result

        mock_llm.chat.return_value = LLMResponse(
            content="未找到相关资料，无法回答您的问题。",
            total_tokens=50,
        )

        pipeline = RAGPipeline(llm=mock_llm)
        pipeline.retriever = mock_retriever

        result = await pipeline.query("一个不存在的问题？")

        assert result["answer"] is not None
        assert len(result["sources"]) == 0

    # ---------- __init__ ----------

    def test_init_with_llm_does_not_invoke_factory(self):
        """提供 LLM 时不应调用工厂"""
        llm = MagicMock()
        with patch("app.rag.pipeline.LLMFactory.create") as mock_create:
            pipeline = RAGPipeline(llm=llm)
        mock_create.assert_not_called()
        assert pipeline.llm is llm
        assert pipeline.retriever is not None
        assert pipeline.retriever.llm is llm

    def test_init_without_llm_invokes_factory_with_settings(self):
        """未提供 LLM 时应基于 settings 通过工厂创建"""
        fake_llm = MagicMock()
        with patch(
            "app.rag.pipeline.LLMFactory.create", return_value=fake_llm
        ) as mock_create:
            pipeline = RAGPipeline(llm=None)
        mock_create.assert_called_once()
        config = mock_create.call_args.args[0]
        assert config.provider == settings.LLM_PROVIDER
        assert config.model == settings.LLM_MODEL
        assert pipeline.llm is fake_llm
        assert pipeline.retriever.llm is fake_llm

    # ---------- estimate_tokens ----------

    def test_estimate_tokens_tiktoken_available_returns_encoded_length(self):
        """tiktoken 可用时返回精确 token 数"""
        fake_encoder = MagicMock()
        fake_encoder.encode.return_value = ["t1", "t2", "t3"]
        fake_tiktoken = MagicMock()
        fake_tiktoken.get_encoding.return_value = fake_encoder
        with patch.dict(sys.modules, {"tiktoken": fake_tiktoken}):
            result = RAGPipeline.estimate_tokens("any text")
        fake_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
        fake_encoder.encode.assert_called_once_with("any text")
        assert result == 3

    def test_estimate_tokens_tiktoken_missing_returns_half_length(self):
        """tiktoken 不可用时退化为字符数一半"""
        with patch.dict(sys.modules, {"tiktoken": None}):
            result = RAGPipeline.estimate_tokens("hello world!")
        assert result == 6  # len 12 // 2

    def test_estimate_tokens_get_encoding_error_returns_half_length(self):
        """get_encoding 抛异常时退化为字符数一半"""
        fake_tiktoken = MagicMock()
        fake_tiktoken.get_encoding.side_effect = OSError("model not found")
        with patch.dict(sys.modules, {"tiktoken": fake_tiktoken}):
            result = RAGPipeline.estimate_tokens("abcdef")
        assert result == 3  # len 6 // 2

    def test_estimate_tokens_empty_text_returns_zero(self):
        """空文本 token 数为 0"""
        with patch.dict(sys.modules, {"tiktoken": None}):
            assert RAGPipeline.estimate_tokens("") == 0

    # ---------- _build_context ----------

    def test_build_context_no_chunks_returns_not_found_message(self, pipeline):
        """无检索分块时返回未找到提示"""
        result = pipeline._build_context(SearchResult(chunks=[], total=0))
        assert result == "未找到相关资料。"

    def test_build_context_single_chunk_includes_metadata_and_content(self, pipeline):
        """单分块上下文包含序号、文档ID、相似度与内容"""
        chunk = DocumentChunk(
            id="c1",
            content="企业制度",
            document_id="doc-1",
            chunk_index=0,
            score=0.951,
        )
        result = pipeline._build_context(SearchResult(chunks=[chunk], total=1))
        assert "[资料 1]" in result
        assert "doc-1" in result
        assert "0.951" in result
        assert "企业制度" in result

    def test_build_context_multiple_chunks_joined_with_newline(self, pipeline):
        """多分块按换行拼接且序号递增"""
        chunks = [
            DocumentChunk(
                id="c1", content="甲", document_id="d1", chunk_index=0, score=0.9
            ),
            DocumentChunk(
                id="c2", content="乙", document_id="d2", chunk_index=1, score=0.8
            ),
        ]
        result = pipeline._build_context(SearchResult(chunks=chunks, total=2))
        assert "[资料 1]" in result
        assert "[资料 2]" in result
        assert "甲" in result
        assert "乙" in result

    # ---------- _build_sources ----------

    def test_build_sources_no_chunks_returns_empty_list(self, pipeline):
        """无分块时来源列表为空"""
        assert pipeline._build_sources(SearchResult(chunks=[], total=0)) == []

    def test_build_sources_short_content_returns_full_preview(self, pipeline):
        """短内容预览返回完整内容"""
        chunk = DocumentChunk(
            id="c1", content="短内容", document_id="d1", chunk_index=2, score=0.91234
        )
        result = pipeline._build_sources(SearchResult(chunks=[chunk], total=1))
        assert result == [
            {
                "document_id": "d1",
                "chunk_index": 2,
                "score": 0.912,
                "content_preview": "短内容",
            }
        ]

    def test_build_sources_content_exactly_200_chars_not_truncated(self, pipeline):
        """200 字符内容不截断"""
        content = "b" * 200
        chunk = DocumentChunk(
            id="c1", content=content, document_id="d1", chunk_index=0, score=0.5
        )
        result = pipeline._build_sources(SearchResult(chunks=[chunk], total=1))
        assert result[0]["content_preview"] == content

    def test_build_sources_long_content_truncated_to_200_chars(self, pipeline):
        """超过 200 字符的内容截断为 200 字符加省略号"""
        content = "a" * 250
        chunk = DocumentChunk(
            id="c1", content=content, document_id="d1", chunk_index=0, score=1.0
        )
        result = pipeline._build_sources(SearchResult(chunks=[chunk], total=1))
        assert result[0]["content_preview"] == "a" * 200 + "..."

    def test_build_sources_score_rounded_to_three_decimals(self, pipeline):
        """相似度保留三位小数"""
        chunk = DocumentChunk(
            id="c1", content="x", document_id="d1", chunk_index=0, score=0.123456
        )
        result = pipeline._build_sources(SearchResult(chunks=[chunk], total=1))
        assert result[0]["score"] == 0.123

    # ---------- query ----------

    @pytest.mark.asyncio
    async def test_query_forwards_question_and_kb_ids_to_retriever(
        self, pipeline, mock_llm, mock_retriever
    ):
        """query 将问题与 kb_ids 透传给检索器"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat.return_value = LLMResponse(content="ok", total_tokens=1)
        kb_ids = ["kb-1", "kb-2"]
        await pipeline.query("问题", kb_ids=kb_ids)
        mock_retriever.search.assert_awaited_once_with("问题", kb_ids)

    @pytest.mark.asyncio
    async def test_query_without_history_sends_single_user_message(
        self, pipeline, mock_llm, mock_retriever
    ):
        """无历史时只发送一条 user 消息"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat.return_value = LLMResponse(content="ok", total_tokens=1)
        await pipeline.query("问题")
        messages = mock_llm.chat.call_args.args[0]
        assert len(messages) == 1
        assert messages[0].role == "user"

    @pytest.mark.asyncio
    async def test_query_with_history_prepends_history_messages(
        self, pipeline, mock_llm, mock_retriever
    ):
        """有历史时将历史消息前置"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat.return_value = LLMResponse(content="ok", total_tokens=1)
        history = [
            {"role": "user", "content": "历史问"},
            {"role": "assistant", "content": "历史答"},
        ]
        await pipeline.query("当前问", history=history)
        messages = mock_llm.chat.call_args.args[0]
        assert len(messages) == 3
        assert messages[0].content == "历史问"
        assert messages[0].role == "user"
        assert messages[1].content == "历史答"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"

    @pytest.mark.asyncio
    async def test_query_history_longer_than_four_truncated_to_four(
        self, pipeline, mock_llm, mock_retriever
    ):
        """历史超过 4 条时只取最近 4 条"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat.return_value = LLMResponse(content="ok", total_tokens=1)
        history = [{"role": "user", "content": f"q{i}"} for i in range(6)]
        await pipeline.query("当前", history=history)
        messages = mock_llm.chat.call_args.args[0]
        assert len(messages) == 5  # 最近4条历史 + 1条新问题
        assert messages[0].content == "q2"  # history[-4]
        assert messages[3].content == "q5"
        assert messages[4].role == "user"

    @pytest.mark.asyncio
    async def test_query_total_tokens_none_defaults_to_zero(
        self, pipeline, mock_llm, mock_retriever
    ):
        """LLM 未返回 token 数时默认为 0"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat.return_value = LLMResponse(content="ok", total_tokens=None)
        result = await pipeline.query("问题")
        assert result["tokens_used"] == 0

    @pytest.mark.asyncio
    async def test_query_passes_system_prompt_to_llm(
        self, pipeline, mock_llm, mock_retriever
    ):
        """query 向 LLM 传递系统提示词"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat.return_value = LLMResponse(content="ok", total_tokens=1)
        await pipeline.query("问题")
        system_prompt = mock_llm.chat.call_args.kwargs["system_prompt"]
        assert "企业知识库" in system_prompt
        assert "当前时间" in system_prompt

    @pytest.mark.asyncio
    async def test_query_propagates_retriever_error(
        self, pipeline, mock_llm, mock_retriever
    ):
        """检索器抛错时 query 向上传播且不调用 LLM"""
        mock_retriever.search.side_effect = RuntimeError("milvus down")
        with pytest.raises(RuntimeError, match="milvus down"):
            await pipeline.query("问题")
        mock_llm.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_propagates_llm_error(self, pipeline, mock_llm, mock_retriever):
        """LLM 抛错时 query 向上传播"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat.side_effect = RuntimeError("llm timeout")
        with pytest.raises(RuntimeError, match="llm timeout"):
            await pipeline.query("问题")

    # ---------- query_stream ----------

    @pytest.mark.asyncio
    async def test_query_stream_yields_sources_chunks_then_done(
        self, pipeline, mock_llm, mock_retriever
    ):
        """流式查询依次产出 sources/chunk/done"""
        chunk = DocumentChunk(
            id="c1", content="资料", document_id="d1", chunk_index=0, score=0.9
        )
        mock_retriever.search.return_value = SearchResult(chunks=[chunk], total=1)
        mock_llm.chat_stream = MagicMock(return_value=_async_gen(["你好", "世界"]))
        events = [e async for e in pipeline.query_stream("问题")]
        assert [e["type"] for e in events] == ["sources", "chunk", "chunk", "done"]
        assert events[0]["data"][0]["document_id"] == "d1"
        assert events[1]["content"] == "你好"
        assert events[2]["content"] == "世界"
        assert events[3]["tokens_used"] == RAGPipeline.estimate_tokens("你好世界")
        assert isinstance(events[3]["latency_ms"], int)
        assert events[3]["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_query_stream_no_chunks_yields_empty_sources(
        self, pipeline, mock_llm, mock_retriever
    ):
        """无检索结果时 sources 为空列表"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat_stream = MagicMock(return_value=_async_gen(["无资料"]))
        events = [e async for e in pipeline.query_stream("问题")]
        assert events[0]["type"] == "sources"
        assert events[0]["data"] == []
        assert events[-1]["type"] == "done"

    @pytest.mark.asyncio
    async def test_query_stream_with_history_prepends_history(
        self, pipeline, mock_llm, mock_retriever
    ):
        """流式查询同样前置历史消息"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat_stream = MagicMock(return_value=_async_gen(["答"]))
        history = [
            {"role": "user", "content": "h1"},
            {"role": "assistant", "content": "h2"},
        ]
        _ = [e async for e in pipeline.query_stream("q", history=history)]
        messages = mock_llm.chat_stream.call_args.args[0]
        assert len(messages) == 3
        assert messages[0].content == "h1"

    @pytest.mark.asyncio
    async def test_query_stream_forwards_kb_ids_to_retriever(
        self, pipeline, mock_llm, mock_retriever
    ):
        """流式查询透传 kb_ids 给检索器"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat_stream = MagicMock(return_value=_async_gen(["x"]))
        kb_ids = ["kb-9"]
        _ = [e async for e in pipeline.query_stream("q", kb_ids=kb_ids)]
        mock_retriever.search.assert_awaited_once_with("q", kb_ids)

    @pytest.mark.asyncio
    async def test_query_stream_propagates_retriever_error(
        self, pipeline, mock_llm, mock_retriever
    ):
        """检索器抛错时流式查询向上传播"""
        mock_retriever.search.side_effect = RuntimeError("search failed")
        with pytest.raises(RuntimeError, match="search failed"):
            _ = [e async for e in pipeline.query_stream("q")]

    @pytest.mark.asyncio
    async def test_query_stream_propagates_llm_stream_error(
        self, pipeline, mock_llm, mock_retriever
    ):
        """流式输出抛错时向上传播"""
        mock_retriever.search.return_value = SearchResult(chunks=[], total=0)
        mock_llm.chat_stream = MagicMock(
            return_value=_RaisingAsyncIter(RuntimeError("stream broke"))
        )
        with pytest.raises(RuntimeError, match="stream broke"):
            _ = [e async for e in pipeline.query_stream("q")]
