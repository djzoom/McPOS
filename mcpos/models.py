"""
McPOS 核心数据模型

定义 McPOS 系统使用的所有核心数据模型，包括 EpisodeSpec、AssetPaths、EpisodeState 等。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum


class StageName(str, Enum):
    """
    阶段名称枚举
    
    McPOS v1 recognizes exactly six stages: init, text_base, cover, mix, text_srt, render.
    Upload and verify are future stages, not part of v1. They will be added as separate
    enums or state fields in future versions.
    
    Note: TEXT is split into TEXT_BASE (title/description/tags, depends only on playlist.csv)
    and TEXT_SRT (subtitles, depends on playlist.csv and timeline.csv from MIX).
    """
    INIT = "init"
    TEXT_BASE = "text_base"  # Title, description, tags (depends on playlist.csv only)
    COVER = "cover"          # Cover image (depends on playlist.csv only)
    MIX = "mix"              # Audio mix (depends on playlist.csv only)
    TEXT_SRT = "text_srt"    # Subtitles (depends on playlist.csv and timeline.csv)
    RENDER = "render"        # Final video (depends on cover.png and final_mix.mp3)
    # Note: UPLOAD and VERIFY are not in v1. They will be added in future versions.


# McPOS v1 核心阶段列表（用于完成度判断）
# 外部脚本应使用 EpisodeState.is_core_complete() 而不是硬编码此列表
CORE_STAGES = (
    StageName.INIT,
    StageName.TEXT_BASE,
    StageName.COVER,
    StageName.MIX,
    StageName.TEXT_SRT,
    StageName.RENDER,
)


@dataclass
class EpisodeSpec:
    """
    一期节目的抽象身份
    
    Interface Contract: Minimum fields are channel_id and episode_id.
    Future fields: date, slot, etc.
    """
    channel_id: str
    episode_id: str
    date: Optional[str] = None  # Optional: YYYYMMDD format or similar
    side: Optional[str] = None  # Optional: A/B side
    theme: Optional[str] = None  # Optional: theme
    style: Optional[str] = None  # Optional: style
    duration_minutes: Optional[int] = None  # Optional: duration in minutes


@dataclass
class AssetPaths:
    """
    一期节目的所有资产文件路径
    
    Interface Contract: Constructed from base_dir and EpisodeSpec.
    All paths follow the asset naming contract in Dev_Bible.md.
    
    Key properties:
    - Init: .playlist_csv, .recipe_json
    - Mix: .final_mix_mp3 (MP3 格式, 256kbps, 48kHz, 用于渲染和归档), .timeline_csv
    - Cover: .cover_png
    - Text: .youtube_title_txt, .youtube_description_txt, .youtube_tags_txt, .youtube_srt
    - Render: .youtube_mp4, .render_complete_flag
    """
    episode_output_dir: Path
    
    # Init 阶段
    playlist_csv: Path
    recipe_json: Path
    
    # Mix 阶段
    final_mix_mp3: Path     # 混音音频（MP3 格式, 256 kbps, 48 kHz，用于渲染和归档）
    timeline_csv: Path
    
    # Cover 阶段
    cover_png: Path
    
    # Text 阶段
    youtube_title_txt: Path
    youtube_description_txt: Path
    youtube_tags_txt: Path
    youtube_srt: Path
    
    # Render 阶段
    youtube_mp4: Path
    render_complete_flag: Path
    
    # Upload/Verify 阶段
    upload_complete_flag: Path
    verify_complete_flag: Path
    
    # 临时文件目录
    tmp_dir: Path
    
    @classmethod
    def from_episode_spec(
        cls,
        spec: EpisodeSpec,
        channels_root: Path,
    ) -> "AssetPaths":
        """
        根据 EpisodeSpec 构建 AssetPaths
        
        根据文档第五章的命名规则：
        - 输出目录: channels/<channel_id>/output/<episode_id>/
        - 文件名遵循规范，以 episode_id 为前缀（除 playlist.csv 和 recipe.json）
        """
        episode_output_dir = channels_root / spec.channel_id / "output" / spec.episode_id
        tmp_dir = episode_output_dir / "tmp"
        
        return cls(
            episode_output_dir=episode_output_dir,
            playlist_csv=episode_output_dir / "playlist.csv",
            recipe_json=episode_output_dir / "recipe.json",
            final_mix_mp3=episode_output_dir / f"{spec.episode_id}_final_mix.mp3",  # MP3 格式，256 kbps, 48 kHz（用于渲染和归档）
            timeline_csv=episode_output_dir / f"{spec.episode_id}_final_mix_timeline.csv",  # 时间轴文件（对应 final_mix_mp3）
            cover_png=episode_output_dir / f"{spec.episode_id}_cover.png",
            youtube_title_txt=episode_output_dir / f"{spec.episode_id}_youtube_title.txt",
            youtube_description_txt=episode_output_dir / f"{spec.episode_id}_youtube_description.txt",
            youtube_tags_txt=episode_output_dir / f"{spec.episode_id}_youtube_tags.txt",
            youtube_srt=episode_output_dir / f"{spec.episode_id}_youtube.srt",
            youtube_mp4=episode_output_dir / f"{spec.episode_id}_youtube.mp4",
            render_complete_flag=episode_output_dir / f"{spec.episode_id}_render_complete.flag",
            upload_complete_flag=episode_output_dir / f"{spec.episode_id}_upload_complete.flag",
            verify_complete_flag=episode_output_dir / f"{spec.episode_id}_verify_complete.flag",
            tmp_dir=tmp_dir,
        )


@dataclass
class StageResult:
    """某一阶段的执行结果"""
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
    一期节目的推导状态快照
    
    注意：
    - 真相来源是文件系统，EpisodeState 是一次检测时的快照，不是独立的持久状态
    - 通过 detect_episode_state_from_filesystem() 从文件系统推导生成
    - v1 只包含六个核心阶段（INIT, TEXT_BASE, COVER, MIX, TEXT_SRT, RENDER）
    """
    episode_id: str
    channel_id: str
    date: str
    current_stage: Optional[StageName] = None
    stage_completed: Dict[StageName, bool] = None
    upload_status: Optional[str] = None  # "pending", "uploaded", "verified", "failed" (future use)
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """初始化默认值"""
        if self.stage_completed is None:
            self.stage_completed = {stage: False for stage in StageName}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def is_core_complete(self) -> bool:
        """
        检查所有核心阶段是否完成（McPOS v1 的六个阶段）
        
        Returns:
            True if all core stages (INIT, TEXT_BASE, COVER, MIX, TEXT_SRT, RENDER) are completed
        
        Note:
            This method checks only v1 core stages. Future stages (UPLOAD, VERIFY) are not included.
        """
        return all(self.stage_completed.get(stage, False) for stage in CORE_STAGES)
    
    def is_render_complete(self) -> bool:
        """
        检查渲染阶段是否完成
        
        Returns:
            True if RENDER stage is completed
        
        Note:
            This is a convenience method for checking render completion specifically,
            separate from overall core completion.
        """
        return self.stage_completed.get(StageName.RENDER, False)

