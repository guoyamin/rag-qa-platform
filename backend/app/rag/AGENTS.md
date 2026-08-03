# RAG 模块 AGENTS

> 模块资产详见 `docs/modules/rag.md`（先读）。本文件只放改这个模块时的硬约束。

## 改这个模块时必须遵守

- **Milvus filter 注入防护**：`kb_id`/`document_id` 拼 filter 前必须过 `_KB_ID_RE`（UUID 形态）校验。动过滤逻辑别绕过它
- **同步客户端异步化**：MilvusClient 是同步阻塞，所有调用必须 `asyncio.to_thread(...)`，禁止直接同步调（会阻塞事件循环）
- **预取再过滤**：search limit 取 `top_k*2`，阈值过滤后截断——别改成精确 limit
- **grounding 约束**：`SYSTEM_PROMPT_TEMPLATE` 强制基于资料、不编造、引用来源。调提示词别破坏这条
- 流式 token 用 `estimate_tokens`（tiktoken）估算，别依赖流式 usage

## 入口

- `RAGPipeline.query()` / `query_stream()`：问答（被 `api/v1/chat.py` 调）
- `RAGRetriever.search()`：检索；`add_document_chunks()` / `delete_document_chunks()`：入库（被 document 服务调）
