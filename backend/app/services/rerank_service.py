"""
Rerank Service Module

可扩展的重排序服务，支持多种 Reranker 后端：
- Jina Reranker v3 (API)
- BGE Reranker (本地模型，待实现)
- Cohere Rerank (API，待实现)

使用方式：
    from app.services.rerank_service import get_reranker
    
    reranker = get_reranker()  # 根据配置自动选择
    reranked = reranker.rerank(query, documents, top_n=5)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..core.config import get_settings


logger = logging.getLogger("app.services.rerank")


class RerankResult:
    """重排序结果"""
    
    def __init__(
        self,
        index: int,
        relevance_score: float,
        document: Optional[str] = None,
    ):
        self.index = index
        self.relevance_score = relevance_score
        self.document = document
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "relevance_score": self.relevance_score,
            "document": self.document,
        }


class BaseReranker(ABC):
    """重排序器基类"""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logger
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Reranker 名称"""
        pass
    
    @abstractmethod
    def _rerank_impl(
        self,
        query: str,
        documents: List[str],
        top_n: int,
    ) -> List[RerankResult]:
        """
        实际的重排序实现
        
        Args:
            query: 查询文本
            documents: 待排序的文档列表
            top_n: 返回 Top N 结果
        
        Returns:
            排序后的结果列表
        """
        pass
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: int = 5,
    ) -> List[RerankResult]:
        """
        对文档进行重排序
        
        Args:
            query: 查询文本
            documents: 待排序的文档列表
            top_n: 返回 Top N 结果
        
        Returns:
            排序后的结果列表
        """
        if not documents:
            return []
        
        top_n = min(top_n, len(documents))
        
        start = time.perf_counter()
        results = self._rerank_impl(query, documents, top_n)
        duration = time.perf_counter() - start
        
        self.logger.info(
            f"{self.name} rerank completed",
            extra={
                "reranker": self.name,
                "query_length": len(query),
                "input_docs": len(documents),
                "output_docs": len(results),
                "duration_ms": round(duration * 1000, 2),
            },
        )
        
        return results
    
    def rerank_chunks(
        self,
        query: str,
        chunks: List[Dict],
        top_n: int = 5,
    ) -> List[Dict]:
        """
        对 chunk 字典列表进行重排序（便捷方法）
        
        Args:
            query: 查询文本
            chunks: chunk 字典列表，每个 chunk 需要有 "text" 字段
            top_n: 返回 Top N 结果
        
        Returns:
            重排序后的 chunk 列表，每个 chunk 会增加 "rerank_score" 字段
        """
        if not chunks:
            return []
        
        documents = [chunk.get("text", "") for chunk in chunks]
        results = self.rerank(query, documents, top_n)
        
        reranked_chunks: List[Dict] = []
        for result in results:
            chunk = chunks[result.index].copy()
            chunk["rerank_score"] = result.relevance_score
            reranked_chunks.append(chunk)
        
        return reranked_chunks


class JinaReranker(BaseReranker):
    """Jina Reranker v3 实现"""
    
    ENDPOINT = "https://api.jina.ai/v1/rerank"
    MODEL = "jina-reranker-v3"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key or self.settings.jina_api_key
        if not self.api_key:
            raise ValueError("Jina API key is required. Set JINA_API_KEY in .env")
    
    @property
    def name(self) -> str:
        return "JinaReranker"
    
    def _rerank_impl(
        self,
        query: str,
        documents: List[str],
        top_n: int,
    ) -> List[RerankResult]:
        import requests
        
        response = requests.post(
            self.ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            json={
                "model": self.MODEL,
                "query": query,
                "top_n": top_n,
                "documents": documents,
                "return_documents": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        
        data = response.json()
        results: List[RerankResult] = []
        for item in data.get("results", []):
            results.append(
                RerankResult(
                    index=item["index"],
                    relevance_score=item["relevance_score"],
                )
            )
        
        return results


class RuleBasedReranker(BaseReranker):
    """基于规则的重排序器（Fallback）"""
    
    # 核心章节优先级提升
    CORE_SECTIONS = ["Abstract", "Introduction", "Conclusion", "摘要", "引言", "结论"]
    
    @property
    def name(self) -> str:
        return "RuleBasedReranker"
    
    def _rerank_impl(
        self,
        query: str,
        documents: List[str],
        top_n: int,
    ) -> List[RerankResult]:
        # 简单规则：按文档长度和关键词匹配度评分
        results: List[RerankResult] = []
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        for idx, doc in enumerate(documents):
            doc_lower = doc.lower()
            doc_terms = set(doc_lower.split())
            
            # 计算词汇重叠率
            overlap = len(query_terms & doc_terms)
            score = overlap / max(len(query_terms), 1)
            
            # 核心章节加分
            for section in self.CORE_SECTIONS:
                if section.lower() in doc_lower:
                    score += 0.1
                    break
            
            results.append(RerankResult(index=idx, relevance_score=score))
        
        # 按分数降序排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_n]
    
    def rerank_chunks_with_metadata(
        self,
        query: str,
        chunks: List[Dict],
        top_n: int = 5,
    ) -> List[Dict]:
        """
        使用 metadata 信息进行更精细的规则重排序
        
        这是原来 rag_service 中的实现，保留用于兼容
        """
        if not chunks:
            return []
        
        section_groups: Dict[str, List[Dict]] = {}
        for chunk in chunks:
            section = chunk.get("metadata", {}).get("section_path", "unknown")
            section_groups.setdefault(section, []).append(chunk)

        scores: List[tuple[str, float]] = []

        for section, section_chunks in section_groups.items():
            # 1. Base score from average distance
            distances = [c.get("distance", 1.0) for c in section_chunks]
            avg_distance = sum(distances) / len(distances)
            score = avg_distance

            # 2. Boost core sections by 30% (lower distance = higher rank)
            if any(core in section for core in self.CORE_SECTIONS):
                score *= 0.7

            # 3. Only boost tables if question explicitly asks about them
            has_table = any(
                c.get("metadata", {}).get("element_type") == "table"
                for c in section_chunks
            )
            if "表格" in query or "table" in query.lower():
                if has_table:
                    score *= 0.8

            scores.append((section, score))

        scores.sort(key=lambda item: item[1])

        reranked: List[Dict] = []
        for section, section_score in scores:
            section_chunks = sorted(
                section_groups[section],
                key=lambda c: int(c.get("metadata", {}).get("chunk_index", 0)),
            )
            for chunk in section_chunks:
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = 1.0 - section_score  # 转换为相关性分数
                reranked.append(chunk_copy)

        return reranked[:top_n]


# TODO: 实现 BGE Reranker (本地模型)
class BGEReranker(BaseReranker):
    """
    BGE Reranker 实现（本地模型）
    
    需要安装: pip install FlagEmbedding
    模型: BAAI/bge-reranker-v2-m3 或 BAAI/bge-reranker-large
    """
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        super().__init__()
        self.model_name = model_name
        self._model = None
    
    @property
    def name(self) -> str:
        return f"BGEReranker({self.model_name})"
    
    def _load_model(self):
        """懒加载模型"""
        if self._model is None:
            try:
                from FlagEmbedding import FlagReranker
                self._model = FlagReranker(self.model_name, use_fp16=True)
                self.logger.info(f"Loaded BGE reranker model: {self.model_name}")
            except ImportError:
                raise ImportError(
                    "FlagEmbedding is required for BGE reranker. "
                    "Install with: pip install FlagEmbedding"
                )
        return self._model
    
    def _rerank_impl(
        self,
        query: str,
        documents: List[str],
        top_n: int,
    ) -> List[RerankResult]:
        model = self._load_model()
        
        # BGE reranker 需要 [query, document] 对
        pairs = [[query, doc] for doc in documents]
        scores = model.compute_score(pairs, normalize=True)
        
        # 如果只有一个文档，scores 可能是单个值
        if not isinstance(scores, list):
            scores = [scores]
        
        results: List[RerankResult] = []
        for idx, score in enumerate(scores):
            results.append(RerankResult(index=idx, relevance_score=float(score)))
        
        # 按分数降序排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_n]


class FallbackReranker(BaseReranker):
    """
    带 Fallback 的重排序器
    
    尝试使用主 reranker，失败时回退到备用 reranker
    """
    
    def __init__(
        self,
        primary: BaseReranker,
        fallback: BaseReranker,
    ):
        super().__init__()
        self.primary = primary
        self.fallback = fallback
    
    @property
    def name(self) -> str:
        return f"Fallback({self.primary.name} -> {self.fallback.name})"
    
    def _rerank_impl(
        self,
        query: str,
        documents: List[str],
        top_n: int,
    ) -> List[RerankResult]:
        try:
            return self.primary._rerank_impl(query, documents, top_n)
        except Exception as e:
            self.logger.warning(
                f"Primary reranker {self.primary.name} failed, using fallback: {e}",
                extra={"error": str(e)},
            )
            return self.fallback._rerank_impl(query, documents, top_n)


def get_reranker(provider: Optional[str] = None) -> BaseReranker:
    """
    获取重排序器实例
    
    Args:
        provider: 指定 reranker 类型，可选值：
            - "jina": Jina Reranker v3
            - "bge": BGE Reranker (本地)
            - "rule": 规则重排序
            - None: 根据配置自动选择
    
    Returns:
        BaseReranker 实例
    """
    settings = get_settings()
    
    if provider is None:
        provider = getattr(settings, "rerank_provider", "jina")
    
    provider = provider.lower()
    
    if provider == "jina":
        if settings.jina_api_key:
            return FallbackReranker(
                primary=JinaReranker(),
                fallback=RuleBasedReranker(),
            )
        else:
            logger.warning("Jina API key not configured, using rule-based reranker")
            return RuleBasedReranker()
    
    elif provider == "bge":
        return FallbackReranker(
            primary=BGEReranker(),
            fallback=RuleBasedReranker(),
        )
    
    elif provider == "rule":
        return RuleBasedReranker()
    
    else:
        raise ValueError(f"Unknown reranker provider: {provider}")
