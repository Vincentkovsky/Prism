from __future__ import annotations

import logging
from typing import Optional

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

TASK_ENQUEUED = Counter(
    "task_enqueued_total",
    "Total tasks enqueued per queue priority",
    ["task_name", "priority"],
)

TASK_STARTED = Counter(
    "task_started_total",
    "Total tasks started",
    ["task_name"],
)

TASK_COMPLETED = Counter(
    "task_completed_total",
    "Total tasks completed successfully",
    ["task_name"],
)

TASK_FAILED = Counter(
    "task_failed_total",
    "Total tasks failed",
    ["task_name"],
)

TASK_DURATION = Histogram(
    "task_duration_seconds",
    "Task execution duration",
    ["task_name"],
    buckets=(5, 15, 30, 60, 120, 300, 600, 900, 1800, float("inf")),
)


def record_task_enqueued(task_name: str, priority: str) -> None:
    TASK_ENQUEUED.labels(task_name=task_name, priority=priority).inc()
    logger.info(
        "Task enqueued",
        extra={"task_name": task_name, "priority": priority},
    )


def record_task_started(task_name: str) -> None:
    TASK_STARTED.labels(task_name=task_name).inc()


def record_task_completed(task_name: str, duration: float) -> None:
    TASK_COMPLETED.labels(task_name=task_name).inc()
    TASK_DURATION.labels(task_name=task_name).observe(duration)


def record_task_failed(task_name: str, duration: Optional[float] = None, reason: Optional[str] = None) -> None:
    TASK_FAILED.labels(task_name=task_name).inc()
    if duration is not None:
        TASK_DURATION.labels(task_name=task_name).observe(duration)
    if reason:
        logger.warning(
            "Task failed",
            extra={"task_name": task_name, "reason": reason},
        )


__all__ = [
    "record_task_enqueued",
    "record_task_started",
    "record_task_completed",
    "record_task_failed",
]

