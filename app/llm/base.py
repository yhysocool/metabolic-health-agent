"""LLM 统一接口，Agent 不依赖具体厂商 SDK。"""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """跨 Provider 的最小聊天消息结构。"""

    role: Literal["system", "user", "assistant"]
    content: str


class BaseLLM(ABC):
    """所有模型提供者必须实现的异步聊天接口。"""

    @abstractmethod
    async def chat(self, messages: list[ChatMessage]) -> str:
        """返回模型文本；具体超时、重试和审计将在真实接入阶段实现。"""

