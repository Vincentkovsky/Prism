from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class TaskPriority(str, Enum):
    PREMIUM = "premium"
    STANDARD = "standard"
    BULK = "bulk"


@dataclass(frozen=True)
class TaskQueueConfig:
    queue: str
    priority: int
    retry_policy: Dict[str, int]


TASK_PRIORITY_CONFIG: Dict[TaskPriority, TaskQueueConfig] = {
    TaskPriority.PREMIUM: TaskQueueConfig(
        queue="tasks_premium",
        priority=0,
        retry_policy={"max_retries": 5, "interval_start": 5, "interval_step": 15, "interval_max": 60},
    ),
    TaskPriority.STANDARD: TaskQueueConfig(
        queue="tasks_standard",
        priority=4,
        retry_policy={"max_retries": 3, "interval_start": 10, "interval_step": 20, "interval_max": 90},
    ),
    TaskPriority.BULK: TaskQueueConfig(
        queue="tasks_bulk",
        priority=9,
        retry_policy={"max_retries": 1, "interval_start": 30, "interval_step": 30, "interval_max": 120},
    ),
}


def get_task_route(priority: TaskPriority) -> TaskQueueConfig:
    return TASK_PRIORITY_CONFIG.get(priority, TASK_PRIORITY_CONFIG[TaskPriority.STANDARD])


__all__ = ["TaskPriority", "TaskQueueConfig", "get_task_route"]

