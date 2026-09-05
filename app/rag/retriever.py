"""Retriever 接口和 FAISS 默认实现。

当前语料全部是明确标识的 Mock 文档；FAISS 只用于跑通向量检索链路，不能作为医学证据。
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.rag.embedding import BaseEmbedding, HashEmbedding


class RetrievedDocument(BaseModel):
    """RAG 返回的最小文档结构。"""

    content: str
    source: str
    score: float = Field(ge=-1, le=1)
    metadata: dict[str, str] = Field(default_factory=dict)


class BaseRetriever(ABC):
    """知识检索协议。"""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedDocument]:
        """返回与查询最相关的文档。"""


class FaissRetriever(BaseRetriever):
    """使用 FAISS 内积索引的第一阶段 Retriever。

    若运行环境尚未安装 FAISS，会退化为简单词项匹配，使 API 仍可启动；部署依赖中已
    声明 ``faiss-cpu``，正常安装后会自动走向量索引。
    """

    def __init__(
        self,
        embedding: BaseEmbedding | None = None,
        documents: Sequence[tuple[str, str]] | None = None,
    ) -> None:
        self.embedding = embedding or HashEmbedding()
        self._documents = list(
            documents
            or [
                ("mock://guideline/activity", "规律、循序渐进的日常活动有助于维持健康习惯。"),
                ("mock://guideline/diet", "健康管理计划应重视均衡饮食、规律进餐和可持续执行。"),
                ("mock://guideline/sleep", "固定作息并记录睡眠变化，有助于观察长期睡眠趋势。"),
            ]
        )
        self._index = None

    def _build_index(self) -> None:
        import faiss  # 延迟导入，避免模块加载时绑定基础设施
        import numpy as np

        vectors = np.asarray(
            self.embedding.embed_documents([item[1] for item in self._documents]),
            dtype="float32",
        )
        faiss.normalize_L2(vectors)
        self._index = faiss.IndexFlatIP(vectors.shape[1])
        self._index.add(vectors)

    def _lexical_fallback(self, query: str, top_k: int) -> list[RetrievedDocument]:
        terms = set(query.lower().split()) or set(query)
        ranked: list[tuple[float, str, str]] = []
        for source, content in self._documents:
            overlap = len(terms.intersection(set(content.lower())))
            score = min(1.0, overlap / max(1, len(terms)))
            ranked.append((score, source, content))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedDocument(
                content=content,
                source=source,
                score=score,
                metadata={"data_status": "mock", "backend": "lexical_fallback"},
            )
            for score, source, content in ranked[:top_k]
        ]

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedDocument]:
        if not query.strip():
            raise ValueError("检索查询不能为空")
        top_k = min(max(top_k, 1), len(self._documents))
        try:
            import faiss
            import numpy as np

            if self._index is None:
                self._build_index()
            query_vector = np.asarray([self.embedding.embed_query(query)], dtype="float32")
            faiss.normalize_L2(query_vector)
            scores, indices = self._index.search(query_vector, top_k)
            return [
                RetrievedDocument(
                    content=self._documents[index][1],
                    source=self._documents[index][0],
                    score=float(score),
                    metadata={"data_status": "mock", "backend": "faiss"},
                )
                for score, index in zip(scores[0], indices[0], strict=True)
                if index >= 0
            ]
        except ImportError:
            return self._lexical_fallback(query, top_k)

