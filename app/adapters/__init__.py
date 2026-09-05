"""外部健康数据进入系统前的统一适配层。"""

from app.adapters.base import BaseHealthAdapter
from app.adapters.mock_adapter import MockHealthAdapter

__all__ = ["BaseHealthAdapter", "MockHealthAdapter"]

