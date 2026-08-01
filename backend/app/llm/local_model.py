"""
智能问答平台 - 私有化部署LLM适配器
支持vLLM、TGI、Ollama等本地推理服务
"""

import json
from collections.abc import AsyncIterator

import httpx

from app.llm.base import BaseLLM, LLMConfig, LLMFactory, LLMResponse, Message


class LocalModelLLM(BaseLLM):
    """
    私有化部署模型适配器
    支持vLLM、TGI、Ollama等兼容OpenAI API格式的本地推理服务
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            base_url=config.api_base or "http://localhost:8000/v1",
            timeout=config.timeout,
        )

    async def chat(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """非流式对话"""
        api_messages = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": self.config.model,
            "messages": api_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }

        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p

        try:
            response = await self.client.post(
                "/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            usage = data.get("usage", {})

            return LLMResponse(
                content=choice["message"]["content"],
                total_tokens=usage.get("total_tokens"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                model=data.get("model", self.config.model),
            )

        except httpx.HTTPError as e:
            raise RuntimeError(f"本地模型调用失败: {str(e)}") from e

    async def chat_stream(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式对话"""
        api_messages = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": self.config.model,
            "messages": api_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }

        try:
            async with self.client.stream(
                "POST",
                "/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue

        except httpx.HTTPError as e:
            raise RuntimeError(f"本地模型流式调用失败: {str(e)}") from e

    async def embedding(self, texts: list[str]) -> list[list[float]]:
        """文本向量化"""
        try:
            response = await self.client.post(
                "/embeddings",
                json={
                    "model": self.config.model,
                    "input": texts,
                },
            )
            response.raise_for_status()
            data = response.json()

            return [item["embedding"] for item in data["data"]]

        except httpx.HTTPError as e:
            raise RuntimeError(f"本地模型Embedding失败: {str(e)}") from e


# 注册到工厂
LLMFactory.register("local", LocalModelLLM)


class VLLMModel(LocalModelLLM):
    """vLLM专用适配器"""

    pass


class TGIModel(LocalModelLLM):
    """TGI (Text Generation Inference) 适配器"""

    pass


class OllamaModel(LocalModelLLM):
    """Ollama适配器"""

    pass


LLMFactory.register("vllm", VLLMModel)
LLMFactory.register("tgi", TGIModel)
LLMFactory.register("ollama", OllamaModel)
