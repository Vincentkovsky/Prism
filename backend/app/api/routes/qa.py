from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...core.security import UserContext, get_current_user
from ...services.rag_service import RAGService
from ...services.subscription_service import SubscriptionService, get_subscription_service


router = APIRouter(prefix="/api/qa", tags=["qa"])


class QueryRequest(BaseModel):
    document_id: str
    question: str
    model: str = "mini"


class AnalysisRequest(BaseModel):
    document_id: str


def get_rag_service_dep() -> RAGService:
    return RAGService()


def get_subscription_service_dep() -> SubscriptionService:
    return get_subscription_service()


def _sku_for_model(model: str) -> str:
    return "qa_turbo" if model == "turbo" else "qa_mini"


@router.post("/query")
async def query_document(
    payload: QueryRequest,
    current_user: UserContext = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service_dep),
    subscription: SubscriptionService = Depends(get_subscription_service_dep),
) -> dict:
    """Query a document with a question using RAG.
    
    This endpoint remains fully functional and is the primary way to
    interact with documents in the Agentic RAG system.
    """
    sku = _sku_for_model(payload.model)
    if not subscription.check_and_consume(current_user.id, sku):
        usage = subscription.get_usage(current_user.id)
        remaining = usage.get("remaining_credits", 0)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，剩余 {remaining} 。",
        )
    try:
        response = rag_service.query(
            question=payload.question,
            document_id=payload.document_id,
            user_id=current_user.id,
            model=payload.model,
        )
        return response
    except Exception as exc:
        subscription.refund_credits(current_user.id, sku, reason="qa_failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


# Deprecated endpoints - blockchain-specific analysis has been removed
# These endpoints are kept for backward compatibility but return deprecation warnings

@router.post("/analysis/generate", deprecated=True)
async def generate_analysis(
    payload: AnalysisRequest,
    current_user: UserContext = Depends(get_current_user),
):
    """[DEPRECATED] Generate blockchain analysis report.
    
    This endpoint has been removed as part of the migration to a generic
    Agentic RAG system. The blockchain-specific analysis workflow is no
    longer available.
    
    For document analysis, please use the /api/qa/query endpoint or the
    new /api/agent/chat endpoint (when available).
    """
    deprecation_message = "This endpoint has been removed. Use /api/qa/query or /api/agent/chat instead."
    detail_message = (
        "The analysis/generate endpoint has been removed. "
        "Please use /api/qa/query for document Q&A or /api/agent/chat for agent-based interactions."
    )
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=detail_message,
        headers={"X-Deprecation-Warning": deprecation_message}
    )


@router.get("/analysis/{document_id}", deprecated=True)
async def get_analysis(
    document_id: str,
    current_user: UserContext = Depends(get_current_user),
):
    """[DEPRECATED] Get blockchain analysis report.
    
    This endpoint has been removed as part of the migration to a generic
    Agentic RAG system. The blockchain-specific analysis workflow is no
    longer available.
    
    For document analysis, please use the /api/qa/query endpoint or the
    new /api/agent/chat endpoint (when available).
    """
    deprecation_message = "This endpoint has been removed. Use /api/qa/query or /api/agent/chat instead."
    detail_message = (
        "The analysis endpoint has been removed. "
        "Please use /api/qa/query for document Q&A or /api/agent/chat for agent-based interactions."
    )
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=detail_message,
        headers={"X-Deprecation-Warning": deprecation_message}
    )
