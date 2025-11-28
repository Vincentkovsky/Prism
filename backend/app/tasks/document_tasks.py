from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
import time

import httpx
from openai import OpenAI

try:
    from celery import Celery, Task
except ImportError:  # pragma: no cover
    Celery = None
    Task = Any  # type: ignore

from ..core.config import get_settings
from ..logging_utils import bind_document_context, bind_task_context, clear_context
from ..models.document import DocumentSource, DocumentStatus
from ..repositories.document_repository import DocumentRepository, create_document_repository
from ..services.chunking_service import StructuredChunker
from ..services.embedding_service import EmbeddingService
from ..services.subscription_service import get_subscription_service
from ..telemetry.task_metrics import (
    record_task_completed,
    record_task_enqueued,
    record_task_failed,
    record_task_started,
)
from .priority import TaskPriority, get_task_route

settings = get_settings()
celery_app = (
    Celery(
        "blockchain_rag",
        broker=settings.celery_broker_url,
        backend=settings.redis_url,
    )
    if Celery
    else None
)

logger = logging.getLogger(__name__)

DEFAULT_PARSE_SKU = "document_upload_pdf"
TASK_SLA_SECONDS = {
    "documents.parse": 600,
}


def get_document_repository() -> DocumentRepository:
    current_settings = get_settings()
    # Use service role for background tasks to bypass RLS
    return create_document_repository(current_settings, use_service_role=True)


@lru_cache(maxsize=1)
def get_chunker() -> StructuredChunker:
    return StructuredChunker()


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingService:
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key)
    return OpenAI()


def _refund_on_failure(user_id: str, sku: str, reason: str) -> None:
    try:
        get_subscription_service().refund_credits(user_id, sku, reason=reason)
    except Exception:  # pragma: no cover
        logger.exception("Failed to refund credits", extra={"user_id": user_id, "sku": sku})


def _check_sla(task_name: str, duration: float, success: bool = True) -> None:
    threshold = TASK_SLA_SECONDS.get(task_name)
    if not threshold:
        return
    if duration > threshold:
        logger.warning(
            "Task SLA breached",
            extra={
                "task_name": task_name,
                "duration": duration,
                "threshold": threshold,
                "success": success,
            },
        )


def _parse_document(
    document_id: str,
    user_id: str,
    source_url: Optional[str] = None,
    sku: str = DEFAULT_PARSE_SKU,
    task: Optional[Task] = None,
) -> None:
    bind_document_context(document_id)
    if task is not None:
        bind_task_context(getattr(getattr(task, "request", None), "id", None))
    repo = get_document_repository()
    _update_task_progress(task, 0, "开始解析")
    logger.info("Starting parse_document_task", extra={"document_id": document_id})
    record_task_started("documents.parse")
    start_time = time.perf_counter()

    document = repo.get(document_id)
    if not document:
        logger.error("Document not found", extra={"document_id": document_id})
        raise ValueError("Document not found")

    repo.mark_status(document_id, DocumentStatus.parsing)

    try:
        elements = _extract_elements(document.source_type, document, source_url)
        _update_task_progress(task, 30, "已提取元素")

        sections = get_chunker().build_sections(elements)
        chunks = get_chunker().chunk_sections(sections)
        _update_task_progress(task, 50, "已完成分块")

        chunks_path = _chunks_path(document_id)
        get_chunker().serialize_chunks(chunks, chunks_path)
        _update_task_progress(task, 70, "已生成 chunk 文件")

        get_embedder().embed_chunks(
            document_id=document_id,
            user_id=user_id,
            chunks_file=chunks_path,
        )
        _update_task_progress(task, 90, "向量入库完成")

        repo.mark_status(document_id, DocumentStatus.completed)
        _update_task_progress(task, 100, "解析完成")
        logger.info("Completed parse_document_task", extra={"document_id": document_id})
        duration = time.perf_counter() - start_time
        record_task_completed("documents.parse", duration)
        _check_sla("documents.parse", duration)
    except Exception as exc:
        logger.exception("Failed to parse document", extra={"document_id": document_id})
        repo.mark_status(document_id, DocumentStatus.failed, str(exc))
        _update_task_progress(task, 100, "解析失败")
        _refund_on_failure(user_id, sku, str(exc))
        duration = time.perf_counter() - start_time
        record_task_failed("documents.parse", duration, str(exc))
        _check_sla("documents.parse", duration, success=False)
        setattr(exc, "credits_refunded", True)
        raise
    finally:
        clear_context()


def _extract_elements(source_type: DocumentSource, document, source_url: Optional[str]) -> list[Dict]:
    chunker = get_chunker()
    if source_type == DocumentSource.pdf:
        if not document.storage_path:
            raise ValueError("PDF document missing storage_path")
        return chunker.parse_pdf(Path(document.storage_path))
    if source_type == DocumentSource.url:
        url = source_url or document.source_value
        html = _fetch_remote_content(url)
        return chunker.parse_html(html)
    return chunker.parse_plain_text(document.source_value)


def _fetch_remote_content(url: str) -> str:
    try:
        with httpx.Client(timeout=20) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch URL content: {url}") from exc


def _chunks_path(document_id: str) -> Path:
    return settings.storage_base_path.parent / "chunks" / f"{document_id}.json"


def _update_task_progress(task: Optional[Task], progress: int, message: str) -> None:
    if not task:
        return
    try:
        task.update_state(state="PROGRESS", meta={"progress": progress, "message": message})
    except Exception:  # pragma: no cover
        logger.debug("Failed to update task progress", exc_info=True)


def _dispatch_task(task_callable, task_name: str, priority: TaskPriority, *args, **kwargs):
    record_task_enqueued(task_name, priority.value)
    if celery_app and not settings.run_tasks_inline:
        route = get_task_route(priority)
        task_callable.apply_async(
            args=args,
            kwargs=kwargs,
            queue=route.queue,
            priority=route.priority,
            retry_policy=route.retry_policy,
        )
    else:
        task_callable(*args, **kwargs)


if celery_app:

    @celery_app.task(name="documents.parse", bind=True)
    def parse_document_task(
        self: Task,
        document_id: str,
        user_id: str,
        source_url: Optional[str] = None,
        sku: str = DEFAULT_PARSE_SKU,
    ) -> None:
        _parse_document(document_id, user_id, source_url, sku=sku, task=self)

else:

    def parse_document_task(
        document_id: str,
        user_id: str,
        source_url: Optional[str] = None,
        sku: str = DEFAULT_PARSE_SKU,
    ) -> None:
        _parse_document(document_id, user_id, source_url, sku=sku, task=None)


def enqueue_parse_document(
    document_id: str,
    user_id: str,
    source_url: Optional[str] = None,
    *,
    priority: TaskPriority = TaskPriority.STANDARD,
    sku: str = DEFAULT_PARSE_SKU,
) -> None:
    """Helper to run Celery task or fallback inline for dev."""
    _dispatch_task(
        parse_document_task,
        "documents.parse",
        priority,
        document_id,
        user_id,
        source_url,
        sku,
    )
