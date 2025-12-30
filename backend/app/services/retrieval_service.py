"""
Retrieval Service Module

独立的文档检索服务，支持向量检索、混合检索（Vector + BM25）和重排序。
供 Agent 的 document_search 工具和其他服务使用。

使用方式：
    from app.services.retrieval_service import RetrievalService
    
    retrieval = RetrievalService()
    chunks = retrieval.retrieve(
        query="什么是比特币",
        user_id="user123",
        document_id="doc456",  # 可选
        mode="hybrid",  # 或 "vector"
        top_k=10,
        rerank_top_n=5,
    )
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Literal, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

try:
    from google import genai  # type: ignore
except ImportError:  # pragma: no cover
    genai = None

from ..core.config import get_settings
from ..logging_utils import bind_document_context
from ..agent.retrieval.bm25_store import BM25IndexStore
from ..agent.retrieval.hybrid_retriever import HybridRetriever, RetrievalResult
from .cache_service import CacheService, chunks_cache_key
from .rerank_service import get_reranker, RuleBasedReranker


logger = logging.getLogger("app.services.retrieval")


# 检索模式类型
RetrievalMode = Literal["vector", "hybrid"]


class RetrievalService:
    """
    文档检索服务
    
    支持两种检索模式：
    - vector: 纯向量检索
    - hybrid: 混合检索 (Vector + BM25 RRF融合)
    
    是 Agent document_search 工具的核心依赖。
    """
    
    CACHE_TTL = 60 * 60  # 1 hour
    
    def __init__(
        self,
        chroma_client: Optional[chromadb.Client] = None,
        bm25_store: Optional[BM25IndexStore] = None,
        cache: Optional[CacheService] = None,
        redis_client=None,
    ):
        """
        初始化检索服务
        
        Args:
            chroma_client: ChromaDB 客户端（可选，默认从配置创建）
            bm25_store: BM25 索引存储（可选，默认创建）
            cache: 缓存服务（可选）
            redis_client: Redis 客户端（可选）
        """
        self.settings = get_settings()
        self.logger = logger
        
        # 初始化 ChromaDB
        if chroma_client:
            self.chroma = chroma_client
        else:
            self.chroma = self._init_chroma()
        
        self.collection = self.chroma.get_or_create_collection("documents")
        
        # 初始化 BM25 Store
        self._bm25_store = bm25_store or BM25IndexStore()
        
        # 初始化 HybridRetriever
        self._hybrid_retriever = HybridRetriever(
            chroma_client=self.chroma,
            bm25_store=self._bm25_store,
            vector_weight=self.settings.vector_weight,
            bm25_weight=self.settings.bm25_weight,
        )
        
        # 初始化 Embedding 客户端
        self.embedding_provider = (self.settings.embedding_provider or "openai").lower()
        self._openai: Optional[OpenAI] = None
        self._gemini_client: Optional["genai.Client"] = None  # type: ignore
        
        if self.embedding_provider == "openai":
            self._openai = OpenAI()
        elif self.embedding_provider == "gemini":
            self._init_gemini()
        
        # 初始化缓存
        self.cache = cache or CacheService(redis_client=redis_client)
    
    def _init_chroma(self) -> chromadb.Client:
        """初始化 ChromaDB 客户端"""
        settings = self.settings
        
        if settings.chroma_server_host:
            return chromadb.HttpClient(
                host=settings.chroma_server_host,
                port=settings.chroma_server_port,
                ssl=settings.chroma_server_ssl,
                headers={"Authorization": f"Bearer {settings.chroma_server_api_key}"} 
                    if settings.chroma_server_api_key else None,
            )
        elif settings.chroma_persist_directory:
            from pathlib import Path
            persist_dir = Path(settings.chroma_persist_directory)
            persist_dir.mkdir(parents=True, exist_ok=True)
            chroma_settings = ChromaSettings(
                persist_directory=str(persist_dir),
                anonymized_telemetry=False,
            )
            return chromadb.PersistentClient(path=str(persist_dir), settings=chroma_settings)
        else:
            return chromadb.Client(settings=ChromaSettings(anonymized_telemetry=False))
    
    def _init_gemini(self) -> None:
        """初始化 Gemini 客户端"""
        if genai is None:  # pragma: no cover
            raise RuntimeError("google-genai is not installed. Run `pip install google-genai`.")
        if not self.settings.google_api_key:
            raise RuntimeError("Missing Google API key for Gemini models.")
        self._gemini_client = genai.Client(api_key=self.settings.google_api_key)
    
    def retrieve(
        self,
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        mode: RetrievalMode = "hybrid",
        top_k: int = 10,
        rerank: bool = True,
        rerank_top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档块
        
        Args:
            query: 查询文本
            user_id: 用户 ID
            document_id: 文档 ID（可选，不指定则搜索用户所有文档）
            mode: 检索模式 - "vector" 或 "hybrid"
            top_k: 检索返回数量
            rerank: 是否进行重排序
            rerank_top_n: 重排序后返回数量（默认使用配置值）
        
        Returns:
            检索到的文档块列表，包含 text, metadata, distance/rerank_score 等字段
        """
        if document_id:
            bind_document_context(document_id)
        
        # 根据模式选择检索方法
        if mode == "hybrid" and document_id:
            # 混合检索需要指定 document_id（因为 BM25 索引是按文档存储的）
            chunks = self.hybrid_search(
                query=query,
                user_id=user_id,
                document_id=document_id,
                k=top_k,
            )
        else:
            # 纯向量检索（支持跨文档搜索）
            if mode == "hybrid" and not document_id:
                self.logger.info(
                    "Hybrid search requires document_id, falling back to vector search",
                )
            chunks = self.vector_search(
                query=query,
                user_id=user_id,
                document_id=document_id,
                k=top_k,
            )
        
        if not chunks:
            return []
        
        # 重排序
        if rerank and self.settings.rerank_enabled:
            rerank_top_n = rerank_top_n or self.settings.rerank_top_n
            chunks = self._rerank(query, chunks, rerank_top_n)
        
        return chunks
    
    def hybrid_search(
        self,
        query: str,
        user_id: str,
        document_id: str,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        执行混合检索 (Vector + BM25 + RRF融合)
        
        Args:
            query: 查询文本
            user_id: 用户 ID
            document_id: 文档 ID（必须）
            k: 返回结果数量
        
        Returns:
            检索到的文档块列表
        """
        bind_document_context(document_id)
        
        # 生成查询向量
        embedding = self._embed_query(query)
        
        start = time.perf_counter()
        results: List[RetrievalResult] = self._hybrid_retriever.search(
            query=query,
            document_id=document_id,
            user_id=user_id,
            query_embedding=embedding,
            k=k,
        )
        duration = time.perf_counter() - start
        
        # 转换为标准格式
        chunks: List[Dict[str, Any]] = []
        for result in results:
            chunks.append({
                "id": result.chunk_id,
                "text": result.text,
                "metadata": result.metadata,
                "distance": 1.0 - result.fused_score,  # 转换为 distance 格式
                "vector_score": result.vector_score,
                "bm25_score": result.bm25_score,
                "fused_score": result.fused_score,
            })
        
        self.logger.info(
            "Hybrid search completed",
            extra={
                "document_id": document_id,
                "user_id": user_id,
                "results": len(chunks),
                "duration_ms": round(duration * 1000, 2),
            },
        )
        
        return chunks
    
    def vector_search(
        self,
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        执行纯向量检索
        
        Args:
            query: 查询文本
            user_id: 用户 ID
            document_id: 文档 ID（可选）
            k: 返回结果数量
        
        Returns:
            检索到的文档块列表
        """
        if document_id:
            bind_document_context(document_id)
        
        # 检查缓存
        cache_key = chunks_cache_key(document_id or "all_docs", query)
        cached = self.cache.get_json(cache_key, layer="chunks")
        if cached:
            self.logger.debug(
                "Chunk cache hit",
                extra={"document_id": document_id or "all", "user_id": user_id, "results": len(cached)},
            )
            return cached
        
        # 生成查询向量
        embedding = self._embed_query(query)
        
        # 构建过滤条件
        where_conditions = [{"user_id": {"$eq": user_id}}]
        if document_id:
            where_conditions.append({"document_id": {"$eq": document_id}})
        where_clause = {"$and": where_conditions} if len(where_conditions) > 1 else where_conditions[0]
        
        # 执行向量搜索
        start = time.perf_counter()
        results = self.collection.query(
            query_embeddings=[embedding],
            where=where_clause,
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        duration = time.perf_counter() - start
        
        # 格式化结果
        chunks: List[Dict[str, Any]] = []
        if results["documents"] and results["documents"][0]:
            for idx in range(len(results["documents"][0])):
                chunks.append({
                    "id": results["ids"][0][idx],
                    "text": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx],
                    "distance": results["distances"][0][idx],
                })
        
        self.logger.info(
            "Vector search completed",
            extra={
                "document_id": document_id or "all",
                "user_id": user_id,
                "results": len(chunks),
                "duration_ms": round(duration * 1000, 2),
            },
        )
        
        # 缓存结果
        self.cache.set_json(cache_key, chunks, self.CACHE_TTL, layer="chunks")
        return chunks
    
    def _rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        """对检索结果进行重排序"""
        try:
            reranker = get_reranker()
            return reranker.rerank_chunks(query, chunks, top_n)
        except Exception as e:
            self.logger.warning(
                f"Reranker failed, using rule-based fallback: {e}",
                extra={"error": str(e)},
            )
            reranker = RuleBasedReranker()
            return reranker.rerank_chunks_with_metadata(query, chunks, top_n)
    
    def _embed_query(self, query: str) -> List[float]:
        """生成查询的向量表示"""
        start = time.perf_counter()
        
        if self.embedding_provider == "gemini":
            if self._gemini_client is None:
                self._init_gemini()
            response = self._gemini_client.models.embed_content(
                model=self.settings.gemini_embedding_model or "text-embedding-004",
                contents=[query],
            )
            if response.embeddings:
                self.logger.debug(
                    "Gemini embedding generated",
                    extra={
                        "model": self.settings.gemini_embedding_model,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    },
                )
                return list(response.embeddings[0].values)
            return []
        
        # OpenAI embedding
        if self._openai is None:
            self._openai = OpenAI()
        response = self._openai.embeddings.create(
            model=self.settings.embedding_model_openai or "text-embedding-3-large",
            input=query,
        )
        embedding = response.data[0].embedding
        self.logger.debug(
            "OpenAI embedding generated",
            extra={
                "model": self.settings.embedding_model_openai,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        return embedding
    
    # --- Legacy compatibility methods ---
    
    def get_relevant_chunks(
        self,
        question: str,
        document_id: Optional[str],
        user_id: str,
        k: int = 10,
    ) -> List[Dict]:
        """Legacy compatibility method."""
        return self.retrieve(
            query=question,
            user_id=user_id,
            document_id=document_id,
            mode="hybrid" if document_id else "vector",
            rerank=False,  # 兼容旧接口，不在这里 rerank
        )
    
    def rerank_chunks(
        self,
        question: str,
        chunks: List[Dict],
        top_n: Optional[int] = None,
    ) -> List[Dict]:
        """Legacy compatibility method."""
        top_n = top_n or self.settings.rerank_top_n
        return self._rerank(question, chunks, top_n)


# 便捷工厂函数
_retrieval_service_instance: Optional[RetrievalService] = None


def get_retrieval_service() -> RetrievalService:
    """获取 RetrievalService 单例"""
    global _retrieval_service_instance
    if _retrieval_service_instance is None:
        _retrieval_service_instance = RetrievalService()
    return _retrieval_service_instance


def reset_retrieval_service() -> None:
    """重置 RetrievalService 单例（用于测试）"""
    global _retrieval_service_instance
    _retrieval_service_instance = None
