"""
智能问答平台 - LLM基础抽象层
统一适配公有云API和私有化部署模型
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field


class Message(BaseModel):
    """对话消息"""

    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class LLMResponse(BaseModel):
    """LLM响应"""

    content: str = Field(..., description="生成的内容")
    total_tokens: int | None = Field(None, description="总Token数")
    prompt_tokens: int | None = Field(None, description="提示Token数")
    completion_tokens: int | None = Field(None, description="生成Token数")
    model: str | None = Field(None, description="使用的模型")


class LLMConfig(BaseModel):
    """LLM配置"""

    provider: str = Field(default="openai", description="提供商")
    api_key: str | None = Field(None, description="API密钥")
    api_base: str | None = Field(None, description="API基础URL")
    model: str = Field(default="gpt-4o", description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1)
    top_p: float | None = Field(default=None, ge=0, le=1)
    timeout: int = Field(default=60, description="超时时间(秒)")


class BaseLLM(ABC):
    """LLM基础抽象类"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """对话生成"""
        pass

    @abstractmethod
    def chat_stream(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式对话生成"""
        pass

    @abstractmethod
    async def embedding(self, texts: list[str]) -> list[list[float]]:
        """文本向量化"""
        pass

    def build_messages(
        self,
        user_message: str,
        system_prompt: str | None = None,
        history: list[Message] | None = None,
    ) -> list[Message]:
        """构建消息列表"""
        messages = []

        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))

        if history:
            messages.extend(history)

        messages.append(Message(role="user", content=user_message))
        return messages


class LLMFactory:
    """LLM工厂"""

    _providers: dict[str, type[BaseLLM]] = {}

    @classmethod
    def register(cls, provider: str, llm_class: type[BaseLLM]) -> None:
        """注册LLM提供商"""
        cls._providers[provider] = llm_class

    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLM:
        """创建LLM实例"""
        llm_class = cls._providers.get(config.provider)
        if not llm_class:
            raise ValueError(f"不支持的LLM提供商: {config.provider}")
        return llm_class(config)

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """获取支持的提供商列表"""
        return list(cls._providers.keys())
