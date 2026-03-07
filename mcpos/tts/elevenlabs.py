"""ElevenLabs production wrapper with existing-asset compatibility."""

from __future__ import annotations

import json
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from .base import BaseTTSEngine, TTSRequest, TTSResult, TTSError
from ..audio.probe import probe_audio_duration
from ..core.logging import log_warning

_API_ROOT = "https://api.elevenlabs.io/v1/text-to-speech"
_DEFAULT_MODEL_ID = "eleven_multilingual_v2"


def _read_elevenlabs_api_key() -> Optional[str]:
    key = os.getenv("ELEVENLABS_API_KEY")
    if key:
        return key
    config_path = Path(__file__).resolve().parents[2] / "config" / "elevenlabs_api_key.txt"
    if config_path.exists():
        value = config_path.read_text(encoding="utf-8").strip()
        return value or None
    return None


def resolve_existing_elevenlabs_asset(asset_path: Path, output_path: Path, *, source_type: str = "existing_asset_direct") -> TTSResult:
    """Copy an existing MP3 asset into the formal output location."""

    if not asset_path.exists():
        return TTSResult(
            engine="existing_asset",
            output_path=None,
            success=False,
            error=f"Existing asset not found: {asset_path}",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if asset_path.resolve() != output_path.resolve():
        shutil.copy2(asset_path, output_path)
    duration = probe_audio_duration(output_path)
    return TTSResult(
        engine="existing_asset",
        output_path=output_path,
        success=True,
        duration_sec=duration,
        metadata={
            "source_type": source_type,
            "source_path": str(asset_path),
            "output_path": str(output_path),
        },
    )


class ElevenLabsTTSEngine(BaseTTSEngine):
    engine_name = "elevenlabs"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: str = _DEFAULT_MODEL_ID,
        output_format: str = "mp3_44100_192",
        timeout_sec: int = 120,
    ) -> None:
        self.api_key = api_key or _read_elevenlabs_api_key()
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = output_format
        self.timeout_sec = timeout_sec

    def synthesize(self, request: TTSRequest) -> TTSResult:
        voice_id = request.voice_config.get("elevenlabs_voice_id") or self.voice_id
        model_id = request.voice_config.get("elevenlabs_model_id") or self.model_id
        output_format = request.voice_config.get("elevenlabs_output_format") or self.output_format
        api_key = request.voice_config.get("elevenlabs_api_key") or self.api_key

        if not api_key:
            return TTSResult(
                engine=self.engine_name,
                output_path=None,
                success=False,
                error="ELEVENLABS_API_KEY not configured",
            )
        if not voice_id:
            return TTSResult(
                engine=self.engine_name,
                output_path=None,
                success=False,
                error="ElevenLabs voice_id not configured",
            )

        payload = {
            "text": request.text,
            "model_id": model_id,
            "output_format": output_format,
        }
        if request.voice_config.get("voice_settings"):
            payload["voice_settings"] = request.voice_config["voice_settings"]

        url = f"{_API_ROOT}/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        }

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        started_at = time.time()
        http_request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_sec) as response:
                audio_bytes = response.read()
        except urllib.error.HTTPError as exc:
            error_text = exc.read().decode("utf-8", errors="replace")
            return TTSResult(
                engine=self.engine_name,
                output_path=None,
                success=False,
                error=f"ElevenLabs HTTP {exc.code}: {error_text[:500]}",
            )
        except Exception as exc:  # noqa: BLE001
            return TTSResult(
                engine=self.engine_name,
                output_path=None,
                success=False,
                error=str(exc),
            )

        if not audio_bytes:
            return TTSResult(
                engine=self.engine_name,
                output_path=None,
                success=False,
                error="ElevenLabs returned empty audio",
            )

        request.output_path.write_bytes(audio_bytes)
        duration = probe_audio_duration(request.output_path)
        if duration <= 0.1:
            log_warning(f"[tts/elevenlabs] Produced suspiciously short audio: {request.output_path}")

        return TTSResult(
            engine=self.engine_name,
            output_path=request.output_path,
            success=True,
            duration_sec=duration,
            metadata={
                "voice_id": voice_id,
                "model_id": model_id,
                "output_format": output_format,
                "elapsed_sec": round(time.time() - started_at, 3),
                "segment_id": request.segment_id,
                "language": request.language,
            },
        )
