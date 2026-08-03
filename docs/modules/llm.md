# LLM 适配层

> 路径：`backend/app/llm/` · 路由定位见 [module-map](../architecture/module-map.md) · AI 工作指令见 `backend/app/llm/AGENTS.md`

## 定位

统一适配多种 LLM 后端（OpenAI / 通义千问 / vLLM / TGI / Ollama 等），对上层（`rag/`、`services/`）暴露一致的 `BaseLLM` 接口。换模型/提供商不改业务代码。

## 文件与类

| 文件 | 类 | 职责 |
|---|---|---|
| `base.py` | `BaseLLM`（ABC） | 抽象接口：`chat` / `chat_stream` / `embedding` |
| `base.py` | `LLMFactory` | 注册式工厂：`register(provider, class)` / `create(config)` |
| `base.py` | `Message` / `LLMResponse` / `LLMConfig` | 数据模型（Pydantic） |
| `openai_compatible.py` | `OpenAICompatibleLLM` / `QwenLLM` | 公有云：OpenAI、通义千问 |
| `local_model.py` | `LocalModelLLM` / `VLLMModel` / `TGIModel` / `OllamaModel` | 私有化：vLLM / TGI / Ollama |

## 设计模式：工厂 + 提供商注册

```python
# base.py 定义抽象 + 工厂
class LLMFactory:
    _providers: dict[str, type[BaseLLM]] = {}
    @classmethod
    def register(cls, provider, llm_class): ...
    @classmethod
    def create(cls, config) -> BaseLLM: ...

# 每个适配器文件末尾自注册
LLMFactory.register("openai", OpenAICompatibleLLM)
LLMFactory.register("qwen", QwenLLM)
LLMFactory.register("local", LocalModelLLM)   # + vllm/tgi/ollama
```

- 新增提供商 = 写个 `BaseLLM` 子类 + 末尾 `register` 一行，**不动工厂**
- 所有适配器都走 **OpenAI 兼容 API 格式**（`/chat/completions` + `/embeddings`），所以 `LocalModelLLM` 与 `OpenAICompatibleLLM` 实现相似，子类（`QwenLLM`/`VLLMModel`…）多靠继承复用

## 关键决策

1. **统一 OpenAI 格式**：即使私有化部署（vLLM/TGI/Ollama）也假设兼容 OpenAI API——降低适配成本。若新模型不兼容 OpenAI 格式，需独立实现 `BaseLLM`。
2. **Embedding 独立 client**：`OpenAICompatibleLLM` 内 embedding 用单独的 `_embedding_client`（独立 `EMBEDDING_API_KEY/BASE/MODEL`），可指向和 chat 不同的服务。
3. **全异步**：公有云用 `AsyncOpenAI`，私有化用 `httpx.AsyncClient`，流式用 SSE 解析（`data:` 前缀 + `[DONE]`）。
4. **Pydantic 配置**：`LLMConfig` 约束 `temperature∈[0,2]`、`max_tokens≥1` 等，配置层校验。

## 依赖

- 上游：`rag/`（embedding + chat）、`services/llm_manager.py`（实例管理）
- 配置：`settings.LLM_PROVIDER/API_KEY/API_BASE/MODEL/TEMPERATURE/MAX_TOKENS` + `EMBEDDING_*`

## 改这个模块时

- **加模型提供商** → 新建适配器类继承 `OpenAICompatibleLLM`（兼容格式）或 `BaseLLM`（不兼容），末尾 `LLMFactory.register`
- **改接口** → `BaseLLM` 是契约，动它要同步改所有适配器
- 注意 `services/llm_manager.py` 做运行时缓存/热更新，**别绕过它直接 `LLMFactory.create`**
