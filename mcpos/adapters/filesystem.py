"""
文件系统适配器

封装目录结构、AssetPaths 构造以及文件存在性检查。
知道 channels/<channel_id>/output/<episode_id>/ 这棵子树，也知道图库 available 和 used 的分布。

McPOS 原则：完全独立，不依赖外部文件夹的业务逻辑。
所有文件检测逻辑都在本模块内部实现，不引用 kat_rec_web、src、scripts 等外部模块。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime

from ..models import EpisodeSpec, AssetPaths, EpisodeState, StageName, get_required_stages
from ..config import get_config
from ..core.logging import log_info, log_warning, log_error


def build_asset_paths(spec: EpisodeSpec, config=None) -> AssetPaths:
    """
    根据 EpisodeSpec 构建 AssetPaths
    
    这是命名规则的唯一来源，所有路径都通过这里获取。
    """
    if config is None:
        config = get_config()
    
    return AssetPaths.from_episode_spec(spec, config.channels_root)


def build_asset_paths_from_output_dir(output_dir: Path, episode_id: str | None = None) -> AssetPaths:
    """Build AssetPaths from an existing episode output directory."""
    return AssetPaths.from_output_dir(output_dir, episode_id=episode_id)


def check_asset_exists(asset_path: Path | None) -> bool:
    """
    检查资产文件是否存在
    
    Args:
        asset_path: 资产文件路径，可以为 None
    
    Returns:
        如果路径存在且为文件则返回 True，否则返回 False
    """
    if asset_path is None:
        return False
    
    return asset_path.exists() and asset_path.is_file()


def move_image_to_used(image_filename: str) -> bool:
    """
    将图库图片从 available 移到 used
    
    Args:
        image_filename: 图片文件名
        
    Returns:
        是否成功移动
    """
    config = get_config()
    source = config.images_pool_available / image_filename
    target = config.images_pool_used / image_filename
    
    if not source.exists():
        return False
    
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return True
    except Exception:
        return False


def move_image_to_available(image_filename: str) -> bool:
    """
    将图库图片从 used 移回 available（用于 reset）
    
    Args:
        image_filename: 图片文件名
        
    Returns:
        是否成功移动
    """
    config = get_config()
    source = config.images_pool_used / image_filename
    target = config.images_pool_available / image_filename
    
    if not source.exists():
        # 如果图片不在 used，可能已经在 available 或不存在
        return False
    
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        log_info(f"Moved image back to available: {image_filename}")
        return True
    except Exception as e:
        log_error(f"Failed to move image to available: {image_filename}, error: {e}")
        return False


def list_available_images() -> list[Path]:
    """
    列出 images_pool/available 中的所有图片
    """
    config = get_config()
    
    if not config.images_pool_available.exists():
        return []
    
    return list(config.images_pool_available.glob("*.png"))


def get_channel_library_songs(channel_id: str) -> list[Path]:
    """
    获取频道曲库中的所有歌曲文件
    """
    config = get_config()
    songs_dir = config.channels_root / channel_id / "library" / "songs"
    
    if not songs_dir.exists():
        return []
    
    audio_extensions = {".mp3", ".wav", ".flac", ".m4a", ".aac"}
    return [
        p for p in songs_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in audio_extensions
    ]


def get_track_durations_from_library(channel_id: str) -> dict[str, int]:
    """
    从 tracklist.csv 读取曲目时长信息
    
    Returns:
        dict[str, int]: 映射 {track_name: duration_seconds}
    """
    config = get_config()
    tracklist_path = config.channels_root / channel_id / "library" / "tracklist.csv"
    
    if not tracklist_path.exists():
        log_warning(f"tracklist.csv not found at {tracklist_path}")
        return {}
    
    try:
        import csv
        durations = {}
        
        with tracklist_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 尝试多种可能的列名
                track_name = row.get("title") or row.get("Title") or row.get("name") or row.get("Name") or ""
                duration_str = row.get("duration") or row.get("Duration") or row.get("duration_seconds") or row.get("DurationSeconds") or ""
                
                if track_name and duration_str:
                    try:
                        # 尝试解析为秒数（可能是 "3:45" 格式或纯数字）
                        if ":" in duration_str:
                            parts = duration_str.split(":")
                            if len(parts) == 2:
                                minutes, seconds = int(parts[0]), int(parts[1])
                                duration_seconds = minutes * 60 + seconds
                            elif len(parts) == 3:
                                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                                duration_seconds = hours * 3600 + minutes * 60 + seconds
                            else:
                                continue
                        else:
                            duration_seconds = int(float(duration_str))
                        
                        # 使用文件名（不含扩展名）作为主 key，同时保留原始字符串作为备用 key
                        track_name_clean = Path(track_name).stem
                        durations[track_name_clean] = duration_seconds
                        # 也使用完整文件名作为 key（用于匹配 CSV 中的原始文本）
                        durations[track_name] = duration_seconds
                    except (ValueError, IndexError):
                        continue
        
        return durations
    except Exception as e:
        log_error(f"Failed to read tracklist.csv: {e}")
        return {}


def detect_episode_state_from_filesystem(spec: EpisodeSpec, asset_paths: AssetPaths | None = None) -> EpisodeState:
    """
    从文件系统检测 episode 状态
    
    这是状态检测的唯一来源，不依赖 ASR 或数据库。
    
    Args:
        spec: EpisodeSpec 对象
        asset_paths: 可选的 AssetPaths 对象，如果提供则使用，否则内部构建
    """
    if asset_paths is None:
        config = get_config()
        asset_paths = build_asset_paths(spec, config)

    required_stages = get_required_stages(spec)

    mix_complete = asset_paths.timeline_csv.exists() and (
        asset_paths.music_mix_mp3.exists() or asset_paths.final_mix_mp3.exists()
    )

    stage_completed = {stage: False for stage in StageName}
    stage_completed.update({
        StageName.INIT: (
            asset_paths.playlist_csv.exists() and
            asset_paths.recipe_json.exists()
        ),
        StageName.TEXT_BASE: (
            asset_paths.youtube_title_txt.exists() and
            asset_paths.youtube_description_txt.exists() and
            asset_paths.youtube_tags_txt.exists()
        ),
        StageName.COVER: asset_paths.cover_png.exists(),
        StageName.MIX: mix_complete,
        StageName.VO_SCRIPT: (
            asset_paths.vo_script_txt.exists() and
            asset_paths.vo_script_ssml.exists() and
            asset_paths.vo_script_meta_json.exists()
        ),
        StageName.VO_GEN: asset_paths.vo_gen_meta_json.exists(),
        StageName.VO_MIX: (
            asset_paths.final_mix_mp3.exists() and
            asset_paths.vo_timeline_csv.exists() and
            asset_paths.audio_ducking_map.exists()
        ),
        StageName.TEXT_SRT: asset_paths.youtube_srt.exists(),
        StageName.RENDER: asset_paths.youtube_mp4.exists() and asset_paths.render_complete_flag.exists(),
        StageName.UPLOADED: asset_paths.upload_complete_flag.exists(),
        StageName.VERIFIED: asset_paths.verify_complete_flag.exists(),
    })
    stage_completed[StageName.READY] = all(stage_completed.get(stage, False) for stage in required_stages)

    current_stage = None
    is_rendering = asset_paths.youtube_mp4.exists() and not asset_paths.render_complete_flag.exists()

    if stage_completed[StageName.VERIFIED]:
        current_stage = StageName.VERIFIED
    elif stage_completed[StageName.UPLOADED]:
        current_stage = StageName.VERIFIED
    elif stage_completed[StageName.READY]:
        current_stage = StageName.READY
    elif is_rendering:
        current_stage = StageName.RENDER
    else:
        for stage in required_stages:
            if not stage_completed.get(stage, False):
                current_stage = stage
                break

    upload_status = "verified" if stage_completed[StageName.VERIFIED] else (
        "uploaded" if stage_completed[StageName.UPLOADED] else (
            "ready" if stage_completed[StageName.READY] else "pending"
        )
    )

    return EpisodeState(
        episode_id=spec.episode_id,
        channel_id=spec.channel_id,
        date=spec.date,
        current_stage=current_stage,
        stage_completed=stage_completed,
        required_stages=required_stages,
        upload_status=upload_status,
        error_message=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def get_episode_used_assets(recipe_path: Path) -> dict[str, Any]:
    """
    从 recipe.json 读取该期使用的资产（图片、曲目）
    
    Returns:
        dict with keys: "image_filename", "tracks"
    """
    if not recipe_path.exists():
        return {"image_filename": None, "tracks": []}
    
    try:
        import json
        with recipe_path.open("r", encoding="utf-8") as f:
            recipe = json.load(f)
        
        # 从 recipe 中提取使用的图片和曲目
        image_filename = recipe.get("cover_image_filename") or recipe.get("image_filename")
        tracks = recipe.get("assets", {}).get("tracks", [])
        
        return {
            "image_filename": image_filename,
            "tracks": tracks,
        }
    except Exception as e:
        log_warning(f"Failed to read recipe.json: {e}")
        return {"image_filename": None, "tracks": []}


def find_latest_episode(channel_id: str) -> str | None:
    """
    查找时间最晚的期数（根据输出目录的修改时间）
    
    Args:
        channel_id: 频道 ID
        
    Returns:
        期数 ID（如 "kat_20241201"），如果没有找到则返回 None
    """
    config = get_config()
    output_dir = config.channels_root / channel_id / "output"
    
    if not output_dir.exists():
        return None
    
    # 查找所有期数目录
    episodes = []
    for episode_dir in output_dir.iterdir():
        if episode_dir.is_dir():
            # 获取目录修改时间
            mtime = episode_dir.stat().st_mtime
            episodes.append((mtime, episode_dir.name))
    
    if not episodes:
        return None
    
    # 按修改时间排序，返回最晚的
    episodes.sort(key=lambda x: x[0], reverse=True)
    latest_episode_id = episodes[0][1]
    
    log_info(f"Found latest episode: {latest_episode_id} (mtime: {episodes[0][0]})")
    
    return latest_episode_id


def reset_episode_assets(spec: EpisodeSpec) -> dict[str, Any]:
    """
    重置期数资产：删除所有输出文件，恢复图、曲使用状态
    
    Args:
        spec: EpisodeSpec
        
    Returns:
        dict with keys: "deleted_files", "restored_image", "errors"
    """
    config = get_config()
    paths = build_asset_paths(spec, config)
    
    result = {
        "deleted_files": [],
        "restored_image": False,
        "errors": [],
    }
    
    # 1. 读取 recipe.json 获取使用的资产
    used_assets = get_episode_used_assets(paths.recipe_json)
    image_filename = used_assets.get("image_filename")
    
    # 2. 删除整个输出目录
    if paths.episode_output_dir.exists():
        try:
            import shutil
            # 收集所有文件路径（用于日志）
            for file_path in paths.episode_output_dir.rglob("*"):
                if file_path.is_file():
                    result["deleted_files"].append(str(file_path))
            
            shutil.rmtree(paths.episode_output_dir)
            log_info(f"Deleted episode output directory: {paths.episode_output_dir}")
        except Exception as e:
            error_msg = f"Failed to delete output directory: {e}"
            log_error(error_msg)
            result["errors"].append(error_msg)
    
    # 3. 恢复图片使用状态（从 used 移回 available）
    if image_filename:
        try:
            if move_image_to_available(image_filename):
                result["restored_image"] = True
                log_info(f"Restored image to available: {image_filename}")
            else:
                # 图片可能不在 used，或者已经不存在
                log_info(f"Image not in used (or already available): {image_filename}")
        except Exception as e:
            error_msg = f"Failed to restore image: {image_filename}, error: {e}"
            log_error(error_msg)
            result["errors"].append(error_msg)
    
    # 4. 曲目使用状态恢复
    # 注意：曲目不需要移动文件，只需要清理使用记录（如果有的话）
    # 当前实现中，曲目使用情况可能记录在其他地方，这里只做日志记录
    tracks = used_assets.get("tracks", [])
    if tracks:
        log_info(f"Reset episode used {len(tracks)} tracks (usage records should be cleared separately if needed)")
    
    return result
