"""
Core 层：决策与调度的大脑

承担所有"应该做什么"和"排序怎么安排"的职责。
"""

from .logging import log_info, log_warning, log_error, log_stage_event, StageEvent

__all__ = [
    "log_info",
    "log_warning",
    "log_error",
    "log_stage_event",
    "StageEvent",
]

