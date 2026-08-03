# RAG 检索核心模块

> 路径：`backend/app/rag/` · 路由定位见 [module-map](../architecture/module-map.md) · AI 工作指令见 `backend/app/rag/AGENTS.md`
>
> 本文档是**模块资产**（设计与原理）。改这个模块前先读完。

## 定位

平台的核心问答能力。把用户提问 → 检索企业知识库 → 基于 retrieved 上下文让 LLM 生成 grounded 回答。这是 "RAG" 中的 R（检索）+ G（生成）编排层。

## 文件与类

| 文件 | 类 | 职责 |
|---|---|---|
| `pipeline.py` | `RAGPipeline` | RAG 全流程编排：检索→构建上下文→提示词→调 LLM→返回 |
| `retriever.py` | `RAGRetriever` | Milvus 向量检索 + 文档分块读写 |
| `retriever.py` | `DocumentChunk` / `SearchResult` | 检索结果数据结构 |

## 数据流

### 问答流程（`query` 非流式 / `query_stream` 流式）

```
用户提问
  → RAGRetriever.search()
      → _embed_query() 用 LLM 生成查询向量
      → Milvus 向量搜索（metric=COSINE, nprobe=10, limit=top_k*2 预取）
      → 相似度阈值过滤 + 排序截断到 top_k
  → _build_context() 拼带来源标注的上下文
  → 套 SYSTEM_PROMPT_TEMPLATE + QA_PROMPT_TEMPLATE
  → BaseLLM.chat() / chat_stream() 生成
  → 返回 {answer, sources, tokens_used, latency_ms}
```

- 非流式 `query()` 一次返回；流式 `query_stream()` 先 yield `sources`，再逐 `chunk`，最后 yield `done`
- 历史对话只取**最近 4 轮**拼进 messages

### 文档入库流程（被 document 服务调用）

```
文档分块 → LLM.embedding() 向量化 → RAGRetriever.add_document_chunks() 写入 Milvus
删除文档 → RAGRetriever.delete_document_chunks()
```

## 关键设计决策

1. **Milvus filter 注入防护**：`kb_id` / `document_id` 用 `_KB_ID_RE`（UUID 形态）正则校验后才拼进 filter 表达式——防止通过 kb_id 注入恶意 Milvus 表达式。**改检索过滤逻辑时必须保留这个校验。**
2. **同步客户端异步化**：MilvusClient 是同步阻塞，所有调用包 `asyncio.to_thread()` 放线程池，避免阻塞 FastAPI 事件循环。
3. **预取再过滤**：搜索 limit 取 `top_k*2`，阈值过滤后截断到 top_k——保证过滤后仍有足够结果。
4. **流式 token 估算**：流式模式 LLM 不返回 usage，用 `tiktoken`（cl100k_base）估算；不可用时退化为 `len//2`。
5. **企业 grounding 约束**：`SYSTEM_PROMPT_TEMPLATE` 强制"严格基于参考资料、不编造、引用来源编号"——调提示词时别破坏这个约束。

## 依赖

- 上游：`api/v1/chat.py`（HTTP 入口）
- 下游：`llm/`（BaseLLM 做 embedding + chat）、Milvus
- 配置：`settings.RAG_TOP_K` / `RAG_SIMILARITY_THRESHOLD` / `MILVUS_*` / `EMBEDDING_*`

## 扩展点

- `hybrid_search()` 目前是 TODO（向量检索占位）——计划接 Elasticsearch 做"向量+关键词"混合检索
- 提示词模板（`SYSTEM_PROMPT_TEMPLATE` / `QA_PROMPT_TEMPLATE`）是类常量，调优改这里

## 改这个模块时

- 动 filter 逻辑 → 先看 `_KB_ID_RE` 校验，**别绕过**
- 动 Milvus 调用 → 必须 `asyncio.to_thread`，别直接同步调
- 改提示词 → 注意企业知识库 grounding 约束（不编造、引用来源）
