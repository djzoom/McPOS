"""
Init 阶段：生成 playlist.csv 和 recipe.json

从零实现，只依赖文件系统和基础工具函数，不调用旧世界的路由或复杂逻辑。

MCPOS_INTERFACE_LOCK: Playlist generation algorithm interface
- generate_playlist_for_episode(spec: EpisodeSpec, library_index: list[Path], config: dict[str, Any], history: dict[str, Any] | None) -> tuple[list[dict], list[dict]]
  This is the core algorithm heart. Schedule only provides constraints (target_duration, special_tags, must_include_track_ids),
  never provides complete track lists. All track selection logic lives here.
"""

from pathlib import Path
from datetime import datetime
from typing import Any
import json
import csv
import random
import hashlib
import re
import shutil

from ..models import EpisodeSpec, AssetPaths, StageResult, StageName
from ..adapters.filesystem import get_channel_library_songs, get_track_durations_from_library, list_available_images
from ..config import get_config
from ..core.logging import log_info, log_warning, log_error


def _load_episode_config(channel_id: str, episode_id: str) -> dict[str, Any] | None:
    """
    从 schedule_master.json 加载轻量配置（降级后的角色）
    
    Schedule 已降级为轻量配置源，只提供约束条件，不提供 track 列表。
    返回的配置只包含：
    - target_duration_minutes: 目标时长（分钟）
    - special_tags: 特殊标签列表（可选，预留字段，当前版本不影响选曲结果）
    - must_include_track_ids: 必须包含的曲目 ID 列表（可选）
    
    如果 schedule 不存在或找不到 episode，返回 None（使用默认配置）。
    """
    config = get_config()
    schedule_path = config.channels_root / channel_id / "schedule_master.json"
    
    if not schedule_path.exists():
        return None
    
    try:
        with schedule_path.open("r", encoding="utf-8") as f:
            schedule = json.load(f)
        
        for ep in schedule.get("episodes", []):
            if ep.get("episode_id") == episode_id:
                # 只提取轻量配置字段
                return {
                    "target_duration_minutes": ep.get("target_duration_minutes", 60),
                    "special_tags": ep.get("special_tags", []),
                    "must_include_track_ids": ep.get("must_include_track_ids", []),
                }
        
        return None
    except Exception as e:
        log_warning(f"Failed to load episode config from schedule: {e}")
        return None


def _load_recent_used_tracks(
    channel_id: str,
    exclude_episode_id: str,
    max_episodes: int = 20,
) -> set[str]:
    """
    Load recently used track filenames/stems from recipe.json history.

    Returns a set containing both file names and stems for quick matching.
    """
    config = get_config()
    output_dir = config.channels_root / channel_id / "output"
    used: set[str] = set()

    if not output_dir.exists():
        return used

    # Collect recipe paths with episode_id for sorting
    recipes: list[tuple[str, Path]] = []
    for episode_dir in output_dir.iterdir():
        if not episode_dir.is_dir():
            continue
        recipe_path = episode_dir / "recipe.json"
        if not recipe_path.exists():
            continue
        try:
            with recipe_path.open("r", encoding="utf-8") as f:
                recipe = json.load(f)
            ep_id = recipe.get("episode_id") or episode_dir.name
            if ep_id == exclude_episode_id:
                continue
            recipes.append((str(ep_id), recipe_path))
        except Exception:
            continue

    # Sort by episode_id to approximate chronology, then take last N
    recipes.sort(key=lambda item: item[0])
    for _, recipe_path in recipes[-max_episodes:]:
        try:
            with recipe_path.open("r", encoding="utf-8") as f:
                recipe = json.load(f)
            tracks = recipe.get("assets", {}).get("tracks", [])
            for track_path in tracks:
                try:
                    p = Path(track_path)
                    used.add(p.name)
                    used.add(p.stem)
                except Exception:
                    continue
        except Exception:
            continue

    return used


def _load_used_image_filenames(
    channel_id: str,
    exclude_episode_id: str,
) -> set[str]:
    """
    Load used image filenames from recipe.json history to prevent reuse.

    NOTE (new workflow):
    - cover_image_filename may be an episode-local renamed copy (album-title slug).
    - cover_source_filename is the canonical "pool identity" that must not repeat.
    """
    config = get_config()
    output_dir = config.channels_root / channel_id / "output"
    used: set[str] = set()

    if not output_dir.exists():
        return used

    for episode_dir in output_dir.iterdir():
        if not episode_dir.is_dir():
            continue
        recipe_path = episode_dir / "recipe.json"
        if not recipe_path.exists():
            continue
        try:
            with recipe_path.open("r", encoding="utf-8") as f:
                recipe = json.load(f)
            ep_id = recipe.get("episode_id") or episode_dir.name
            if ep_id == exclude_episode_id:
                continue
            source_name = (
                recipe.get("cover_source_filename")
                or recipe.get("cover_image_source_filename")
                or recipe.get("cover_image_original_filename")
            )
            if source_name:
                used.add(str(source_name))

            image_filename = recipe.get("cover_image_filename") or recipe.get("image_filename")
            if image_filename:
                used.add(str(image_filename))
        except Exception:
            continue

    return used


def _load_recent_used_images(channel_id: str, limit: int = 8) -> list[str]:
    """
    获取最近使用的图片文件名（按 recipe.json 修改时间倒序）
    """
    config = get_config()
    output_dir = config.channels_root / channel_id / "output"
    if not output_dir.exists():
        return []
    recipes: list[tuple[float, Path]] = []
    for episode_dir in output_dir.iterdir():
        if not episode_dir.is_dir():
            continue
        recipe_path = episode_dir / "recipe.json"
        if recipe_path.exists():
            try:
                mtime = recipe_path.stat().st_mtime
                recipes.append((mtime, recipe_path))
            except Exception:
                continue
    recipes.sort(reverse=True)
    recent: list[str] = []
    for _, recipe_path in recipes[: max(limit, 1)]:
        try:
            data = json.loads(recipe_path.read_text(encoding="utf-8"))
            name = (
                data.get("cover_source_filename")
                or data.get("cover_image_filename")
                or data.get("image_filename")
            )
            if name:
                recent.append(name)
        except Exception:
            continue
    return recent


def _image_signature(filename: str) -> str:
    """
    从图片文件名提取“主题签名”，用于避免相邻批次重复。
    """
    base = Path(filename).stem.lower()
    # 去掉常见用户名/前缀（如 0x... 或 @name）
    base = re.sub(r"^(0x[a-z0-9]+|@?[a-z0-9]+)[_-]", "", base)
    tokens = re.split(r"[_\\-\\s]+", base)
    tokens = [t for t in tokens if len(t) > 2]
    return "_".join(tokens[:2]) if tokens else base


def _try_distribute_tracks(
    selected: list[dict],
    must_include_track_ids: list[str],
    min_side_duration_seconds: int,
) -> tuple[list[dict], list[dict]]:
    """
    尝试将选中的曲目分配到 A/B 面
    
    注意：这是一个粗分配函数，主要用于在选曲过程中快速验证是否满足约束。
    真正的书面保证（每面都 >= min_side_duration_seconds）由外层调用方负责最终校验。
    
    Args:
        selected: 选中的曲目列表
        must_include_track_ids: 必须包含的曲目 ID 列表
        min_side_duration_seconds: 每面的最小时长（秒）
    
    Returns:
        (side_a, side_b): A/B 面的曲目列表
    """
    side_a = []
    side_b = []
    side_a_duration = 0
    
    # 先处理必须包含的曲目（如果有）
    must_include_set = set(must_include_track_ids)
    must_include_tracks = [t for t in selected if t["file_name"] in must_include_set or Path(t["file_path"]).stem in must_include_set]
    other_tracks = [t for t in selected if t not in must_include_tracks]
    
    # 将必须包含的曲目平均分配到 A/B 面
    for i, track in enumerate(must_include_tracks):
        if i % 2 == 0:
            side_a.append(track)
            side_a_duration += track["duration_seconds"]
        else:
            side_b.append(track)
    
    # 然后分配其他曲目，确保每面 >= min_side_duration_seconds
    for track in other_tracks:
        if side_a_duration < min_side_duration_seconds:
            side_a.append(track)
            side_a_duration += track["duration_seconds"]
        else:
            side_b.append(track)
    
    return side_a, side_b


def generate_playlist_for_episode(
    spec: EpisodeSpec,
    library_index: list[Path],
    config: dict[str, Any],
    history: dict[str, Any] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    MCPOS_INTERFACE_LOCK: Core playlist generation algorithm
    
    这是 McPOS 的算法心脏。核心选曲由本函数负责，schedule 仅提供约束条件，不提供 track 列表。
    
    Args:
        spec: EpisodeSpec with channel_id and episode_id
        library_index: List of song file paths from library
        config: Lightweight config dict with:
            - target_duration_minutes: Target duration (default: 60)
            - special_tags: Optional list of special tags
            - must_include_track_ids: Optional list of track IDs that must be included
        history: Optional history dict for deduplication (future use)
    
    Returns:
        (side_a: list[dict], side_b: list[dict]) - Track lists for A and B sides
    
    Interface Contract: This signature is locked. Do not change without updating MCPOS_INTERFACE_LOCK.
    """
    if not library_index:
        raise ValueError(f"No songs found in library for channel {spec.channel_id}")
    
    target_duration_minutes = config.get("target_duration_minutes", 60)
    must_include_track_ids = config.get("must_include_track_ids", [])
    special_tags = config.get("special_tags", [])
    
    # 从 tracklist.csv 读取真实时长信息
    track_durations = get_track_durations_from_library(spec.channel_id)
    log_info(f"Loaded {len(track_durations)} track durations from library")
    
    def get_track_duration(song_path: Path) -> int:
        """
        获取曲目时长（秒）
        从 tracklist.csv 读取，如果找不到则抛出错误
        
        禁止使用任何默认值或 fallback。必须从 tracklist.csv 获取真实时长。
        """
        # 尝试多种 key 匹配方式
        stem = song_path.stem  # 不含扩展名的文件名
        name = song_path.name  # 完整文件名（含扩展名）
        
        # 1. 直接匹配 stem（不含扩展名）
        if stem in track_durations:
            return track_durations[stem]
        
        # 2. 匹配完整文件名（含扩展名）
        if name in track_durations:
            return track_durations[name]
        
        # 3. 尝试移除常见后缀（如 "_remastered", "_extended" 等）
        for suffix in ["_remastered", "_extended", "_original", "_mix"]:
            if stem.endswith(suffix):
                base = stem[:-len(suffix)]
                if base in track_durations:
                    return track_durations[base]
        
        # 4. 如果都找不到，抛出错误（禁止使用默认值）
        raise ValueError(
            f"Track duration not found in tracklist.csv for: {song_path.name} "
            f"(tried: {stem}, {name}, and variants with suffixes removed). "
            f"Please add this track to library/tracklist.csv with correct duration."
        )
    
    selected = []
    total_duration = 0
    target_seconds = target_duration_minutes * 60
    MIN_SIDE_DURATION_SECONDS = 29 * 60 + 39  # 29分39秒
    MIN_TOTAL_DURATION_SECONDS = MIN_SIDE_DURATION_SECONDS * 2  # 两面都需要 >= 29分39秒
    MAX_TRACKS = 26  # 总曲目数限制：不超过 26 首
    
    # 使用 episode_id 作为随机种子，确保可复现（使用 hashlib 确保跨进程/重启的一致性）
    seed = int(hashlib.md5(spec.episode_id.encode("utf-8")).hexdigest(), 16) % 10**9
    rng = random.Random(seed)
    
    # 先处理必须包含的曲目
    must_include_set = set(must_include_track_ids)
    must_include_tracks = []
    for song_path in library_index:
        if song_path.name in must_include_set or song_path.stem in must_include_set:
            duration = get_track_duration(song_path)
            must_include_tracks.append({
                "file_path": str(song_path),
                "file_name": song_path.name,
                "title": song_path.stem.replace("_", " ").title(),
                "duration_seconds": duration,
            })
            total_duration += duration
    
    # 将必须包含的曲目加入已选列表
    selected.extend(must_include_tracks)

    # 近期去重（默认启用）：避免短期内重复使用同一首歌
    avoid_recent_tracks = config.get("avoid_recent_tracks", True)
    recent_track_lookback = config.get("recent_track_lookback", 20)
    recent_used = (
        _load_recent_used_tracks(spec.channel_id, spec.episode_id, recent_track_lookback)
        if avoid_recent_tracks
        else set()
    )
    if avoid_recent_tracks:
        log_info(f"Loaded {len(recent_used)} recently used track keys for deduplication")

    # 准备其他曲目：随机打乱，保持随机性（优先未使用曲目）
    fresh_tracks: list[dict] = []
    used_tracks: list[dict] = []
    for song_path in library_index:
        if song_path.name not in must_include_set and song_path.stem not in must_include_set:
            try:
                duration = get_track_duration(song_path)
                track_payload = {
                    "file_path": str(song_path),
                    "file_name": song_path.name,
                    "title": song_path.stem.replace("_", " ").title(),
                    "duration_seconds": duration,
                }
                if song_path.name in recent_used or song_path.stem in recent_used:
                    used_tracks.append(track_payload)
                else:
                    fresh_tracks.append(track_payload)
            except ValueError:
                # 跳过无法获取时长的曲目
                continue

    # 随机打乱其他曲目（保持随机性）
    rng.shuffle(fresh_tracks)
    rng.shuffle(used_tracks)
    if avoid_recent_tracks and not fresh_tracks:
        log_warning("All tracks are marked as recently used; falling back to full pool")

    other_tracks = fresh_tracks + used_tracks
    
    # 必须满足：总时长 >= max(target_seconds, MIN_TOTAL_DURATION_SECONDS)
    # 这样才能确保分成两半后，每半都 >= MIN_SIDE_DURATION_SECONDS
    required_total = max(target_seconds, MIN_TOTAL_DURATION_SECONDS)
    
    # 随机选择其他曲目，直到满足时长要求
    # 需要确保分配后每面都能满足最小时长要求
    # 如果达到26首限制但分配仍不满足，允许继续选择直到满足要求
    max_attempts = len(other_tracks)  # 最多尝试所有可用曲目
    attempts = 0
    
    for track in other_tracks:
        attempts += 1
        if attempts > max_attempts:
            break
        
        duration = track["duration_seconds"]
        
        # 尝试添加这首曲目，检查是否能满足分配要求
        test_selected = selected + [track]
        test_total_duration = total_duration + duration
        
        # 尝试分配，检查每面是否都能满足最小时长
        test_side_a, test_side_b = _try_distribute_tracks(
            test_selected, must_include_track_ids, MIN_SIDE_DURATION_SECONDS
        )
        
        test_side_a_total = sum(t["duration_seconds"] for t in test_side_a)
        test_side_b_total = sum(t["duration_seconds"] for t in test_side_b)
        
        # 如果分配后每面都满足最小时长，或者还没达到最小总时长，则添加
        if (test_side_a_total >= MIN_SIDE_DURATION_SECONDS and 
            test_side_b_total >= MIN_SIDE_DURATION_SECONDS):
            # 分配满足要求，添加这首曲目
            selected.append(track)
            total_duration += duration
            # 如果已达到最小总时长且分配满足，可以停止
            if total_duration >= required_total:
                break
        elif total_duration < required_total:
            # 还没达到最小总时长，即使分配不满足也要继续选（后面会再检查）
            selected.append(track)
            total_duration += duration
        else:
            # 已达到最小总时长但分配不满足，继续选曲直到分配满足
            # 即使超过26首限制也要继续，直到满足分配要求
            selected.append(track)
            total_duration += duration
            # 如果分配满足，可以停止
            if (test_side_a_total >= MIN_SIDE_DURATION_SECONDS and 
                test_side_b_total >= MIN_SIDE_DURATION_SECONDS):
                break
    
    # 验证总时长是否足够
    if total_duration < MIN_TOTAL_DURATION_SECONDS:
        raise ValueError(
            f"Total selected duration ({total_duration // 60}:{total_duration % 60:02d}) "
            f"is less than minimum required ({MIN_TOTAL_DURATION_SECONDS // 60}:{MIN_TOTAL_DURATION_SECONDS % 60:02d}) "
            f"for two sides (each >= {MIN_SIDE_DURATION_SECONDS // 60}:{MIN_SIDE_DURATION_SECONDS % 60:02d}). "
            f"Selected {len(selected)} tracks (max: {MAX_TRACKS}). Need longer tracks or more tracks."
        )
    
    # 验证总曲目数（放宽限制：如果分配满足要求，允许超过26首）
    if len(selected) > MAX_TRACKS:
        # 检查分配是否满足要求
        side_a, side_b = _try_distribute_tracks(selected, must_include_track_ids, MIN_SIDE_DURATION_SECONDS)
        side_a_total = sum(t["duration_seconds"] for t in side_a)
        side_b_total = sum(t["duration_seconds"] for t in side_b)
        
        if (side_a_total < MIN_SIDE_DURATION_SECONDS or 
            side_b_total < MIN_SIDE_DURATION_SECONDS):
            # 即使超过限制，分配仍不满足，这是真正的错误
            raise ValueError(
                f"Selected {len(selected)} tracks (exceeds maximum {MAX_TRACKS}), "
                f"but Side A duration ({side_a_total // 60}:{side_a_total % 60:02d}) or "
                f"Side B duration ({side_b_total // 60}:{side_b_total % 60:02d}) "
                f"is still less than minimum required ({MIN_SIDE_DURATION_SECONDS // 60}:{MIN_SIDE_DURATION_SECONDS % 60:02d}). "
                f"Need longer tracks or more tracks in library."
            )
        else:
            # 超过限制但分配满足，记录警告但继续
            log_warning(
                f"Selected {len(selected)} tracks, exceeds recommended maximum {MAX_TRACKS} tracks, "
                f"but distribution satisfies minimum duration requirements."
            )
    
    # 分成 A/B 面，确保每面 >= 29分39秒 (1779秒)
    side_a, side_b = _try_distribute_tracks(selected, must_include_track_ids, MIN_SIDE_DURATION_SECONDS)
    
    # 验证每面时长
    side_a_total = sum(t["duration_seconds"] for t in side_a)
    side_b_total = sum(t["duration_seconds"] for t in side_b)
    
    if side_a_total < MIN_SIDE_DURATION_SECONDS:
        raise ValueError(
            f"Side A duration ({side_a_total // 60}:{side_a_total % 60:02d}) "
            f"is less than minimum required ({MIN_SIDE_DURATION_SECONDS // 60}:{MIN_SIDE_DURATION_SECONDS % 60:02d}). "
            f"Total selected duration: {total_duration // 60}:{total_duration % 60:02d}. "
            f"Need to select more tracks."
        )
    
    if side_b_total < MIN_SIDE_DURATION_SECONDS:
        raise ValueError(
            f"Side B duration ({side_b_total // 60}:{side_b_total % 60:02d}) "
            f"is less than minimum required ({MIN_SIDE_DURATION_SECONDS // 60}:{MIN_SIDE_DURATION_SECONDS % 60:02d}). "
            f"Total selected duration: {total_duration // 60}:{total_duration % 60:02d}. "
            f"Need to select more tracks."
        )
    
    log_info(f"Side A: {len(side_a)} tracks, {side_a_total // 60}:{side_a_total % 60:02d} (min: {MIN_SIDE_DURATION_SECONDS // 60}:{MIN_SIDE_DURATION_SECONDS % 60:02d})")
    log_info(f"Side B: {len(side_b)} tracks, {side_b_total // 60}:{side_b_total % 60:02d} (min: {MIN_SIDE_DURATION_SECONDS // 60}:{MIN_SIDE_DURATION_SECONDS % 60:02d})")
    
    return side_a, side_b


def _calculate_needle_timeline_duration(side_a: list[dict], side_b: list[dict]) -> int:
    """
    计算 Needle timeline 的总时长（包括所有 SFX）
    
    计算方式与 mp3 合成方式相同：
    - Side A 开始：Needle On Vinyl Record (3秒)
    - Side A 曲目：每首曲目使用完整 duration_seconds（不再减2秒）
    - Side A 曲目之间：Vinyl Noise 在时间轴上只贡献 3 秒"间隔"（实际7秒音频重叠在曲目上）
    - A 面结束后：Silence (3秒)
    - Side B 开始：Needle On Vinyl Record (3秒)
    - Side B 曲目：每首曲目使用完整 duration_seconds
    - Side B 曲目之间：Vinyl Noise 3 秒间隔
    
    公式：总时长 = 3秒开头 + Σ(曲目完整时长) + (曲目数-1) × 3秒间隙 + 3秒Silence
    
    注意：SFX 时长必须与 mix.py 中的常量对齐：
    - NEEDLE_TARGET_DURATION = 3.0
    - VINYL_TIMELINE_INTERVAL = 3.0（时间轴上的间隔，不是音频长度）
    - SILENCE_DURATION = 3.0
    
    Args:
        side_a: A 面曲目列表
        side_b: B 面曲目列表
    
    Returns:
        总时长（秒）
    """
    # SFX 时长常量（与 mix.py 对齐）
    NEEDLE_TARGET_DURATION = 3.0
    VINYL_TIMELINE_INTERVAL = 3.0  # 时间轴上的间隔（实际7秒音频重叠在曲目上）
    SILENCE_DURATION = 3.0
    
    total_time = 0
    
    # Side A 开始：Needle On Vinyl Record
    total_time += NEEDLE_TARGET_DURATION
    
    # Side A 曲目：使用完整时长
    for idx, track in enumerate(side_a):
        d = track["duration_seconds"]
        total_time += d
        # 如果不是最后一首，添加 Vinyl Noise 间隔（3秒）
        if idx < len(side_a) - 1:
            total_time += VINYL_TIMELINE_INTERVAL
    
    # A 面结束后，3 秒静音
    total_time += SILENCE_DURATION
    
    # Side B 开始：Needle On Vinyl Record
    total_time += NEEDLE_TARGET_DURATION
    
    # Side B 曲目：使用完整时长
    for idx, track in enumerate(side_b):
        d = track["duration_seconds"]
        total_time += d
        # 如果不是最后一首，添加 Vinyl Noise 间隔（3秒）
        if idx < len(side_b) - 1:
            total_time += VINYL_TIMELINE_INTERVAL
    
    return int(total_time)


def _write_playlist_csv(
    paths: AssetPaths,
    side_a: list[dict],
    side_b: list[dict],
    episode_id: str,
) -> None:
    """
    写入 playlist.csv 文件
    
    包含：
    1. Metadata 和 Summary 行（包含总时长）
    2. Track 行（曲目列表）
    3. Timeline 行（Needle 时间轴，包含 SFX）
    4. Clean Timeline 行（不含 SFX，用于字幕生成）
    """
    paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
    
    def format_timestamp(seconds: float | int) -> str:
        """将秒数转换为 M:SS 格式"""
        seconds_int = int(seconds)
        minutes, secs = divmod(seconds_int, 60)
        return f"{minutes}:{secs:02d}"
    
    # 计算 Needle timeline 总时长（与 mp3 合成方式相同）
    total_audio_duration = _calculate_needle_timeline_duration(side_a, side_b)
    
    with paths.playlist_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        
        # CSV 头部（符合旧世界格式）
        writer.writerow([
            "Section", "Field", "Value", "Side", "Order",
            "Title", "Duration", "DurationSeconds",
            "Timeline", "Timestamp", "Description",
        ])
        
        # 元信息（包含总时长）
        # 注意：AlbumTitle 字段将在 TEXT_BASE 阶段生成真正的专辑标题后写入
        # 这里只写入 EpisodeId 作为标识
        writer.writerow([
            "Metadata", "EpisodeId", episode_id, "", "", "", "", "", "", "", ""
        ])
        writer.writerow([
            "Metadata", "TotalDuration", format_timestamp(total_audio_duration),
            "", "", "", "", "", "", "", ""
        ])
        
        # A 面 Track 行
        total_a = sum(t["duration_seconds"] for t in side_a)
        total_a_int = int(total_a)
        writer.writerow([
            "Summary", "SideTotal", f"{len(side_a)} tracks",
            "A", "", "", f"{total_a_int // 60}:{total_a_int % 60:02d}", total_a_int, "", "", "",
        ])
        
        for idx, track in enumerate(side_a, 1):
            d_int = int(track["duration_seconds"])
            writer.writerow([
                "Track", "Song", track["file_path"],
                "A", idx, track["title"],
                f"{d_int // 60}:{d_int % 60:02d}",
                d_int,
                "", "", "",
            ])
        
        # B 面 Track 行
        total_b = sum(t["duration_seconds"] for t in side_b)
        total_b_int = int(total_b)
        writer.writerow([
            "Summary", "SideTotal", f"{len(side_b)} tracks",
            "B", "", "", f"{total_b_int // 60}:{total_b_int % 60:02d}", total_b_int, "", "", "",
        ])
        
        for idx, track in enumerate(side_b, 1):
            d_int = int(track["duration_seconds"])
            writer.writerow([
                "Track", "Song", track["file_path"],
                "B", idx, track["title"],
                f"{d_int // 60}:{d_int % 60:02d}",
                d_int,
                "", "", "",
            ])
        
        # Timeline 行（Needle 时间轴，包含 SFX）
        # 用于混音，包含 "Needle On Vinyl Record"、"Vinyl Noise"、"Silence" 等 SFX
        # 时间轴公式：3秒开头 + Σ(曲目完整时长) + (曲目数-1) × 3秒间隙
        current_time = 0
        
        # 记录每首曲目在 Needle timeline 中的开始时间（用于 Clean timeline 对齐）
        # 使用 file_path 作为 key，避免重名曲目导致时间戳错位
        track_needle_times = {}  # {file_path: needle_start_time}
        
        # Side A 开始：Needle On Vinyl Record
        writer.writerow([
            "Timeline", "", "", "A", "", "", "", "", "Needle", format_timestamp(current_time),
            "Needle On Vinyl Record"
        ])
        # Needle 固定 3 秒，Track1 从 3 秒开始
        current_time += 3  # Needle 音效持续 3 秒（与 mix.py 的 NEEDLE_TARGET_DURATION 对齐）
        
        # Side A 曲目：使用完整时长，不再减2秒
        for idx, track in enumerate(side_a):
            track_key = track["file_path"]
            track_title = track["title"]
            d = float(track["duration_seconds"])
            
            # 记录曲目在 Needle timeline 中的开始时间（使用 file_path 作为唯一标识）
            track_needle_times[track_key] = int(current_time)
            
            writer.writerow([
                "Timeline", "", "", "A", "", "", "", "", "Needle", format_timestamp(current_time),
                track_title
            ])
            # 下一首歌的起点 = 当前起点 + 本曲全长
            current_time += d
            
            # 如果不是最后一首，添加 Vinyl Noise（时间轴上只占3秒间隔）
            if idx < len(side_a) - 1:
                # Vinyl Noise 的 start_time 放在"当前曲目结束前2秒"（实际7秒音频会重叠）
                # 但时间轴只推进3秒，表示"间隔"
                vinyl_start_time = current_time - 2  # 提前2秒开始（重叠在曲目尾部）
                writer.writerow([
                    "Timeline", "", "", "A", "", "", "", "", "Needle", format_timestamp(vinyl_start_time),
                    "Vinyl Noise"
                ])
                # 时间轴推进3秒（间隔），实际7秒音频重叠在前后曲目上
                current_time += 3  # Vinyl Noise 在时间轴上只占3秒间隔
        
        # A 面结束后，3 秒静音
        writer.writerow([
            "Timeline", "", "", "A", "", "", "", "", "Needle", format_timestamp(current_time),
            "Silence"
        ])
        current_time += 3  # Silence 持续 3 秒（与 mix.py 的 SILENCE_DURATION 对齐）
        
        # Side B 开始：Needle On Vinyl Record
        writer.writerow([
            "Timeline", "", "", "B", "", "", "", "", "Needle", format_timestamp(current_time),
            "Needle On Vinyl Record"
        ])
        current_time += 3  # Needle 音效持续 3 秒（与 mix.py 的 NEEDLE_TARGET_DURATION 对齐）
        
        # Side B 曲目：使用完整时长，不再减2秒
        for idx, track in enumerate(side_b):
            track_key = track["file_path"]
            track_title = track["title"]
            d = float(track["duration_seconds"])
            
            # 记录曲目在 Needle timeline 中的开始时间（使用 file_path 作为唯一标识）
            track_needle_times[track_key] = int(current_time)
            
            writer.writerow([
                "Timeline", "", "", "B", "", "", "", "", "Needle", format_timestamp(current_time),
                track_title
            ])
            # 下一首歌的起点 = 当前起点 + 本曲全长
            current_time += d
            
            # 如果不是最后一首，添加 Vinyl Noise（时间轴上只占3秒间隔）
            if idx < len(side_b) - 1:
                # Vinyl Noise 的 start_time 放在"当前曲目结束前2秒"（实际7秒音频会重叠）
                # 但时间轴只推进3秒，表示"间隔"
                vinyl_start_time = current_time - 2  # 提前2秒开始（重叠在曲目尾部）
                writer.writerow([
                    "Timeline", "", "", "B", "", "", "", "", "Needle", format_timestamp(vinyl_start_time),
                    "Vinyl Noise"
                ])
                # 时间轴推进3秒（间隔），实际7秒音频重叠在前后曲目上
                current_time += 3  # Vinyl Noise 在时间轴上只占3秒间隔
        
        # Clean Timeline 行（不含 SFX，用于字幕生成）
        # 使用 Needle timeline 中对应曲目的开始时间，确保时间对齐
        # 使用 file_path 作为 key，避免重名曲目导致时间戳错位
        # Side A 曲目（Clean）
        for track in side_a:
            track_key = track["file_path"]
            track_title = track["title"]
            # 使用 Needle timeline 中该曲目的开始时间（通过 file_path 匹配）
            clean_time = track_needle_times.get(track_key, 0)
            writer.writerow([
                "Timeline", "", "", "A", "", "", "", "", "Clean", format_timestamp(clean_time),
                track_title
            ])
        
        # Side B 曲目（Clean）
        for track in side_b:
            track_key = track["file_path"]
            track_title = track["title"]
            # 使用 Needle timeline 中该曲目的开始时间（通过 file_path 匹配）
            clean_time = track_needle_times.get(track_key, 0)
            writer.writerow([
                "Timeline", "", "", "B", "", "", "", "", "Clean", format_timestamp(clean_time),
                track_title
            ])


def _write_recipe_json(
    paths: AssetPaths,
    spec: EpisodeSpec,
    side_a: list[dict],
    side_b: list[dict],
    image_filename: str | None = None,
    cover_source_filename: str | None = None,
) -> None:
    """
    写入 recipe.json 文件
    
    Args:
        paths: AssetPaths
        spec: EpisodeSpec
        side_a: A 面曲目列表
        side_b: B 面曲目列表
        image_filename: 选定的图片文件名（可选，如果 INIT 阶段已选图）
    """
    paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
    
    # 独立计算 Needle timeline 总时长（与 playlist.csv 计算方式相同）
    total_audio_duration = _calculate_needle_timeline_duration(side_a, side_b)
    
    existing: dict[str, Any] = {}
    if paths.recipe_json.exists():
        try:
            existing = json.loads(paths.recipe_json.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except Exception:
            existing = {}

    # Base recipe generated by INIT (authoritative for track list + durations).
    recipe: dict[str, Any] = dict(existing)
    recipe["episode_id"] = spec.episode_id
    recipe["channel_id"] = spec.channel_id
    # Keep an existing schedule_date if present; otherwise write a sensible default.
    recipe["schedule_date"] = recipe.get("schedule_date") or spec.date or datetime.now().strftime("%Y-%m-%d")
    recipe["created_at"] = recipe.get("created_at") or datetime.now().isoformat()
    recipe["stages"] = ["init", "cover", "text", "mix", "render"]

    existing_assets = existing.get("assets")
    if not isinstance(existing_assets, dict):
        existing_assets = {}

    assets: dict[str, Any] = {
        "tracks": [t["file_path"] for t in side_a + side_b],
        "side_a_count": len(side_a),
        "side_b_count": len(side_b),
        "total_audio_duration_seconds": total_audio_duration,
        "total_audio_duration_formatted": f"{int(total_audio_duration) // 60}:{int(total_audio_duration) % 60:02d}",
    }
    # Preserve theme_color_rgb written by Plan/COVER stages if present.
    if "theme_color_rgb" in existing_assets:
        assets["theme_color_rgb"] = existing_assets.get("theme_color_rgb")
    recipe["assets"] = assets
    
    # Cover selection metadata (Plan-stage compatible).
    if image_filename:
        recipe["cover_image_filename"] = image_filename
    else:
        # Preserve an existing planned value if INIT didn't supply one.
        if existing.get("cover_image_filename") and not recipe.get("cover_image_filename"):
            recipe["cover_image_filename"] = existing.get("cover_image_filename")

    if cover_source_filename:
        recipe.setdefault("cover_source_filename", cover_source_filename)

    with paths.recipe_json.open("w", encoding="utf-8") as f:
        json.dump(recipe, f, ensure_ascii=False, indent=2)


async def init_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    """
    初始化一期节目，生成 playlist.csv 和 recipe.json
    
    Interface Contract: async def init_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult
    
    从零实现，只依赖文件系统和基础工具函数，不调用旧世界的路由或复杂逻辑。
    输出文件：paths.playlist_csv, paths.recipe_json
    """
    started_at = datetime.now()
    
    try:
        # 确保输出目录存在
        paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 幂等性检查：如果文件已存在，跳过生成
        if paths.playlist_csv.exists() and paths.recipe_json.exists():
            log_info(f"Init already complete for {spec.episode_id}, skipping")
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            
            return StageResult(
                stage=StageName.INIT,
                success=True,
                duration_seconds=duration,
                key_asset_paths=[paths.playlist_csv, paths.recipe_json],
                started_at=started_at,
                finished_at=finished_at,
            )
        
        # 从 schedule 加载轻量配置（可选，如果不存在则使用默认配置）
        episode_config = _load_episode_config(spec.channel_id, spec.episode_id)
        if episode_config:
            log_info(f"Loaded episode config from schedule: target_duration={episode_config.get('target_duration_minutes')}min")
        else:
            log_info(f"No schedule config found for {spec.episode_id}, using defaults")
            episode_config = {
                "target_duration_minutes": 60,
                "special_tags": [],
                "must_include_track_ids": [],
            }
        
        # 获取曲库索引
        library_index = get_channel_library_songs(spec.channel_id)
        if not library_index:
            raise ValueError(f"No songs found in library for channel {spec.channel_id}")
        
        # 核心选曲算法（schedule 仅提供约束条件，不提供 track 列表）
        log_info(f"Generating playlist for {spec.episode_id} using algorithm...")
        side_a, side_b = generate_playlist_for_episode(
            spec=spec,
            library_index=library_index,
            config=episode_config,
            history=None,  # TODO: Load history for deduplication
        )
        
        log_info(f"Selected {len(side_a)} tracks for side A, {len(side_b)} tracks for side B")
        
        # 封面选图（Plan-stage 兼容）：
        # - 新工作流中：封面应在 Plan 阶段被复制进 episode 文件夹，并写入 recipe.json。
        # - INIT 阶段只负责读取 / 补齐，不再把图库图片提前 move 到 used。
        image_filename: str | None = None
        cover_source_filename: str | None = None
        config = get_config()

        # 1) 优先使用 recipe.json 里 Plan 阶段写入的封面信息
        if paths.recipe_json.exists():
            try:
                existing_recipe = json.loads(paths.recipe_json.read_text(encoding="utf-8"))
                image_filename = existing_recipe.get("cover_image_filename") or existing_recipe.get("image_filename")
                cover_source_filename = (
                    existing_recipe.get("cover_source_filename")
                    or existing_recipe.get("cover_image_source_filename")
                    or existing_recipe.get("cover_image_original_filename")
                )
            except Exception as e:
                log_warning(f"Failed to read existing recipe.json for cover planning: {e}")

        # 2) 如果没有 recipe.json（或缺字段），从 episode 目录探测一个候选图
        if not image_filename:
            local_candidates = [
                p for p in paths.episode_output_dir.glob("*.png")
                if p.name != paths.cover_png.name and not p.name.endswith("_cover.png")
            ]
            if local_candidates:
                local_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                image_filename = local_candidates[0].name
                log_info(f"Using episode-local planned cover image: {image_filename}")

        # 3) 兼容旧路径：如果仍无封面，则从 available 选一张，但只 COPY 到 episode 文件夹
        if not image_filename:
            available_images = list_available_images()
            used_images = _load_used_image_filenames(spec.channel_id, spec.episode_id)

            if not available_images:
                raise FileNotFoundError(
                    f"No images available in pool for {spec.episode_id}. 需要1张图才能继续制作。"
                )

            candidates = [
                img for img in available_images
                if img.name not in used_images and not (config.images_pool_used / img.name).exists()
            ]
            if not candidates:
                raise FileNotFoundError(
                    f"No unused images available for {spec.episode_id}; all candidates already used. 需要1张图才能继续制作。"
                )

            recent_used = _load_recent_used_images(spec.channel_id, limit=8)
            recent_signatures = {_image_signature(name) for name in recent_used if name}
            rng = random.SystemRandom()
            weights: list[float] = []
            for img in candidates:
                sig = _image_signature(img.name)
                weights.append(0.2 if sig in recent_signatures else 1.0)
            selected_image = rng.choices(candidates, weights=weights, k=1)[0]
            image_filename = selected_image.name
            cover_source_filename = selected_image.name

            dst = paths.episode_output_dir / image_filename
            if not dst.exists():
                shutil.copy2(selected_image, dst)
                log_info(f"Copied cover into episode folder: {dst.name}")
            else:
                log_info(f"Cover already present in episode folder: {dst.name}")

        if not image_filename:
            raise FileNotFoundError(
                f"Cover image missing for {spec.episode_id}. 请先运行 Plan 阶段分配封面图片。"
            )
        log_info(f"Using cover image for episode: {image_filename} (source={cover_source_filename or 'unknown'})")
        
        # 写入 playlist.csv
        log_info(f"Writing playlist.csv to {paths.playlist_csv}")
        _write_playlist_csv(paths, side_a, side_b, spec.episode_id)
        
        # 写入 recipe.json（包含选定的图片）
        log_info(f"Writing recipe.json to {paths.recipe_json}")
        _write_recipe_json(
            paths,
            spec,
            side_a,
            side_b,
            image_filename,
            cover_source_filename=cover_source_filename,
        )
        
        # 验证文件是否存在
        if not paths.playlist_csv.exists():
            raise FileNotFoundError(f"playlist.csv not found at {paths.playlist_csv}")
        if not paths.recipe_json.exists():
            raise FileNotFoundError(f"recipe.json not found at {paths.recipe_json}")
        
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        log_info(f"✅ Init complete for {spec.episode_id}: playlist={paths.playlist_csv.exists()}, recipe={paths.recipe_json.exists()}")
        
        return StageResult(
            stage=StageName.INIT,
            success=True,
            duration_seconds=duration,
            key_asset_paths=[paths.playlist_csv, paths.recipe_json],
            started_at=started_at,
            finished_at=finished_at,
        )
        
    except Exception as e:
        log_error(f"init_episode exception for {spec.episode_id}: {e}")
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        return StageResult(
            stage=StageName.INIT,
            success=False,
            duration_seconds=duration,
            key_asset_paths=[],
            error_message=str(e),
            started_at=started_at,
            finished_at=finished_at,
        )
