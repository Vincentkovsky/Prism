"""
Document Processing Tasks

Handles asynchronous document parsing using Celery or inline execution.
Removed analysis report functionality - use Agent for document Q&A.
"""
from __future__ import annotations

import logging
import asyncio
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import trafilatura
from curl_cffi import requests

try:
    from celery import Celery, Task
except ImportError:  # pragma: no cover
    Celery = None
    Task = Any  # type: ignore

from ..core.config import get_settings
from ..core.database import AsyncSessionLocal
from ..logging_utils import bind_document_context, bind_task_context, clear_context
from ..models.document import DocumentSource, DocumentStatus
from ..repositories.document_repository import PostgresDocumentRepository
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
TASK_SLA_SECONDS = {"documents.parse": 600}


def get_document_repository() -> PostgresDocumentRepository:
    """Get async document repository with new session"""
    session = AsyncSessionLocal()
    return PostgresDocumentRepository(session)


@lru_cache(maxsize=1)
def get_chunker() -> StructuredChunker:
    return StructuredChunker()


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingService:
    return EmbeddingService()


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


async def _parse_document(
    document_id: str,
    user_id: str,
    source_url: Optional[str] = None,
    sku: str = DEFAULT_PARSE_SKU,
    task: Optional[Task] = None,
) -> None:
    """Parse document: extract elements, chunk, embed."""
    bind_document_context(document_id)
    if task is not None:
        bind_task_context(getattr(getattr(task, "request", None), "id", None))
    repo = get_document_repository()
    _update_task_progress(task, 0, "开始解析")
    logger.info("Starting parse_document_task", extra={"document_id": document_id})
    record_task_started("documents.parse")
    start_time = time.perf_counter()

    try:
        document = await repo.get(document_id)
        if not document:
            logger.error("Document not found", extra={"document_id": document_id})
            raise ValueError("Document not found")

        await repo.mark_status(document_id, DocumentStatus.parsing)

        try:
            loop = asyncio.get_running_loop()
            
            elements = await loop.run_in_executor(
                None, _extract_elements, document.source_type, document, source_url
            )
            _update_task_progress(task, 30, "已提取元素")

            # Try to extract title from elements
            title = None
            for element in elements:
                if element.get("category") == "Title":
                    title = element.get("text", "").strip()
                    if title:
                        break
            
            if title:
                await repo.update_title(document_id, title)

            chunker = get_chunker()
            sections = await loop.run_in_executor(None, chunker.build_sections, elements)
            chunks = await loop.run_in_executor(None, chunker.chunk_sections, sections)
            _update_task_progress(task, 50, "已完成分块")

            chunks_path = _chunks_path(document_id)
            await loop.run_in_executor(None, chunker.serialize_chunks, chunks, chunks_path)
            _update_task_progress(task, 70, "已生成 chunk 文件")

            embedder = get_embedder()
            await loop.run_in_executor(
                None,
                embedder.embed_chunks,
                document_id,
                user_id,
                chunks_path,
            )
            _update_task_progress(task, 90, "向量入库完成")

            await repo.mark_status(document_id, DocumentStatus.completed)
            _update_task_progress(task, 100, "解析完成")
            logger.info("Completed parse_document_task", extra={"document_id": document_id})
            duration = time.perf_counter() - start_time
            record_task_completed("documents.parse", duration)
            _check_sla("documents.parse", duration)
        except Exception as exc:
            logger.exception("Failed to parse document", extra={"document_id": document_id})
            await repo.mark_status(document_id, DocumentStatus.failed, str(exc))
            _update_task_progress(task, 100, "解析失败")
            _refund_on_failure(user_id, sku, str(exc))
            duration = time.perf_counter() - start_time
            record_task_failed("documents.parse", duration, str(exc))
            _check_sla("documents.parse", duration, success=False)
            setattr(exc, "credits_refunded", True)
            raise
    finally:
        await repo.session.close()
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
        text = trafilatura.extract(
            html, include_comments=False, include_tables=True, 
            no_fallback=True, output_format="markdown"
        )
        if not text:
            return chunker.parse_html(html)
        return chunker.parse_plain_text(text)
    return chunker.parse_plain_text(document.source_value)


def _fetch_remote_content(url: str) -> str:
    """Fetch URL content with browser impersonation."""
    try:
        response = requests.get(
            url,
            impersonate="chrome120", 
            headers={
                "Referer": "https://www.google.com/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            },
            timeout=15
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Download failed with status {response.status_code}")

        html = response.text
        
        # Check for content iframes
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            
            soup = BeautifulSoup(html, 'html.parser')
            iframes = soup.find_all('iframe')
            
            if not iframes:
                return html
                
            # Score iframes to find main content
            best_iframe = None
            max_score = 0
            
            for iframe in iframes:
                src = iframe.get('src')
                if not src:
                    continue
                    
                score = 0
                width = iframe.get('width')
                height = iframe.get('height')
                style = iframe.get('style', '').lower()
                
                if width and (width == '100%' or (width.isdigit() and int(width) > 800)):
                    score += 2
                if height and (height == '100%' or (height.isdigit() and int(height) > 600)):
                    score += 2
                if 'width: 100%' in style or 'height: 100%' in style:
                    score += 2
                    
                src_lower = src.lower()
                if 'pdf' in src_lower:
                    score += 3
                if 'article' in src_lower or 'content' in src_lower:
                    score += 1
                if 'viewer' in src_lower:
                    score += 2
                    
                if 'ads' in src_lower or 'tracker' in src_lower:
                    score -= 10

                if score > max_score:
                    max_score = score
                    best_iframe = src

            if best_iframe and max_score > 0:
                logger.info(f"Found content iframe with score {max_score}: {best_iframe}")
                full_url = urljoin(url, best_iframe)
                
                iframe_response = requests.get(
                    full_url,
                    impersonate="chrome120",
                    headers={"Referer": url},
                    timeout=15
                )
                
                if iframe_response.status_code == 200:
                    return iframe_response.text
                    
        except ImportError:
            logger.warning("BeautifulSoup not installed, skipping iframe extraction")
        except Exception as e:
            logger.warning(f"Iframe extraction failed: {e}")

        return html

    except Exception as e:
        raise RuntimeError(f"Failed to fetch URL content: {url}. Error: {str(e)}")


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


# Celery tasks
if celery_app:

    @celery_app.task(name="documents.parse", bind=True)
    def parse_document_task(
        self: Task,
        document_id: str,
        user_id: str,
        source_url: Optional[str] = None,
        sku: str = DEFAULT_PARSE_SKU,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop:
            loop.create_task(_parse_document(document_id, user_id, source_url, sku=sku, task=self))
        else:
            asyncio.run(_parse_document(document_id, user_id, source_url, sku=sku, task=self))

else:

    def parse_document_task(
        document_id: str,
        user_id: str,
        source_url: Optional[str] = None,
        sku: str = DEFAULT_PARSE_SKU,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop:
            loop.create_task(_parse_document(document_id, user_id, source_url, sku=sku, task=None))
        else:
            asyncio.run(_parse_document(document_id, user_id, source_url, sku=sku, task=None))


def enqueue_parse_document(
    document_id: str,
    user_id: str,
    source_url: Optional[str] = None,
    *,
    priority: TaskPriority = TaskPriority.STANDARD,
    sku: str = DEFAULT_PARSE_SKU,
) -> None:
    """Enqueue document parsing task."""
    _dispatch_task(
        parse_document_task,
        "documents.parse",
        priority,
        document_id,
        user_id,
        source_url,
        sku,
    )
