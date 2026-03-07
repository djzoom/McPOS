"""Shared protocol for TTS engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class TTSError(RuntimeError):
    """Raised when a TTS engine cannot produce usable audio."""


@dataclass
class TTSRequest:
    text: str
    output_path: Path
    language: str = "en"
    segment_id: str = "full"
    ssml_text: Optional[str] = None
    voice_config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSResult:
    engine: str
    output_path: Optional[Path]
    success: bool
    duration_sec: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class BaseTTSEngine(ABC):
    engine_name: str = "unknown"

    @abstractmethod
    def synthesize(self, request: TTSRequest) -> TTSResult:
        raise NotImplementedError
