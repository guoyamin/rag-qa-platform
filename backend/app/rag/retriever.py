"""
智能问答平台 - RAG检索模块
"""

import asyncio
import re
from typing import Any

from app.core.config import settings
from app.llm.base import BaseLLM

# kb_id 仅允许 UUID 形态字符，防止 Milvus filter 表达式注入
_KB_ID_RE = re.compile(r"^[0-9a-fA-F-]{1,64}$")


class DocumentChunk:
    """文档分块"""

    def __init__(
        self,
        id: str,
        content: str,
        document_id: str,
        chunk_index: int,
        score: float = 0.0,
    ):
        self.id = id
        self.content = content
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.score = score


class SearchResult:
    """搜索结果"""

    def __init__(self, chunks: list[DocumentChunk], total: int = 0):
        self.chunks = chunks
        self.total = total


class RAGRetriever:
    """RAG检索器"""

    def __init__(self, llm: BaseLLM | None = None):
        self.llm = llm
        self._milvus_client: Any = None

    @property
    def milvus_client(self) -> Any:
        """懒加载Milvus客户端"""
        if self._milvus_client is None:
            from pymilvus import MilvusClient

            self._milvus_client = MilvusClient(
                uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            )
        return self._milvus_client

    async def search(
        self,
        query: str,
        kb_ids: list[str] | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> SearchResult:
        """
        向量检索

        Args:
            query: 查询文本
            kb_ids: 知识库ID列表，None表示全部
            top_k: 返回数量
            similarity_threshold: 相似度阈值
        """
        top_k = top_k or settings.RAG_TOP_K
        threshold = similarity_threshold or settings.RAG_SIMILARITY_THRESHOLD

        # 1. 生成查询向量
        query_embedding = await self._embed_query(query)

        # 2. 执行向量搜索
        collection = settings.MILVUS_COLLECTION

        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10},
        }

        # 构建过滤条件（校验 kb_id，防止 filter 表达式注入）
        filter_expr = None
        if kb_ids:
            safe_ids = [kb for kb in kb_ids if _KB_ID_RE.match(kb)]
            if safe_ids:
                kb_filter = " || ".join([f'kb_id == "{kb}"' for kb in safe_ids])
                filter_expr = f"({kb_filter})"

        # MilvusClient 为同步阻塞客户端，放到线程池避免阻塞事件循环
        results = await asyncio.to_thread(
            self.milvus_client.search,
            collection_name=collection,
            data=[query_embedding],
            limit=top_k * 2,  # 多取一些，后续过滤
            search_params=search_params,
            filter=filter_expr,
            output_fields=["id", "content", "document_id", "chunk_index", "kb_id"],
        )

        # 3. 解析结果
        chunks = []
        for result in results[0]:
            if result["distance"] < threshold:
                continue

            chunk = DocumentChunk(
                id=result["id"],
                content=result["entity"]["content"],
                document_id=result["entity"]["document_id"],
                chunk_index=result["entity"]["chunk_index"],
                score=result["distance"],
            )
            chunks.append(chunk)

        # 按相似度排序并截断
        chunks.sort(key=lambda x: x.score, reverse=True)
        chunks = chunks[:top_k]

        return SearchResult(chunks=chunks, total=len(chunks))

    async def hybrid_search(
        self,
        query: str,
        kb_ids: list[str] | None = None,
        top_k: int | None = None,
    ) -> SearchResult:
        """
        混合检索：向量检索 + 关键词检索
        """
        # TODO: 实现混合检索
        # 1. 向量检索
        vector_results = await self.search(query, kb_ids, top_k)

        # 2. 关键词检索（使用BM25或简单匹配）
        # TODO: 接入全文搜索引擎如Elasticsearch

        return vector_results

    async def _embed_query(self, query: str) -> list[float]:
        """将查询文本转为向量"""
        if not self.llm:
            raise RuntimeError("LLM实例未初始化")

        embeddings = await self.llm.embedding([query])
        return embeddings[0]

    async def add_document_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        kb_id: str,
    ) -> bool:
        """向Milvus添加文档分块"""
        collection = settings.MILVUS_COLLECTION

        # 准备数据
        entities = []
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            entities.append(
                {
                    "id": chunk.id,
                    "vector": embedding,
                    "content": chunk.content,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "kb_id": kb_id,
                }
            )

        # 插入数据（同步调用放线程池）
        await asyncio.to_thread(
            self.milvus_client.insert,
            collection_name=collection,
            data=entities,
        )

        return True

    async def delete_document_chunks(self, document_id: str) -> bool:
        """删除文档的所有分块"""
        collection = settings.MILVUS_COLLECTION

        # 校验 document_id，防止 filter 注入
        if not _KB_ID_RE.match(document_id):
            raise ValueError("非法的 document_id")

        await asyncio.to_thread(
            self.milvus_client.delete,
            collection_name=collection,
            filter=f'document_id == "{document_id}"',
        )

        return True
