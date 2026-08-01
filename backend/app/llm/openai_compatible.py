"""
智能问答平台 - OpenAI兼容LLM适配器
支持OpenAI API、通义千问、文心一言等兼容OpenAI格式的服务
"""

from collections.abc import AsyncIterator
from typing import cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import settings
from app.llm.base import BaseLLM, LLMConfig, LLMFactory, LLMResponse, Message


class OpenAICompatibleLLM(BaseLLM):
    """OpenAI兼容LLM适配器"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.api_base,
            timeout=config.timeout,
        )
        # Embedding 使用独立配置，复用 client 避免每次请求新建连接
        self._embedding_client = AsyncOpenAI(
            api_key=settings.EMBEDDING_API_KEY or config.api_key,
            base_url=settings.EMBEDDING_API_BASE or config.api_base,
            timeout=60,
        )

    async def chat(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """非流式对话"""
        api_messages: list[ChatCompletionMessageParam] = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            api_messages.append(
                cast(
                    ChatCompletionMessageParam,
                    {"role": msg.role, "content": msg.content},
                )
            )

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=api_messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                top_p=self.config.top_p,
            )

            choice = response.choices[0]
            usage = response.usage

            return LLMResponse(
                content=choice.message.content or "",
                total_tokens=usage.total_tokens if usage else None,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                model=response.model,
            )

        except Exception as e:
            raise RuntimeError(f"LLM调用失败: {str(e)}") from e

    async def chat_stream(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式对话"""
        api_messages: list[ChatCompletionMessageParam] = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            api_messages.append(
                cast(
                    ChatCompletionMessageParam,
                    {"role": msg.role, "content": msg.content},
                )
            )

        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model,
                messages=api_messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                top_p=self.config.top_p,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise RuntimeError(f"LLM流式调用失败: {str(e)}") from e

    async def embedding(self, texts: list[str]) -> list[list[float]]:
        """文本向量化"""
        try:
            response = await self._embedding_client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=texts,
            )

            return [item.embedding for item in response.data]

        except Exception as e:
            raise RuntimeError(f"Embedding调用失败: {str(e)}") from e


# 注册到工厂
LLMFactory.register("openai", OpenAICompatibleLLM)


class QwenLLM(OpenAICompatibleLLM):
    """
    通义千问适配器
    通义千问兼容OpenAI API格式，继承OpenAICompatibleLLM即可
    """

    pass


LLMFactory.register("qwen", QwenLLM)
