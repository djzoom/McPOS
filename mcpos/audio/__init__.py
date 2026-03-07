"""mcpos/audio — Audio production utilities."""

from .catalog import get_track_duration, scan_bpm_library, scan_library, scan_sg_library
from .ducking import apply_ducking_and_mix
from .normalize import normalize_vo_audio
from .probe import probe_audio, probe_audio_duration

__all__ = [
    "get_track_duration",
    "scan_bpm_library",
    "scan_library",
    "scan_sg_library",
    "apply_ducking_and_mix",
    "normalize_vo_audio",
    "probe_audio",
    "probe_audio_duration",
]
