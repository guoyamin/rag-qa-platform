# ADR-010: 多模型管理方案

**状态:** 已接受  
**日期:** 2026-08-01  
**决策主体:** 用户 + AI辅助

---

## 上下文

### 业务背景

模型管理功能需要支持多模型管理：
- 支持 OpenAI、Anthropic、Qwen 等多种提供商
- 支持 LLM 和 Embedding 两种模型类型
- 支持模型热切换和负载均衡

### 技术约束

- 需要统一的模型调用接口
- 需要支持配置热更新
- 需要处理不同提供商的差异

---

## 决策

> 我们决定实现 **LLMManager 单例模式**，统一管理所有模型的配置和调用。

---

## LLMManager 设计

```python
class LLMManager:
    """LLM 管理器（单例模式）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._config_cache = {}  # 模型配置缓存
        self._client_cache = {}  # 模型客户端缓存
        self._db = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def reload_llm(self, model_id: str):
        """刷新指定模型的缓存"""
        if model_id in self._config_cache:
            del self._config_cache[model_id]
        if model_id in self._client_cache:
            del self._client_cache[model_id]
        # 重新加载
        self._load_model_config(model_id)
        logger.info(f"模型缓存已刷新: {model_id}")
    
    def reload_version(self, version_id: str):
        """刷新指定版本的缓存"""
        if version_id in self._version_cache:
            del self._version_cache[version_id]
        logger.info(f"版本缓存已刷新: {version_id}")
```

---

## 模型客户端接口

```python
class BaseModelClient:
    """模型客户端基类"""
    
    async def chat(self, messages: list, config: dict) -> ChatResponse:
        raise NotImplementedError
    
    async def embed(self, texts: list) -> EmbedResponse:
        raise NotImplementedError

class OpenAIClient(BaseModelClient):
    async def chat(self, messages: list, config: dict) -> ChatResponse:
        # OpenAI 实现
        pass

class AnthropicClient(BaseModelClient):
    async def chat(self, messages: list, config: dict) -> ChatResponse:
        # Anthropic 实现
        pass

class QwenClient(BaseModelClient):
    async def chat(self, messages: list, config: dict) -> ChatResponse:
        # 通义千问实现
        pass
```

---

## 影响

### 对开发的影响
- 需要实现各提供商的客户端
- 需要处理 API 差异和错误
- 需要实现重试和熔断逻辑

### 对运维的影响
- 监控各模型的调用情况
- 需要关注各提供商的稳定性

---

## 相关决策
- ADR-008: 模型配置存储方案
- ADR-011: 健康检查方案
