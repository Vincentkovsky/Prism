"""
Document Search Tool for the Agent.

Provides document retrieval functionality by integrating with RAGService.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.app.agent.types import Tool, ToolSchema
from backend.app.services.rag_service import RAGService


logger = logging.getLogger("app.agent.tools.document_search")


def create_document_search_tool(rag_service: RAGService) -> Tool:
    """Create a document_search tool instance.
    
    Args:
        rag_service: The RAGService instance to use for retrieval
        
    Returns:
        A Tool instance configured for document search
    """
    
    def document_search(
        query: str,
        document_id: str,
        user_id: str,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks in a document.
        
        Args:
            query: The search query
            document_id: ID of the document to search
            user_id: ID of the user making the request
            k: Number of results to return (default: 10)
            
        Returns:
            List of relevant chunks with text and metadata
        """
        logger.debug(
            f"Document search: query='{query[:50]}...', "
            f"document_id={document_id}, user_id={user_id}, k={k}"
        )
        
        try:
            chunks = rag_service.get_relevant_chunks(
                question=query,
                document_id=document_id,
                user_id=user_id,
                k=k,
            )
            
            # Format results for agent consumption
            results = []
            for chunk in chunks:
                results.append({
                    "id": chunk.get("id"),
                    "text": chunk.get("text", ""),
                    "section": chunk.get("metadata", {}).get("section_path", "unknown"),
                    "page": chunk.get("metadata", {}).get("page_number"),
                    "relevance_score": 1.0 - chunk.get("distance", 0.0),  # Convert distance to score
                })
            
            logger.info(f"Document search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            raise
    
    schema = ToolSchema(
        name="document_search",
        description=(
            "Search for relevant information in an uploaded document. "
            "Use this tool when you need to find specific information, "
            "facts, or context from the user's document."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant content",
                },
                "document_id": {
                    "type": "string",
                    "description": "The ID of the document to search",
                },
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user making the request",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 10)",
                    "default": 10,
                },
            },
        },
        required=["query", "document_id", "user_id"],
    )
    
    return Tool(schema=schema, handler=document_search)
