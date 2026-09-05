"""Embedding 接口及无网络依赖的 Mock 实现。"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
import hashlib
import math


class BaseEmbedding(ABC):
    """向量化提供者接口，后续可接入本地或远程医学 Embedding 模型。"""

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """批量生成文档向量。"""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """生成查询向量。"""


class HashEmbedding(BaseEmbedding):
    """可重复的哈希向量，仅用于验证检索链路，不表达真实语义。"""

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = [token for token in text.lower().split() if token] or list(text)
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

