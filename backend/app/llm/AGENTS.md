# LLM 模块 AGENTS

> 模块资产详见 `docs/modules/llm.md`（先读）。

## 改这个模块时必须遵守

- **加工厂模式**：加新 LLM 提供商 = 写 `BaseLLM` 子类 + 文件末尾 `LLMFactory.register("name", Class)`。**别改 `LLMFactory` 本身，别在业务代码里 `if provider == ...`**
- 统一 OpenAI 格式：兼容格式的提供商继承 `OpenAICompatibleLLM`；不兼容的才直接实现 `BaseLLM`
- **embedding 独立 client**：`OpenAICompatibleLLM` 的 embedding 用 `_embedding_client`（独立 `EMBEDDING_*` 配置），别和 chat client 混用
- `BaseLLM` 的 `chat` / `chat_stream` / `embedding` 是契约，改它要同步改所有适配器

## 运行时

- 实例管理走 `services/llm_manager.py`（单例 + 缓存 + 热更新）。**别在业务里直接 `LLMFactory.create`**，用 `LLMManager`
