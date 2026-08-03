# 业务术语表（Glossary）

> 平台领域术语。AI 遇到这些词时查这里。

## RAG / 检索

| 术语 | 含义 |
|---|---|
| **RAG** | Retrieval-Augmented Generation，检索增强生成。先检索知识库再让 LLM 基于检索结果回答，避免幻觉 |
| **Embedding** | 文本向量化。把文本转成向量供相似度检索。本项目 embedding 模型独立配置（`EMBEDDING_*`） |
| **向量检索** | 基于向量相似度（COSINE）找相关文档分块，存储在 Milvus |
| **Document Chunk** | 文档分块。文档切成小块各自向量化入库，检索单位是 chunk |
| **Grounding** | 回答必须基于检索到的参考资料、不编造。`rag/pipeline.py` 的系统提示词强制此约束 |
| **Top-K** | 检索返回的最相似结果数（`settings.RAG_TOP_K`） |
| **Hybrid Search** | 向量+关键词混合检索（当前 TODO，计划接 ES） |

## LLM 网关 / 智能路由

| 术语 | 含义 |
|---|---|
| **LLM 网关** | 本平台不止是 RAG 问答，`services/` 层是统一管理多 LLM 的网关：路由、限流、熔断、成本管控 |
| **智能路由** | 按问题复杂度（关键词+长度→SIMPLE/MEDIUM/COMPLEX）匹配规则选模型。规则驱动，非 ML |
| **路由策略** | BALANCED（均衡）/ QUALITY_FIRST（质量优先）/ COST_FIRST（成本优先） |
| **熔断器（Circuit Breaker）** | 故障模型自动摘除。状态机 CLOSED→OPEN→HALF_OPEN。`check_availability` 判断是否可调 |
| **限流** | GLOBAL / USER / MODEL 三级限流 |
| **AB 测试** | 流量分组成实验，对比不同模型/版本效果 |
| **灰度发布** | 模型版本按比例上线（`ROLLOUT_STAGES=[10,30,50,100]`） |
| **LLMManager** | LLM 实例运行时管理器（单例），缓存实例 + 热更新。DB 是真相源，它是缓存 |

## 安全 / 凭据

| 术语 | 含义 |
|---|---|
| **Vault** | HashiCorp Vault，密钥管理。API Key 等敏感凭据经 VaultClient 存取，AppRole 认证 |
| **派生物** | 由源自动生成的产物：OpenAPI schema、前端 TS 类型、package-lock。改源必须重新生成，CI 校验一致性 |

## 错误码

见 `docs/standards/api-contract.md` §错误码（SUCCESS / VALIDATION_ / AUTHENTICATION_ / NOT_FOUND_ / LLM_ / RAG_ …）。
