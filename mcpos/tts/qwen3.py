"""Qwen3 production wrapper that calls the existing isolated engine directly."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .base import BaseTTSEngine, TTSRequest, TTSResult
from ..audio.probe import probe_audio_duration
from ..core.logging import log_warning

_QWEN_ROOT = Path("/Users/z/Downloads/TTSBlindTest/tts6_pipeline")
_QWEN_PYTHON = Path("/Users/z/Downloads/Qwen3TTS/.venv/bin/python")
_QWEN_SCRIPT = _QWEN_ROOT / "scripts" / "engines" / "run_qwen3.py"
_SAFE_RUNNER = _QWEN_ROOT / "scripts" / "core" / "safe_runner.py"
_INDEX_PYTHON = Path("/Users/z/Downloads/TTSBlindTest/repos/index-tts/.venv/bin/python")
_INDEX_REPO = Path("/Users/z/Downloads/TTSBlindTest/repos/index-tts")
_INDEX_SCRIPT = _QWEN_ROOT / "scripts" / "engines" / "run_indextts2.py"
_DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


class Qwen3TTSEngine(BaseTTSEngine):
    engine_name = "qwen3"

    def __init__(self, *, timeout_sec: int = 5400, fallback_to_index: bool = True) -> None:
        self.timeout_sec = timeout_sec
        self.fallback_to_index = fallback_to_index

    def synthesize(self, request: TTSRequest) -> TTSResult:
        started_at = time.time()
        tmp_dir = request.output_path.parent / "tmp" / f"tts_{request.segment_id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        target_text_path = tmp_dir / f"{request.segment_id}_target.txt"
        log_path = tmp_dir / f"{request.segment_id}_qwen3.log"
        raw_wav = tmp_dir / f"{request.segment_id}_qwen3.wav"

        target_text_path.write_text(request.text, encoding="utf-8")
        language = self._normalize_language(request.voice_config.get("language") or request.language)
        ref_audio = Path(request.voice_config.get("ref_audio_path", ""))
        ref_text = Path(request.voice_config.get("ref_text_path", ""))
        if not ref_audio.exists() or not ref_text.exists():
            return TTSResult(
                engine=self.engine_name,
                output_path=None,
                success=False,
                error="Qwen3 reference audio/text not configured",
                metadata={
                    "ref_audio_path": str(ref_audio),
                    "ref_text_path": str(ref_text),
                },
            )
        qwen_result = self._run_qwen(
            raw_wav=raw_wav,
            ref_audio=ref_audio,
            ref_text=ref_text,
            target_text=target_text_path,
            log_path=log_path,
            language=language,
            device=request.voice_config.get("device", "cpu"),
        )
        if qwen_result.success:
            final_result = self._finalize_audio(raw_wav, request.output_path, engine_used="qwen3")
            final_result.metadata.update(qwen_result.metadata)
            final_result.metadata["elapsed_sec"] = round(time.time() - started_at, 3)
            return final_result

        if not self.fallback_to_index:
            qwen_result.metadata["elapsed_sec"] = round(time.time() - started_at, 3)
            return qwen_result

        index_raw_wav = tmp_dir / f"{request.segment_id}_indextts2.wav"
        index_log_path = tmp_dir / f"{request.segment_id}_indextts2.log"
        index_result = self._run_index(
            raw_wav=index_raw_wav,
            ref_audio=Path(request.voice_config["ref_audio_path"]),
            target_text=target_text_path,
            log_path=index_log_path,
            device=request.voice_config.get("device", "cpu"),
        )
        if index_result.success:
            final_result = self._finalize_audio(index_raw_wav, request.output_path, engine_used="indextts2")
            final_result.metadata.update(index_result.metadata)
            final_result.metadata["fallback_from"] = "qwen3"
            final_result.metadata["elapsed_sec"] = round(time.time() - started_at, 3)
            return final_result

        return TTSResult(
            engine=self.engine_name,
            output_path=None,
            success=False,
            error=index_result.error or qwen_result.error or "Qwen3 synthesis failed",
            metadata={
                "qwen_error": qwen_result.error,
                "index_error": index_result.error,
                "qwen_log": str(log_path),
                "index_log": str(index_log_path),
                "elapsed_sec": round(time.time() - started_at, 3),
            },
        )

    def _run_qwen(
        self,
        *,
        raw_wav: Path,
        ref_audio: Path,
        ref_text: Path,
        target_text: Path,
        log_path: Path,
        language: str,
        device: str,
    ) -> TTSResult:
        if not _QWEN_PYTHON.exists() or not _QWEN_SCRIPT.exists() or not _SAFE_RUNNER.exists():
            return TTSResult(
                engine=self.engine_name,
                output_path=None,
                success=False,
                error="Qwen3 runtime not installed",
            )

        cmd = [
            str(_QWEN_PYTHON),
            str(_SAFE_RUNNER),
            "--log", str(log_path),
            "--timeout", str(self.timeout_sec),
            "--cleanup-pattern", "Qwen3TTS/.venv/bin/python -c from multiprocessing.resource_tracker import main",
            "--cleanup-pattern", "tts6_pipeline/scripts/engines/run_qwen3.py",
            "--env", "PYTHONUNBUFFERED=1",
            "--env", "TOKENIZERS_PARALLELISM=false",
            "--",
            str(_QWEN_PYTHON),
            "-u",
            str(_QWEN_SCRIPT),
            "--model", _DEFAULT_MODEL,
            "--ref-audio", str(ref_audio),
            "--ref-text-file", str(ref_text),
            "--target-text-file", str(target_text),
            "--out", str(raw_wav),
            "--device", device,
            "--language", language,
        ]
        return self._run_command(cmd, raw_wav, log_path, self.engine_name)

    def _run_index(
        self,
        *,
        raw_wav: Path,
        ref_audio: Path,
        target_text: Path,
        log_path: Path,
        device: str,
    ) -> TTSResult:
        if not _INDEX_PYTHON.exists() or not _INDEX_SCRIPT.exists() or not _SAFE_RUNNER.exists():
            return TTSResult(
                engine="indextts2",
                output_path=None,
                success=False,
                error="IndexTTS2 runtime not installed",
            )

        cmd = [
            str(_INDEX_PYTHON),
            str(_SAFE_RUNNER),
            "--log", str(log_path),
            "--timeout", str(max(self.timeout_sec, 7200)),
            "--cleanup-pattern", "index-tts/.venv/bin/python -c from multiprocessing.resource_tracker import main",
            "--cleanup-pattern", "tts6_pipeline/scripts/engines/run_indextts2.py",
            "--env", "PYTHONUNBUFFERED=1",
            "--env", "TOKENIZERS_PARALLELISM=false",
            "--",
            str(_INDEX_PYTHON),
            "-u",
            str(_INDEX_SCRIPT),
            "--repo", str(_INDEX_REPO),
            "--ref-audio", str(ref_audio),
            "--target-text-file", str(target_text),
            "--out", str(raw_wav),
            "--device", device,
        ]
        return self._run_command(cmd, raw_wav, log_path, "indextts2")

    def _run_command(self, cmd: list[str], raw_wav: Path, log_path: Path, engine: str) -> TTSResult:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_sec + 30)
        except Exception as exc:  # noqa: BLE001
            return TTSResult(engine=engine, output_path=None, success=False, error=str(exc), metadata={"log_path": str(log_path)})

        if result.returncode != 0:
            return TTSResult(
                engine=engine,
                output_path=None,
                success=False,
                error=(result.stderr or result.stdout or f"{engine} failed")[-1000:],
                metadata={"log_path": str(log_path)},
            )

        duration = probe_audio_duration(raw_wav)
        if duration <= 0.5:
            return TTSResult(
                engine=engine,
                output_path=None,
                success=False,
                error=f"{engine} produced invalid audio",
                metadata={"log_path": str(log_path), "raw_output": str(raw_wav)},
            )

        return TTSResult(
            engine=engine,
            output_path=raw_wav,
            success=True,
            duration_sec=duration,
            metadata={"log_path": str(log_path), "raw_output": str(raw_wav)},
        )

    def _finalize_audio(self, raw_wav: Path, output_path: Path, *, engine_used: str) -> TTSResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() == ".wav":
            shutil.copy2(raw_wav, output_path)
        else:
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(raw_wav),
                "-c:a", "libmp3lame",
                "-b:a", "320k",
                str(output_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                return TTSResult(
                    engine=engine_used,
                    output_path=None,
                    success=False,
                    error=(result.stderr or "ffmpeg transcoding failed")[-1000:],
                )

        duration = probe_audio_duration(output_path)
        if duration <= 0.5:
            log_warning(f"[tts/qwen3] Finalized audio is suspiciously short: {output_path}")
        return TTSResult(
            engine=engine_used,
            output_path=output_path,
            success=True,
            duration_sec=duration,
            metadata={"engine_used": engine_used, "output_path": str(output_path)},
        )

    @staticmethod
    def _normalize_language(language: str) -> str:
        lowered = str(language).strip().lower()
        if lowered in {"zh", "zh-cn", "chinese", "cn"}:
            return "Chinese"
        return "English"
