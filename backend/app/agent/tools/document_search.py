"""
Document Search Tool for the Agent.

Provides document retrieval functionality by integrating with RetrievalService.
"""

import logging
from typing import Any, Dict, List, Optional

from ..types import Tool, ToolSchema
from ...services.retrieval_service import RetrievalService, get_retrieval_service


logger = logging.getLogger("app.agent.tools.document_search")


def create_document_search_tool(
    retrieval_service: Optional[RetrievalService] = None,
) -> Tool:
    """Create a document_search tool instance.
    
    Args:
        retrieval_service: The RetrievalService instance to use (optional, uses singleton if not provided)
        
    Returns:
        A Tool instance configured for document search
    """
    from ...core.config import get_settings
    settings = get_settings()
    default_k = settings.retrieval_top_k
    
    # Use provided service or get singleton
    service = retrieval_service or get_retrieval_service()
    
    def document_search(
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        k: int = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks in documents.
        
        Args:
            query: The search query
            user_id: ID of the user making the request
            document_id: ID of the document to search (optional, searches all user documents if not provided)
            k: Number of results to return (uses config default if not specified)
            
        Returns:
            List of relevant chunks with text and metadata
        """
        if k is None:
            k = default_k
        logger.debug(
            f"Document search: query='{query[:50]}...', "
            f"document_id={document_id or 'all'}, user_id={user_id}, k={k}"
        )
        
        try:
            # Use retrieve() which includes reranking
            chunks = service.retrieve(
                query=query,
                user_id=user_id,
                document_id=document_id,
                top_k=k * 2,  # Retrieve more for reranking
                rerank=True,
                rerank_top_n=k,
            )
            
            # Format results for agent consumption
            results = []
            for chunk in chunks:
                results.append({
                    "id": chunk.get("id"),
                    "text": chunk.get("text", ""),
                    "document_id": chunk.get("metadata", {}).get("document_id", "unknown"),
                    "section": chunk.get("metadata", {}).get("section_path", "unknown"),
                    "page": chunk.get("metadata", {}).get("page_number"),
                    "relevance_score": chunk.get("rerank_score", 1.0 - chunk.get("distance", 0.0)),
                })
            
            logger.info(f"Document search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            raise
    
    schema = ToolSchema(
        name="document_search",
        description=(
            "Search for relevant information across the user's documents. "
            "Use this tool when you need to find specific information, "
            "facts, or context from documents. Searches all user documents by default."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant content",
                },
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user making the request",
                },
                "document_id": {
                    "type": "string",
                    "description": "Optional: The ID of a specific document to search (omit to search all user documents)",
                },
                "k": {
                    "type": "integer",
                    "description": f"Number of results to return (default: {default_k})",
                    "default": default_k,
                },
            },
        },
        required=["query", "user_id"],
    )
    
    return Tool(schema=schema, handler=document_search)
