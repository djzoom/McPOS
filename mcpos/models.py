"""
McPOS 核心数据模型

定义 McPOS 系统使用的所有核心数据模型，包括 EpisodeSpec、AssetPaths、EpisodeState 等。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional


class StageName(str, Enum):
    """
    阶段名称枚举。

    Legacy core flow:
      INIT -> TEXT_BASE -> COVER -> MIX -> TEXT_SRT -> RENDER

    VO-aware flow for SG:
      INIT -> TEXT_BASE -> COVER -> MIX -> VO_SCRIPT -> VO_GEN ->
      VO_MIX -> TEXT_SRT -> RENDER

    Post-production:
      READY -> UPLOADED -> VERIFIED
    """

    INIT = "init"
    TEXT_BASE = "text_base"
    COVER = "cover"
    MIX = "mix"
    VO_SCRIPT = "vo_script"
    VO_GEN = "vo_gen"
    VO_MIX = "vo_mix"
    TEXT_SRT = "text_srt"
    RENDER = "render"
    READY = "ready"
    UPLOADED = "uploaded"
    VERIFIED = "verified"


LEGACY_CORE_STAGES: tuple[StageName, ...] = (
    StageName.INIT,
    StageName.TEXT_BASE,
    StageName.COVER,
    StageName.MIX,
    StageName.TEXT_SRT,
    StageName.RENDER,
)

SG_VO_CORE_STAGES: tuple[StageName, ...] = (
    StageName.INIT,
    StageName.TEXT_BASE,
    StageName.COVER,
    StageName.MIX,
    StageName.VO_SCRIPT,
    StageName.VO_GEN,
    StageName.VO_MIX,
    StageName.TEXT_SRT,
    StageName.RENDER,
)

# Backward-compatible alias used by older code.
CORE_STAGES = LEGACY_CORE_STAGES


@dataclass
class Track:
    """
    A single audio track from the library.

    BPM-aware fields are used by KAT/RBR channels.
    SG/CHL fields are used by healing / ambient channels.
    """

    path: Path
    title: str
    duration_sec: float

    # BPM-aware (KAT / RBR)
    bpm: Optional[float] = None
    bpm_confidence: Optional[float] = None
    intro_silence_sec: float = 0.0
    outro_silence_sec: float = 0.0

    # SG / CHL extensions
    vocal_class: Optional[Literal["instrumental", "vocal"]] = None
    song_intro_sec: Optional[float] = None
    first_vocal_sec: Optional[float] = None

    def __str__(self) -> str:
        return f"{self.title} ({self.duration_sec:.0f}s)"


@dataclass
class EpisodeSpec:
    """
    一期节目的抽象身份。

    Interface Contract: minimum fields are channel_id and episode_id.
    Future fields: date, slot, etc.
    """

    channel_id: str
    episode_id: str
    date: Optional[str] = None
    side: Optional[str] = None
    theme: Optional[str] = None
    style: Optional[str] = None
    duration_minutes: Optional[int] = None
    target_bpm: Optional[int] = None
    target_duration_min: Optional[int] = None


def _channel_id_from_spec_or_str(spec_or_channel_id: EpisodeSpec | str) -> str:
    if isinstance(spec_or_channel_id, EpisodeSpec):
        return spec_or_channel_id.channel_id
    return str(spec_or_channel_id)


def _channel_has_vo_enabled(channel_id: str) -> bool:
    if channel_id != "sg":
        return False
    try:
        from .config import load_channel_config

        channel_cfg = load_channel_config(channel_id)
    except Exception:
        return False
    return bool(channel_cfg.extra.get("enable_vo", False))


def get_required_stages(
    spec_or_channel_id: EpisodeSpec | str,
    *,
    enable_vo: Optional[bool] = None,
) -> tuple[StageName, ...]:
    """Return required production stages for an episode or channel."""

    channel_id = _channel_id_from_spec_or_str(spec_or_channel_id)
    if enable_vo is None:
        enable_vo = _channel_has_vo_enabled(channel_id)

    if channel_id == "sg" and enable_vo:
        return SG_VO_CORE_STAGES
    return LEGACY_CORE_STAGES


@dataclass
class AssetPaths:
    """
    一期节目的所有资产文件路径。

    Interface Contract: constructed from base_dir and EpisodeSpec.
    All paths follow the asset naming contract.
    """

    episode_output_dir: Path

    # INIT
    playlist_csv: Path
    recipe_json: Path

    # MIX / audio
    music_mix_mp3: Path
    final_mix_mp3: Path
    timeline_csv: Path
    audio_ducking_map: Path
    ducking_meta_json: Path

    # VO
    vo_intro_mp3: Path
    vo_outro_mp3: Path
    vo_full_mp3: Path
    vo_timeline_csv: Path
    vo_srt: Path
    vo_script_txt: Path
    vo_script_ssml: Path
    vo_script_meta_json: Path
    vo_gen_meta_json: Path
    vo_normalize_meta_json: Path

    # COVER / TEXT
    cover_png: Path
    youtube_title_txt: Path
    youtube_description_txt: Path
    youtube_tags_txt: Path
    youtube_srt: Path

    # RENDER / UPLOAD / VERIFY
    youtube_mp4: Path
    render_complete_flag: Path
    upload_complete_flag: Path
    verify_complete_flag: Path

    # TEMP
    tmp_dir: Path

    @classmethod
    def from_episode_spec(cls, spec: EpisodeSpec, channels_root: Path) -> "AssetPaths":
        episode_output_dir = channels_root / spec.channel_id / "output" / spec.episode_id
        return cls.from_output_dir(episode_output_dir, spec.episode_id)

    @classmethod
    def from_output_dir(cls, episode_output_dir: Path, episode_id: Optional[str] = None) -> "AssetPaths":
        episode_output_dir = Path(episode_output_dir)
        eid = episode_id or episode_output_dir.name
        tmp_dir = episode_output_dir / "tmp"
        return cls(
            episode_output_dir=episode_output_dir,
            playlist_csv=episode_output_dir / "playlist.csv",
            recipe_json=episode_output_dir / "recipe.json",
            music_mix_mp3=episode_output_dir / f"{eid}_music_mix.mp3",
            final_mix_mp3=episode_output_dir / f"{eid}_final_mix.mp3",
            timeline_csv=episode_output_dir / f"{eid}_final_mix_timeline.csv",
            audio_ducking_map=episode_output_dir / f"{eid}_audio_ducking_map.csv",
            ducking_meta_json=episode_output_dir / f"{eid}_ducking_meta.json",
            vo_intro_mp3=episode_output_dir / f"{eid}_vo_intro.mp3",
            vo_outro_mp3=episode_output_dir / f"{eid}_vo_outro.mp3",
            vo_full_mp3=episode_output_dir / f"{eid}_vo_full.mp3",
            vo_timeline_csv=episode_output_dir / f"{eid}_vo_timeline.csv",
            vo_srt=episode_output_dir / f"{eid}_vo.srt",
            vo_script_txt=episode_output_dir / f"{eid}_vo_script.txt",
            vo_script_ssml=episode_output_dir / f"{eid}_vo_script.ssml",
            vo_script_meta_json=episode_output_dir / f"{eid}_vo_script_meta.json",
            vo_gen_meta_json=episode_output_dir / f"{eid}_vo_gen_meta.json",
            vo_normalize_meta_json=episode_output_dir / f"{eid}_vo_normalize_meta.json",
            cover_png=episode_output_dir / f"{eid}_cover.png",
            youtube_title_txt=episode_output_dir / f"{eid}_youtube_title.txt",
            youtube_description_txt=episode_output_dir / f"{eid}_youtube_description.txt",
            youtube_tags_txt=episode_output_dir / f"{eid}_youtube_tags.txt",
            youtube_srt=episode_output_dir / f"{eid}_youtube.srt",
            youtube_mp4=episode_output_dir / f"{eid}_youtube.mp4",
            render_complete_flag=episode_output_dir / f"{eid}_render_complete.flag",
            upload_complete_flag=episode_output_dir / f"{eid}_upload_complete.flag",
            verify_complete_flag=episode_output_dir / f"{eid}_verify_complete.flag",
            tmp_dir=tmp_dir,
        )

    def iter_key_paths(self) -> Iterable[Path]:
        """Return all file-like asset paths for introspection/debugging."""

        for value in self.__dict__.values():
            if isinstance(value, Path):
                yield value


@dataclass
class StageResult:
    """某一阶段的执行结果。"""

    stage: StageName
    success: bool
    duration_seconds: float
    key_asset_paths: List[Path]
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@dataclass
class EpisodeState:
    """
    一期节目的推导状态快照。

    真相来源是文件系统；EpisodeState 是一次检测时的快照。
    """

    episode_id: str
    channel_id: str
    date: Optional[str]
    current_stage: Optional[StageName] = None
    stage_completed: Optional[Dict[StageName, bool]] = None
    required_stages: Optional[tuple[StageName, ...]] = None
    upload_status: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.stage_completed is None:
            self.stage_completed = {stage: False for stage in StageName}
        else:
            for stage in StageName:
                self.stage_completed.setdefault(stage, False)

        if self.required_stages is None:
            self.required_stages = get_required_stages(self.channel_id)
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def is_core_complete(self) -> bool:
        return all(self.stage_completed.get(stage, False) for stage in (self.required_stages or CORE_STAGES))

    def is_render_complete(self) -> bool:
        return self.stage_completed.get(StageName.RENDER, False)

    def completed_required_stages(self) -> list[StageName]:
        return [stage for stage in (self.required_stages or CORE_STAGES) if self.stage_completed.get(stage, False)]

