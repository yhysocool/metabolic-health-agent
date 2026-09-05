"""本地 LLM Provider 占位，不连接真实推理服务。"""

from app.llm.base import BaseLLM, ChatMessage


class LocalProvider(BaseLLM):
    """保存本地服务地址，当前仅用于验证 Provider 切换机制。"""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    async def chat(self, messages: list[ChatMessage]) -> str:
        return "[MOCK:local] 已生成健康管理计划草案，未调用本地模型。"

