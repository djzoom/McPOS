"""mcpos.vo — VO pipeline domain modules."""

from .models import (
    DuckingInterval,
    NormalizationStats,
    VOAudioBundle,
    VOAsset,
    VOConfig,
    VOChannelProfile,
    VOMode,
    VOSegmentKind,
    VOScriptBundle,
    VOTimelineEntry,
    VoiceReferenceConfig,
)
from .profiles import get_channel_profile
from .resolver import load_vo_config, resolve_or_generate_vo_audio, resolve_existing_vo_asset
from .script_generator import resolve_or_generate_vo_script
from .timeline import build_vo_timeline

__all__ = [
    "DuckingInterval",
    "NormalizationStats",
    "VOAudioBundle",
    "VOAsset",
    "VOConfig",
    "VOChannelProfile",
    "VOMode",
    "VOSegmentKind",
    "VOScriptBundle",
    "VOTimelineEntry",
    "VoiceReferenceConfig",
    "get_channel_profile",
    "load_vo_config",
    "resolve_or_generate_vo_audio",
    "resolve_existing_vo_asset",
    "resolve_or_generate_vo_script",
    "build_vo_timeline",
]
