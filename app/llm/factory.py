"""根据配置创建 LLM Provider，避免 Agent 内出现厂商判断。"""

from app.config import Settings, get_settings
from app.llm.base import BaseLLM
from app.llm.deepseek import DeepSeekProvider
from app.llm.local import LocalProvider
from app.llm.qwen import QwenProvider


def create_llm_provider(settings: Settings | None = None) -> BaseLLM:
    """创建当前配置指定的 Provider；所有实现目前均为 Mock。"""

    settings = settings or get_settings()
    if settings.llm_provider == "deepseek":
        return DeepSeekProvider(settings.deepseek_api_key)
    if settings.llm_provider == "qwen":
        return QwenProvider(settings.qwen_api_key)
    return LocalProvider(settings.local_llm_base_url)

