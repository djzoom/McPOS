"""Dataclasses shared by the VO pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class VOMode(str, Enum):
    EXISTING_ASSET = "existing_asset"
    ELEVENLABS = "elevenlabs"
    QWEN3 = "qwen3"
    HYBRID = "hybrid"


class VOSegmentKind(str, Enum):
    INTRO = "intro"
    OUTRO = "outro"
    FULL = "full"


@dataclass
class VoiceReferenceConfig:
    ref_audio_path: Optional[Path] = None
    ref_text_path: Optional[Path] = None
    language: str = "en"
    device: str = "cpu"


@dataclass
class VOConfig:
    enable_vo: bool = False
    mode: VOMode = VOMode.HYBRID
    intro_enabled: bool = True
    outro_enabled: bool = True
    ducking_db: float = -8.0
    fade_sec: float = 3.0
    lufs_target: float = -14.0
    true_peak_dbtp: float = -1.0
    channel_profile: str = "generic_dj"
    language: str = "en"
    existing_asset_dir: Optional[Path] = None
    existing_asset_prefer: bool = True
    script_template: Optional[str] = None
    outro_margin_sec: float = 0.0
    legacy_intro_max_sec: float = 45.0
    legacy_outro_max_sec: float = 30.0
    elevenlabs_voice_id: Optional[str] = None
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    voice_settings: dict[str, Any] = field(default_factory=dict)
    reference: VoiceReferenceConfig = field(default_factory=VoiceReferenceConfig)

    @classmethod
    def from_extra(cls, extra: dict[str, Any]) -> "VOConfig":
        ref_audio = extra.get("vo_voice_ref_audio_path")
        ref_text = extra.get("vo_voice_ref_text_path")
        mode_str = str(extra.get("vo_mode", VOMode.HYBRID.value))
        try:
            mode = VOMode(mode_str)
        except ValueError:
            mode = VOMode.HYBRID
        return cls(
            enable_vo=bool(extra.get("enable_vo", False)),
            mode=mode,
            intro_enabled=bool(extra.get("vo_intro_enabled", True)),
            outro_enabled=bool(extra.get("vo_outro_enabled", True)),
            ducking_db=float(extra.get("vo_ducking_db", -8.0)),
            fade_sec=float(extra.get("vo_fade_sec", 3.0)),
            lufs_target=float(extra.get("vo_lufs_target", -14.0)),
            true_peak_dbtp=float(extra.get("vo_true_peak_dbtp", -1.0)),
            channel_profile=str(extra.get("vo_channel_profile", "generic_dj")),
            language=str(extra.get("vo_language", "en")),
            existing_asset_dir=Path(str(extra["vo_existing_asset_dir"])).expanduser() if extra.get("vo_existing_asset_dir") else None,
            existing_asset_prefer=bool(extra.get("vo_existing_asset_prefer", True)),
            script_template=extra.get("vo_script_template"),
            outro_margin_sec=float(extra.get("vo_outro_margin_sec", 0.0)),
            legacy_intro_max_sec=float(extra.get("vo_existing_legacy_intro_max_sec", 45.0)),
            legacy_outro_max_sec=float(extra.get("vo_existing_legacy_outro_max_sec", 30.0)),
            elevenlabs_voice_id=extra.get("vo_elevenlabs_voice_id"),
            elevenlabs_model_id=str(extra.get("vo_elevenlabs_model_id", "eleven_multilingual_v2")),
            voice_settings=dict(extra.get("vo_voice_settings", {}) or {}),
            reference=VoiceReferenceConfig(
                ref_audio_path=Path(str(ref_audio)).expanduser() if ref_audio else None,
                ref_text_path=Path(str(ref_text)).expanduser() if ref_text else None,
                language=str(extra.get("vo_language", "en")),
                device=str(extra.get("vo_device", "cpu")),
            ),
        )

    def enabled_segments(self) -> list[VOSegmentKind]:
        segments: list[VOSegmentKind] = []
        if self.intro_enabled:
            segments.append(VOSegmentKind.INTRO)
        if self.outro_enabled:
            segments.append(VOSegmentKind.OUTRO)
        return segments


@dataclass
class VOChannelProfile:
    profile_id: str
    channel_name: str
    language: str
    intro_template: str
    outro_template: str
    full_template: str
    tone_profile: str
    pacing_profile: str


@dataclass
class VOScriptBundle:
    txt_path: Path
    ssml_path: Path
    meta_path: Path
    intro_text: Optional[str] = None
    outro_text: Optional[str] = None
    full_text: Optional[str] = None
    intro_ssml: Optional[str] = None
    outro_ssml: Optional[str] = None
    full_ssml: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def text_for(self, kind: VOSegmentKind) -> Optional[str]:
        if kind == VOSegmentKind.INTRO:
            return self.intro_text
        if kind == VOSegmentKind.OUTRO:
            return self.outro_text
        return self.full_text

    def ssml_for(self, kind: VOSegmentKind) -> Optional[str]:
        if kind == VOSegmentKind.INTRO:
            return self.intro_ssml
        if kind == VOSegmentKind.OUTRO:
            return self.outro_ssml
        return self.full_ssml


@dataclass
class VOAsset:
    kind: VOSegmentKind
    path: Optional[Path]
    duration_sec: float = 0.0
    text: Optional[str] = None
    ssml_text: Optional[str] = None
    source_type: str = "skipped"
    status: str = "skipped"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VOAudioBundle:
    intro: Optional[VOAsset] = None
    outro: Optional[VOAsset] = None
    full: Optional[VOAsset] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def segment(self, kind: VOSegmentKind) -> Optional[VOAsset]:
        if kind == VOSegmentKind.INTRO:
            return self.intro
        if kind == VOSegmentKind.OUTRO:
            return self.outro
        return self.full

    def active_assets(self) -> list[VOAsset]:
        return [asset for asset in [self.intro, self.outro, self.full] if asset and asset.path and asset.status != "skipped"]


@dataclass
class NormalizationStats:
    input_path: Path
    output_path: Path
    target_lufs: float
    target_peak: float
    input_i: Optional[float] = None
    output_i: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VOTimelineEntry:
    segment_id: str
    kind: VOSegmentKind
    audio_path: Path
    start_sec: float
    end_sec: float
    duck_start_sec: float
    duck_end_sec: float
    text: str = ""
    ssml_text: str = ""


@dataclass
class DuckingInterval:
    segment_id: str
    start_sec: float
    end_sec: float
    target_db: float
    fade_sec: float
    source: str
