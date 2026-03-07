"""VO asset resolution and generation orchestration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from .models import VOAsset, VOAudioBundle, VOChannelProfile, VOConfig, VOSegmentKind, VOScriptBundle, VOMode
from ..audio.probe import probe_audio_duration
from ..core.logging import log_info, log_warning
from ..models import AssetPaths
from ..tts.base import TTSRequest
from ..tts.elevenlabs import ElevenLabsTTSEngine, resolve_existing_elevenlabs_asset
from ..tts.qwen3 import Qwen3TTSEngine


def load_vo_config(extra: dict[str, Any]) -> VOConfig:
    return VOConfig.from_extra(extra)


def _ordered_sources(vo_config: VOConfig) -> list[str]:
    if vo_config.mode == VOMode.EXISTING_ASSET:
        return ["existing_asset"]
    if vo_config.mode == VOMode.QWEN3:
        return (["existing_asset", "qwen3"] if vo_config.existing_asset_prefer else ["qwen3", "existing_asset"])
    if vo_config.mode == VOMode.ELEVENLABS:
        return (["existing_asset", "elevenlabs_api", "qwen3"] if vo_config.existing_asset_prefer else ["elevenlabs_api", "qwen3", "existing_asset"])
    return ["existing_asset", "elevenlabs_api", "qwen3"]


def _candidate_assets(asset_dir: Optional[Path]) -> list[Path]:
    if not asset_dir or not asset_dir.exists():
        return []
    return sorted(asset_dir.glob("*.mp3"))


def _paired_text(asset_dir: Optional[Path], asset_path: Optional[Path]) -> Optional[str]:
    if not asset_dir or not asset_dir.exists():
        return None
    if asset_path:
        same_stem = asset_dir / f"{asset_path.stem}.txt"
        if same_stem.exists():
            return same_stem.read_text(encoding="utf-8").strip()
    txt_files = sorted(asset_dir.glob("*.txt"))
    if txt_files:
        return txt_files[0].read_text(encoding="utf-8").strip()
    return None


def _excerpt_existing_asset(source_path: Path, output_path: Path, *, start_sec: float, duration_sec: float) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{max(0.0, start_sec):.3f}",
        "-t", f"{max(0.1, duration_sec):.3f}",
        "-i", str(source_path),
        "-c:a", "libmp3lame",
        "-b:a", "320k",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "ffmpeg excerpt failed")[-1000:])
    return output_path


def resolve_existing_vo_asset(
    kind: VOSegmentKind,
    vo_config: VOConfig,
    output_path: Path,
    *,
    script_bundle: Optional[VOScriptBundle] = None,
) -> Optional[VOAsset]:
    assets = _candidate_assets(vo_config.existing_asset_dir)
    if not assets:
        return None

    direct = next((asset for asset in assets if kind.value in asset.stem.lower()), None)
    source_text = _paired_text(vo_config.existing_asset_dir, direct)
    if direct:
        result = resolve_existing_elevenlabs_asset(direct, output_path, source_type="existing_asset_direct")
        return VOAsset(
            kind=kind,
            path=result.output_path,
            duration_sec=result.duration_sec,
            text=(script_bundle.text_for(kind) if script_bundle else source_text),
            ssml_text=(script_bundle.ssml_for(kind) if script_bundle else None),
            source_type="existing_asset_direct",
            status="resolved" if result.success else "failed",
            metadata=result.metadata,
        )

    full_asset = assets[0]
    full_duration = probe_audio_duration(full_asset)
    if full_duration <= 0.0:
        return None

    if kind == VOSegmentKind.INTRO:
        excerpt_duration = min(vo_config.legacy_intro_max_sec, full_duration)
        excerpt_path = _excerpt_existing_asset(full_asset, output_path, start_sec=0.0, duration_sec=excerpt_duration)
        text = script_bundle.text_for(kind) if script_bundle else source_text
        ssml_text = script_bundle.ssml_for(kind) if script_bundle else None
    else:
        excerpt_duration = min(vo_config.legacy_outro_max_sec, full_duration)
        excerpt_start = max(0.0, full_duration - excerpt_duration)
        excerpt_path = _excerpt_existing_asset(full_asset, output_path, start_sec=excerpt_start, duration_sec=excerpt_duration)
        text = script_bundle.text_for(kind) if script_bundle else source_text
        ssml_text = script_bundle.ssml_for(kind) if script_bundle else None

    return VOAsset(
        kind=kind,
        path=excerpt_path,
        duration_sec=probe_audio_duration(excerpt_path),
        text=text,
        ssml_text=ssml_text,
        source_type="existing_asset_excerpt",
        status="resolved",
        metadata={
            "source_path": str(full_asset),
            "paired_text_found": bool(source_text),
        },
    )


def _synthesize_with_engine(
    source: str,
    kind: VOSegmentKind,
    script_bundle: VOScriptBundle,
    output_path: Path,
    vo_config: VOConfig,
) -> Optional[VOAsset]:
    text = script_bundle.text_for(kind)
    if not text:
        return VOAsset(kind=kind, path=None, source_type="skipped", status="skipped", metadata={"reason": "missing_script"})

    if source == "elevenlabs_api":
        engine = ElevenLabsTTSEngine(
            voice_id=vo_config.elevenlabs_voice_id,
            model_id=vo_config.elevenlabs_model_id,
        )
        result = engine.synthesize(TTSRequest(
            text=text,
            ssml_text=script_bundle.ssml_for(kind),
            output_path=output_path,
            language=vo_config.language,
            segment_id=kind.value,
            voice_config={
                "elevenlabs_voice_id": vo_config.elevenlabs_voice_id,
                "elevenlabs_model_id": vo_config.elevenlabs_model_id,
                "voice_settings": vo_config.voice_settings,
            },
        ))
        return VOAsset(
            kind=kind,
            path=result.output_path,
            duration_sec=result.duration_sec,
            text=text,
            ssml_text=script_bundle.ssml_for(kind),
            source_type="elevenlabs_api",
            status="generated" if result.success else "failed",
            metadata=result.metadata | ({"error": result.error} if result.error else {}),
        )

    engine = Qwen3TTSEngine()
    result = engine.synthesize(TTSRequest(
        text=text,
        ssml_text=script_bundle.ssml_for(kind),
        output_path=output_path,
        language=vo_config.language,
        segment_id=kind.value,
        voice_config={
            "ref_audio_path": str(vo_config.reference.ref_audio_path) if vo_config.reference.ref_audio_path else "",
            "ref_text_path": str(vo_config.reference.ref_text_path) if vo_config.reference.ref_text_path else "",
            "language": vo_config.language,
            "device": vo_config.reference.device,
        },
    ))
    return VOAsset(
        kind=kind,
        path=result.output_path,
        duration_sec=result.duration_sec,
        text=text,
        ssml_text=script_bundle.ssml_for(kind),
        source_type="qwen3",
        status="generated" if result.success else "failed",
        metadata=result.metadata | ({"error": result.error} if result.error else {}),
    )


def resolve_or_generate_vo_audio(
    script_bundle: VOScriptBundle,
    paths: AssetPaths,
    vo_config: VOConfig,
    channel_profile: VOChannelProfile,
) -> VOAudioBundle:
    """Resolve reusable VO assets first, then synthesize missing segments."""

    del channel_profile  # currently used only to keep the public contract aligned.
    sources = _ordered_sources(vo_config)
    meta: dict[str, Any] = {
        "mode": vo_config.mode.value,
        "source_order": sources,
        "segments": {},
        "degraded_to_music_only": False,
    }
    bundle = VOAudioBundle(metadata=meta)

    output_map = {
        VOSegmentKind.INTRO: paths.vo_intro_mp3,
        VOSegmentKind.OUTRO: paths.vo_outro_mp3,
        VOSegmentKind.FULL: paths.vo_full_mp3,
    }

    for kind in vo_config.enabled_segments():
        asset: Optional[VOAsset] = None
        for source in sources:
            if source == "existing_asset":
                asset = resolve_existing_vo_asset(kind, vo_config, output_map[kind], script_bundle=script_bundle)
            else:
                asset = _synthesize_with_engine(source, kind, script_bundle, output_map[kind], vo_config)
            if asset and asset.status in {"resolved", "generated"} and asset.path:
                break
        if asset is None:
            asset = VOAsset(kind=kind, path=None, source_type="skipped", status="skipped", metadata={"reason": "all_sources_failed"})
        if kind == VOSegmentKind.INTRO:
            bundle.intro = asset
        elif kind == VOSegmentKind.OUTRO:
            bundle.outro = asset
        else:
            bundle.full = asset
        meta["segments"][kind.value] = {
            "status": asset.status,
            "source_type": asset.source_type,
            "path": str(asset.path) if asset.path else None,
            "duration_sec": asset.duration_sec,
            **asset.metadata,
        }

    if not bundle.active_assets():
        meta["degraded_to_music_only"] = True
        log_warning("[vo/resolver] No VO assets resolved; pipeline will fall back to music-only output")
    else:
        log_info(f"[vo/resolver] Resolved {len(bundle.active_assets())} VO segment(s)")

    paths.vo_gen_meta_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle
