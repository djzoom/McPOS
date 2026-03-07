"""
mcpos/core/channel.py — Channel Plugin Abstract Base Class

Each channel (kat, rbr, sg) implements this interface.
The pipeline calls these methods; channel-specific logic lives in channels/<id>/plugin.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import EpisodeSpec, AssetPaths, StageResult, Track


@dataclass
class ChannelConfig:
    """Per-channel configuration loaded from channels/<id>/config/config.yaml."""
    channel_id: str
    channel_name: str
    library_root: Path                      # root of song library
    assets_root: Path                       # channel-specific assets (intro/outro, video loops)

    # YouTube
    youtube_channel_id: Optional[str] = None
    youtube_playlist_id: Optional[str] = None
    credentials_dir: Optional[Path] = None  # channels/<id>/credentials/

    # Audio production
    target_bpm: Optional[int] = None        # None for SG (no BPM)
    target_duration_min: int = 180
    crossfade_sec: float = 8.0

    # Scheduling
    timezone: str = "UTC"
    publish_time_local: str = "23:00"
    daily_quota_budget: int = 3000

    # Extra per-channel params
    extra: dict = field(default_factory=dict)


class ChannelPlugin(ABC):
    """
    Abstract base class for all channel plugins.

    Each channel implements this interface. The pipeline is channel-agnostic;
    it calls these methods and the plugin provides channel-specific logic.
    """

    def __init__(self, config: ChannelConfig):
        self.config = config
        self.channel_id = config.channel_id

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    @abstractmethod
    def scan_library(self) -> list:
        """
        Scan the channel's song library and return a list of Track objects.

        May use a cached CSV, scan the filesystem, or load from a
        classification CSV (e.g. SG's classification_results.csv).
        """

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    @abstractmethod
    def select_tracks(self, spec, catalog: list) -> list:
        """
        Select tracks for one episode from the catalog.

        Rules differ per channel:
        - KAT: random shuffle, dedup against recent episodes
        - RBR: BPM range filter, BPM-locked selection
        - SG: instrumental-preferred, crossfade-friendly duration
        """

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    @abstractmethod
    def build_mix(self, tracks: list, spec, paths) -> object:
        """
        Build the audio mix for one episode.

        Writes final_mix.mp3 to paths.final_mix_mp3.
        Returns StageResult indicating success/failure.
        """

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------

    @abstractmethod
    def render_video(self, spec, paths) -> object:
        """
        Render the final YouTube video.

        Reads paths.final_mix_mp3 + paths.cover_png.
        Writes paths.youtube_mp4.
        Returns StageResult indicating success/failure.
        """

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    @abstractmethod
    def generate_text(self, spec, paths, tracks: list) -> object:
        """
        Generate title, description, tags for YouTube.

        Writes:
          paths.youtube_title_txt
          paths.youtube_description_txt
          paths.youtube_tags_txt
        """

    # ------------------------------------------------------------------
    # Registry helper
    # ------------------------------------------------------------------

    @classmethod
    def channel_id_str(cls) -> str:
        """Override to return the channel id string, e.g. 'kat', 'rbr', 'sg'."""
        raise NotImplementedError


# ------------------------------------------------------------------
# Channel registry
# ------------------------------------------------------------------

_REGISTRY: dict[str, type[ChannelPlugin]] = {}


def register_channel(cls: type[ChannelPlugin]) -> type[ChannelPlugin]:
    """Class decorator to register a ChannelPlugin implementation."""
    _REGISTRY[cls.channel_id_str()] = cls
    return cls


def get_channel_plugin(channel_id: str, config: ChannelConfig) -> ChannelPlugin:
    """
    Instantiate the ChannelPlugin for a given channel_id.

    Import all channel plugins first so they register themselves:
        import channels.kat.plugin  # noqa
        import channels.rbr.plugin  # noqa
        import channels.sg.plugin   # noqa

    Raises KeyError if channel_id is not registered.
    """
    if channel_id not in _REGISTRY:
        try:
            import channels.kat.plugin  # noqa: F401
            import channels.rbr.plugin  # noqa: F401
            import channels.sg.plugin  # noqa: F401
        except Exception:
            pass

    if channel_id not in _REGISTRY:
        raise KeyError(
            f"No plugin registered for channel '{channel_id}'. "
            f"Available: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[channel_id](config)


def list_registered_channels() -> list[str]:
    """Return sorted list of registered channel IDs."""
    return sorted(_REGISTRY.keys())
