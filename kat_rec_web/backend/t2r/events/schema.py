"""
T2R WebSocket Event Schema (Documentation & Types Only)

Centralizes the event envelope shape used across the system.
This module does not alter runtime behavior; it's a single source of truth for event types.
"""
from dataclasses import dataclass
from typing import Any, Dict, Literal, TypedDict, Union

EventLevel = Literal["info", "warn", "error"]


class EventEnvelope(TypedDict, total=False):
    type: str            # e.g. "t2r_scan_progress"
    version: int         # global monotonically increasing
    ts: str              # ISO8601 timestamp
    level: EventLevel    # "info" | "warn" | "error"
    data: Dict[str, Any] # payload


# Example union tags (documentational)
ScanProgressType = Literal["t2r_scan_progress"]
FixAppliedType = Literal["t2r_fix_applied"]
RunbookStageUpdateType = Literal["t2r_runbook_stage_update", "t2r_runbook_stage_update", "t2r_runbook_error"]
UploadProgressType = Literal["t2r_upload_progress"]
VerifyResultType = Literal["t2r_verify_result"]

# Union-like doc only; actual enforcement is at the sender/receiver code
EventType = Union[
    ScanProgressType,
    FixAppliedType,
    RunbookStageUpdateType,
    UploadProgressType,
    VerifyResultType,
]


@dataclass
class ExampleEvent:
    """Example of building a valid envelope (for docs/tests)"""
    type: str
    version: int
    ts: str
    level: EventLevel
    data: Dict[str, Any]

    def to_envelope(self) -> EventEnvelope:
        return {
            "type": self.type,
            "version": self.version,
            "ts": self.ts,
            "level": self.level,
            "data": self.data,
        }
