"""Qwen Provider 占位，不发起真实 API 请求。"""

from app.llm.base import BaseLLM, ChatMessage


class QwenProvider(BaseLLM):
    """保留 API Key 注入位置，当前仅返回显式 Mock 内容。"""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def chat(self, messages: list[ChatMessage]) -> str:
        return "[MOCK:qwen] 已生成健康管理计划草案，未调用外部模型。"

