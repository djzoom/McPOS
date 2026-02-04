"""
文本资产生成

按照文档标准实现：生成 YouTube 标题、描述、标签和字幕。
TEXT_BASE 阶段：使用 playlist.csv 和 recipe.json 生成标题、描述、标签。
TEXT_SRT 阶段：使用 full_mix_timeline.csv 生成字幕。
"""

from pathlib import Path
from datetime import datetime as dt
from typing import Any
import csv
import json
import os

from ..models import EpisodeSpec, AssetPaths, StageResult, StageName
from ..core.logging import log_info, log_error, log_warning
from ..adapters.ai_title_generator import (
    EpisodeBudget,
    generate_album_title,
    generate_youtube_title_and_description,
)
from ..adapters.color_extractor import extract_theme_color, rgb_to_hex
from ..config import get_config, get_openai_api_key


def _generate_rbr_content(
    spec: EpisodeSpec,
    paths: AssetPaths,
    config: Any,
) -> tuple[str, str, list[str]]:
    """
    为 RBR 频道生成内容（标题、描述、标签）
    
    基于 BPM 和时长生成，参考 Yellow Runner Video Generator 的逻辑。
    
    Args:
        spec: EpisodeSpec
        paths: AssetPaths
        config: McPOSConfig
    
    Returns:
        (youtube_title, description, tags)
    """
    # 从 recipe.json 或 channel config 读取 BPM 和时长
    bpm = 175  # 默认 BPM
    duration_minutes = 60  # 默认时长
    
    # 尝试从 recipe.json 读取
    if paths.recipe_json.exists():
        try:
            with paths.recipe_json.open("r", encoding="utf-8") as f:
                recipe = json.load(f)
            bpm = recipe.get("bpm", bpm)
            duration_minutes = recipe.get("duration_minutes", duration_minutes)
            log_info(f"Loaded BPM={bpm}, duration={duration_minutes}min from recipe.json")
        except Exception as e:
            log_warning(f"Failed to read recipe.json: {e}")
    
    # 如果 recipe.json 中没有，尝试从 channel config 读取
    if bpm == 175 or duration_minutes == 60:
        try:
            channel_config_path = config.channels_root / spec.channel_id / "config" / "channel.json"
            if channel_config_path.exists():
                with channel_config_path.open("r", encoding="utf-8") as f:
                    channel_config = json.load(f)
                bpm = channel_config.get("default_bpm", bpm)
                duration_minutes = channel_config.get("default_duration_minutes", duration_minutes)
                log_info(f"Loaded BPM={bpm}, duration={duration_minutes}min from channel config")
        except Exception as e:
            log_warning(f"Failed to read channel config: {e}")
    
    # RBR 内容生成逻辑（参考 Yellow Runner Video Generator）
    ACTION_PHRASES = [
        "Surpass Your Tempo",
        "Boost Your Endurance",
        "Own Every Stride",
        "Fuel Your Tempo Run",
        "Ride the Rhythm",
    ]
    
    TARGET_AUDIENCES = [
        "Built for Marathon Pace Setters",
        "Perfect for Progressive Runs",
        "Designed for Tempo Specialists",
        "Ideal for Endurance Athletes",
        "Tuned for Consistent Stride Seekers",
    ]
    
    def _choose_phrase(bpm: int, options: list[str]) -> str:
        return options[bpm % len(options)]
    
    action_phrase = _choose_phrase(bpm, ACTION_PHRASES)
    series_tagline = _choose_phrase(bpm // 5, TARGET_AUDIENCES)
    
    # 生成标题
    title = (
        f"{duration_minutes}-Minute {bpm}BPM Running Music | "
        f"{action_phrase} | {series_tagline}"
    )
    
    # 生成描述
    description = (
        "Welcome to Run Baby Run – your ultimate source for tempo-perfect running music!\n\n"
        f"This {duration_minutes}-minute mix at {bpm} BPM is engineered to boost endurance and rhythm – "
        "ideal for runners seeking consistent pace.\n"
        f"✨ Series Spotlight: {series_tagline}. Fresh energy every single play.\n\n"
        "🔥 What to Expect:\n"
        f"- Steady {bpm} BPM rhythm aligned with optimal stride frequency\n"
        "- Motivational beats for sustained energy\n"
        "- Seamless transitions for treadmill, road, or marathon training\n\n"
        "🎧 Best experienced with headphones. Get in the zone and own your run.\n\n"
        "▶️ Explore More BPM-Specific Mixes:\n"
        "https://www.youtube.com/@Run-Baby-Run/playlists\n\n"
        "📲 Stay Connected with Run Baby Run:\n"
        "- Subscribe for weekly BPM drops and exclusive persona releases\n"
        "- Like & share to empower your running tribe\n"
        "- Comment your goal pace so we can craft the next mix for you\n\n"
        f"🏷️ Tags:\n#runningmusic #{bpm}BPM #runningmix #RunBabyRun #cardioworkout #fitnessmusic #joggingplaylist"
    )
    
    # 生成标签
    TAG_BASE = [
        "running music",
        "running mix",
        "Run Baby Run",
        "cardio workout",
        "fitness music",
        "jogging playlist",
        "tempo run",
        "marathon training",
        "endurance beats",
        "treadmill mix",
        "high energy playlist",
    ]
    
    tags = list(
        dict.fromkeys(
            [
                *TAG_BASE,
                f"{bpm} bpm",
                f"{duration_minutes} minute mix",
            ]
        )
    )
    
    log_info(f"Generated RBR content: BPM={bpm}, duration={duration_minutes}min")
    
    return title, description, tags


async def generate_text_base_assets(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    """
    生成文本基础资产（标题、描述、标签）
    
    Interface Contract: async def generate_text_base_assets(spec: EpisodeSpec, paths: AssetPaths) -> StageResult
    
    按照文档标准实现：
    - 使用 playlist.csv 读取曲目信息
    - 使用 recipe.json 读取封面图片和主题色（如果可用）
    - 优先使用 AI 生成标题和描述，失败时回退到模板生成
    - 生成 YouTube 标题、描述、标签文件
    
    输出文件：
    - paths.youtube_title_txt (<episode_id>_youtube_title.txt)
    - paths.youtube_description_txt (<episode_id>_youtube_description.txt)
    - paths.youtube_tags_txt (<episode_id>_youtube_tags.txt)
    
    依赖：
    - playlist.csv (必需, 来自 INIT 阶段)
    - recipe.json (可选, 来自 INIT/COVER 阶段, 用于主题色和封面图片信息)
    """
    started_at = dt.now()
    
    try:
        # 幂等性检查：如果所有文件都已存在，跳过生成
        if (paths.youtube_title_txt.exists() and
            paths.youtube_description_txt.exists() and
            paths.youtube_tags_txt.exists()):
            log_info(f"Text base assets already complete for {spec.episode_id}, skipping")
            finished_at = dt.now()
            duration = (finished_at - started_at).total_seconds()
            
            return StageResult(
                stage=StageName.TEXT_BASE,
                success=True,
                duration_seconds=duration,
                key_asset_paths=[
                    paths.youtube_title_txt,
                    paths.youtube_description_txt,
                    paths.youtube_tags_txt,
                ],
                started_at=started_at,
                finished_at=finished_at,
            )
        
        # 确保输出目录存在
        paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查必需输入文件
        if not paths.playlist_csv.exists():
            raise FileNotFoundError(
                f"playlist.csv not found at {paths.playlist_csv}. Run INIT stage first."
            )
        
        # 读取 playlist.csv
        log_info(f"Reading playlist from {paths.playlist_csv}")
        tracks_a = []
        tracks_b = []
        track_titles = []
        
        with paths.playlist_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                section = (row.get("Section") or "").strip()
                if section == "Track":
                    title = (row.get("Title") or "").strip()
                    side = (row.get("Side") or "").strip().upper()
                    duration_str = (row.get("DurationSeconds") or "").strip()
                    
                    if title:
                        # 解析时长（用于 AI prompt，如果解析失败则跳过该曲目）
                        duration_seconds = None
                        if duration_str:
                            try:
                                duration_seconds = int(duration_str)
                            except ValueError:
                                log_warning(f"Invalid DurationSeconds for track {title}: {duration_str}, skipping duration")
                        
                        track_data = {
                            "title": title,
                            "duration_seconds": duration_seconds,
                        }
                        
                        if side == "A":
                            tracks_a.append(track_data)
                        elif side == "B":
                            tracks_b.append(track_data)
                        
                        track_titles.append(title)
        
        if not track_titles:
            raise ValueError(f"No tracks found in playlist.csv for {spec.episode_id}")
        
        log_info(f"Found {len(tracks_a)} tracks on Side A, {len(tracks_b)} tracks on Side B")
        
        # 读取 recipe.json（用于主题色和封面图片信息）
        cover_image_filename = None
        theme_color_rgb = None
        album_title_from_recipe = None
        
        if paths.recipe_json.exists():
            try:
                with paths.recipe_json.open("r", encoding="utf-8") as f:
                    recipe = json.load(f)
                
                # 读取封面图片文件名
                cover_image_filename = recipe.get("cover_image_filename") or recipe.get("image_filename")
                album_title_from_recipe = recipe.get("album_title")
                
                # 尝试从 recipe 读取主题色（如果 COVER 阶段已写入）
                assets = recipe.get("assets", {})
                if "theme_color_rgb" in assets:
                    rgb_list = assets["theme_color_rgb"]
                    if isinstance(rgb_list, list) and len(rgb_list) == 3:
                        theme_color_rgb = tuple(rgb_list)
                        log_info(f"Using theme color from recipe.json: {theme_color_rgb}")
            except Exception as e:
                log_warning(f"Failed to read recipe.json: {e}")
        
        # 获取配置（用于后续使用）
        config = get_config()
        
        # 如果 recipe 中没有主题色，尝试从封面图片提取
        if theme_color_rgb is None and cover_image_filename:
            cover_candidates = [
                paths.episode_output_dir / cover_image_filename,  # Plan-stage episode-local copy
                config.images_pool_root / "used" / cover_image_filename,  # legacy path
                config.images_pool_root / "available" / cover_image_filename,  # rare fallback
            ]
            cover_image_path = next((p for p in cover_candidates if p.exists()), None)

            if cover_image_path is not None:
                try:
                    theme_color_rgb = extract_theme_color(cover_image_path)
                    if theme_color_rgb:
                        log_info(f"Extracted theme color from cover image: {theme_color_rgb}")
                except Exception as e:
                    log_warning(f"Failed to extract theme color from cover image: {e}")
        
        # RBR 频道使用特定的内容生成逻辑（基于 BPM 和时长）
        if spec.channel_id == "rbr":
            log_info("Using RBR channel-specific content generation...")
            youtube_title, description, tags = _generate_rbr_content(
                spec=spec,
                paths=paths,
                config=config,
            )
        else:
            # Kat 频道使用 AI 生成标题和描述（必需，不允许 fallback）
            # 根据 Dev_Bible：没有 API AI 可用时，不 fallback，使用接口报错并停止工作
            api_key = get_openai_api_key()
            
            if not api_key or not api_key.strip():
                # 提供更详细的错误信息和解决方案
                error_msg = (
                    "OPENAI_API_KEY not set. AI title generation is required for TEXT_BASE stage.\n"
                    "\n"
                    "解决方案（选择一种，推荐方法 1）：\n"
                    "1. 使用配置文件（推荐，永久生效）：\n"
                    "   将 API key 写入 config/openai_api_key.txt 文件\n"
                    "   echo 'your-api-key-here' > config/openai_api_key.txt\n"
                    "\n"
                    "2. 在当前 shell 中设置（临时）：\n"
                    "   export OPENAI_API_KEY='your-api-key-here'\n"
                    "\n"
                    "3. 使用 .envrc（如果存在）：\n"
                    "   source .envrc\n"
                    "\n"
                    "4. 在命令前设置（单次使用）：\n"
                    "   OPENAI_API_KEY='your-api-key-here' python3 -m mcpos.cli.main run-stage kat kat_20251201 TEXT_BASE\n"
                )
                raise RuntimeError(error_msg)
            
            log_info("Generating titles and description with AI...")
            
            # 处理日期格式：spec.date 是字符串（YYYYMMDD），需要转换为 ISO 格式（YYYY-MM-DD）
            episode_date_iso = None
            if spec.date:
                try:
                    # 尝试解析 YYYYMMDD 格式
                    if len(spec.date) == 8 and spec.date.isdigit():
                        # 格式化为 YYYY-MM-DD
                        episode_date_iso = f"{spec.date[:4]}-{spec.date[4:6]}-{spec.date[6:8]}"
                    else:
                        # 如果已经是其他格式，尝试解析为日期对象
                        date_obj = dt.strptime(spec.date, "%Y-%m-%d")
                        episode_date_iso = date_obj.isoformat()[:10]  # 只取日期部分
                except Exception as e:
                    log_warning(f"Failed to parse date '{spec.date}': {e}, using as-is")
                    episode_date_iso = spec.date
            
            # Plan-stage compatibility:
            # - Album title may already be written into recipe.json during Plan stage.
            # - YouTube title may already exist (<episode_id>_youtube_title.txt) from Plan stage.
            planned_youtube_title = None
            if paths.youtube_title_txt.exists():
                try:
                    planned_youtube_title = paths.youtube_title_txt.read_text(encoding="utf-8").strip() or None
                except Exception as e:
                    log_warning(f"Failed to read planned YouTube title: {e}")

            album_title = None
            if album_title_from_recipe and str(album_title_from_recipe).strip():
                album_title = str(album_title_from_recipe).strip()
                budget = EpisodeBudget(max_calls=1)  # only description call is allowed in this stage
                log_info(f"Using planned album title from recipe.json: {album_title}")
            else:
                budget = EpisodeBudget(max_calls=2)
                album_title = await generate_album_title(
                    track_titles=track_titles,
                    image_filename=cover_image_filename or "",
                    theme_color_rgb=theme_color_rgb or (0, 0, 0),
                    episode_date=episode_date_iso,
                    api_key=api_key,
                    channel_id=spec.channel_id,
                    budget=budget,
                )

                # 将专辑标题写入 recipe.json（供 COVER 阶段使用，仅 Kat 频道）
                if paths.recipe_json.exists():
                    try:
                        with paths.recipe_json.open("r", encoding="utf-8") as f:
                            recipe = json.load(f)
                        recipe["album_title"] = album_title
                        with paths.recipe_json.open("w", encoding="utf-8") as f:
                            json.dump(recipe, f, ensure_ascii=False, indent=2)
                        log_info(f"Updated recipe.json with album_title: {album_title}")
                    except Exception as e:
                        log_warning(f"Failed to update recipe.json with album_title: {e}")

            # 构建 playlist_data 用于 YouTube 标题和描述生成
            playlist_data = {
                "tracks_a": tracks_a,
                "tracks_b": tracks_b,
            }

            # 生成 YouTube 标题和描述（YouTube 标题不调用 AI；描述可选单次 AI）
            generated_youtube_title, description = await generate_youtube_title_and_description(
                album_title=album_title,
                playlist_data=playlist_data,
                api_key=api_key,
                channel_id=spec.channel_id,
                budget=budget,
            )

            youtube_title = planned_youtube_title or generated_youtube_title
            if planned_youtube_title and planned_youtube_title != generated_youtube_title:
                log_warning(
                    "Planned YouTube title differs from regenerated deterministic title; "
                    "keeping planned title."
                )

            log_info(f"AI generation successful: album_title={album_title}, youtube_title={youtube_title}")
            
            # Kat 频道标签（基于曲目和频道）
            tags = [
                "#KatRecords",
                "#vibecoding",
                "#vinylsession",
                "#jazzambient",
                "#nightmusic",
                "#cityrain",
                "#chillinstrumental",
                "#sounddiary",
                "#creativefocus",
                "#analogdreams",
                "#sleepmusic",
                "#studybeats",
                "#lofisoul",
                "#nightdrive",
                "#cozyvibes",
            ]
            
            # 添加曲目相关的标签（取前 5 首）
            for track_title in track_titles[:5]:
                # 简单提取关键词作为标签
                words = track_title.split()
                for word in words[:2]:  # 每首曲目最多 2 个词
                    if len(word) > 3:  # 过滤太短的词
                        tags.append(f"#{word}")
        
        # 写入文件（两个分支共用）
        # Plan-stage compatibility: if title already exists, keep it.
        try:
            existing_title = paths.youtube_title_txt.read_text(encoding="utf-8").strip() if paths.youtube_title_txt.exists() else ""
        except Exception:
            existing_title = ""

        if not existing_title:
            paths.youtube_title_txt.write_text(youtube_title, encoding="utf-8")
        else:
            log_info(f"YouTube title already exists for {spec.episode_id}, keeping planned title file")
        paths.youtube_description_txt.write_text(description, encoding="utf-8")
        paths.youtube_tags_txt.write_text("\n".join(tags), encoding="utf-8")
        
        log_info(f"✅ Text base assets generated for {spec.episode_id}")
        
        finished_at = dt.now()
        duration = (finished_at - started_at).total_seconds()
        
        return StageResult(
            stage=StageName.TEXT_BASE,
            success=True,
            duration_seconds=duration,
            key_asset_paths=[
                paths.youtube_title_txt,
                paths.youtube_description_txt,
                paths.youtube_tags_txt,
            ],
            started_at=started_at,
            finished_at=finished_at,
        )
        
    except Exception as e:
        import traceback
        log_error(f"generate_text_base_assets exception for {spec.episode_id}: {e}\n{traceback.format_exc()}")
        finished_at = dt.now()
        duration = (finished_at - started_at).total_seconds()
        
        return StageResult(
            stage=StageName.TEXT_BASE,
            success=False,
            duration_seconds=duration,
            key_asset_paths=[],
            error_message=str(e),
            started_at=started_at,
            finished_at=finished_at,
        )


async def generate_text_srt(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    """
    生成字幕文件（SRT 格式）
    
    Interface Contract: async def generate_text_srt(spec: EpisodeSpec, paths: AssetPaths) -> StageResult
    
    按照文档标准实现：
    - 使用 playlist.csv 的 Clean timeline 读取时间轴信息（不含 SFX）
    - 每个字幕显示 5 秒，提前 1 秒开始显示
    - 确保字幕不重叠
    
    输出文件：
    - paths.youtube_srt (<episode_id>_youtube.srt)
    
    依赖：
    - playlist.csv (必需, 来自 INIT 阶段，读取 Clean timeline)
    
    Note:
        - 假设两首歌之间的间隔至少 3 秒（混音规则中的 3 秒空档）
        - 如果混音间隙长度改变，需要相应调整此逻辑
        - Clean timeline 使用与 Needle timeline 相同的曲目开始时间，确保时间对齐
    """
    started_at = dt.now()
    
    try:
        # 幂等性检查：如果文件已存在，跳过生成
        if paths.youtube_srt.exists():
            log_info(f"SRT file already exists for {spec.episode_id}, skipping")
            finished_at = dt.now()
            duration = (finished_at - started_at).total_seconds()
            
            return StageResult(
                stage=StageName.TEXT_SRT,
                success=True,
                duration_seconds=duration,
                key_asset_paths=[paths.youtube_srt],
                started_at=started_at,
                finished_at=finished_at,
            )
        
        # 确保输出目录存在
        paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查必需输入文件
        if not paths.playlist_csv.exists():
            raise FileNotFoundError(
                f"playlist.csv not found at {paths.playlist_csv}. Run INIT stage first."
            )
        
        # 解析时间戳（M:SS 或 H:MM:SS 格式）为秒数
        def parse_timestamp_to_seconds(timestamp: str) -> float:
            """将 M:SS 或 H:MM:SS 格式的时间戳转换为秒数"""
            parts = timestamp.strip().split(":")
            if len(parts) == 2:
                # M:SS 格式
                minutes, seconds = int(parts[0]), int(parts[1])
                return minutes * 60.0 + seconds
            elif len(parts) == 3:
                # H:MM:SS 格式
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                return hours * 3600.0 + minutes * 60.0 + seconds
            else:
                raise ValueError(f"Invalid timestamp format: {timestamp}")
        
        # 读取 playlist.csv 的 Clean timeline 和 Track 信息
        log_info(f"Reading Clean timeline from {paths.playlist_csv}")
        timeline_entries = []
        track_durations: dict[str, int] = {}  # {title: duration_seconds}
        
        with paths.playlist_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                section = (row.get("Section") or "").strip()
                
                # 先读取 Track 行，建立 title -> duration_seconds 映射
                if section == "Track":
                    title = (row.get("Title") or "").strip()
                    duration_str = (row.get("DurationSeconds") or "").strip()
                    if title and duration_str:
                        try:
                            track_durations[title] = int(duration_str)
                        except ValueError:
                            log_warning(f"Invalid DurationSeconds for track {title}: {duration_str}")
                
                # 处理 Clean timeline 行
                timeline_type = (row.get("Timeline") or "").strip()
                timestamp_str = (row.get("Timestamp") or "").strip()
                description = (row.get("Description") or "").strip()
                
                if section == "Timeline" and timeline_type == "Clean" and timestamp_str and description:
                    try:
                        start_time = parse_timestamp_to_seconds(timestamp_str)
                        # 从 Track 行获取 duration_seconds（如果存在）
                        duration_seconds = track_durations.get(description, 0)
                        timeline_entries.append({
                            "start_time": start_time,
                            "duration_seconds": duration_seconds,
                            "title": description,
                        })
                    except (ValueError, IndexError) as e:
                        log_warning(f"Invalid timestamp in Clean timeline: {timestamp_str}, skipping: {e}")
        
        if not timeline_entries:
            raise ValueError(f"No valid Clean timeline entries found in {paths.playlist_csv}")
        
        # 显式按 start_time 排序，确保字幕按时间顺序显示
        timeline_entries.sort(key=lambda e: e["start_time"])
        
        log_info(f"Found {len(timeline_entries)} timeline entries")
        
        # 生成 SRT 文件
        SRT_DISPLAY_DURATION = 5.0  # 每个字幕显示 5 秒
        SRT_PREVIEW_OFFSET = 1.0    # 提前 1 秒开始显示
        
        srt_lines = []
        
        for idx, entry in enumerate(timeline_entries):
            track_start_time = entry["start_time"]
            track_title = entry["title"]
            
            # 字幕开始时间 = 曲目开始时间 - 1 秒（提前预览）
            srt_start_time = max(0.0, track_start_time - SRT_PREVIEW_OFFSET)
            
            # 字幕结束时间 = 开始时间 + 5 秒（显示时长）
            srt_end_time = srt_start_time + SRT_DISPLAY_DURATION
            
            # 如果下一首曲目开始时间更早，截断当前字幕
            if idx < len(timeline_entries) - 1:
                next_start_time = timeline_entries[idx + 1]["start_time"]
                # 提前 1 秒显示下一首，所以当前字幕应该在 next_start_time - 1 秒结束
                max_end_time = next_start_time - SRT_PREVIEW_OFFSET
                if srt_end_time > max_end_time:
                    srt_end_time = max(srt_start_time + 1.0, max_end_time)  # 至少显示 1 秒
            
            # 格式化时间戳（SRT 格式：HH:MM:SS,mmm）
            def format_srt_time(seconds: float) -> str:
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                millis = int((seconds % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
            
            srt_lines.append(f"{idx + 1}")
            srt_lines.append(f"{format_srt_time(srt_start_time)} --> {format_srt_time(srt_end_time)}")
            srt_lines.append(track_title)
            srt_lines.append("")  # 空行分隔
        
        # 写入 SRT 文件
        paths.youtube_srt.write_text("\n".join(srt_lines), encoding="utf-8")
        
        log_info(f"✅ SRT file generated for {spec.episode_id}: {len(timeline_entries)} subtitles")
        
        finished_at = dt.now()
        duration = (finished_at - started_at).total_seconds()
        
        return StageResult(
            stage=StageName.TEXT_SRT,
            success=True,
            duration_seconds=duration,
            key_asset_paths=[paths.youtube_srt],
            started_at=started_at,
            finished_at=finished_at,
        )
        
    except Exception as e:
        import traceback
        log_error(f"generate_text_srt exception for {spec.episode_id}: {e}\n{traceback.format_exc()}")
        finished_at = dt.now()
        duration = (finished_at - started_at).total_seconds()
        
        return StageResult(
            stage=StageName.TEXT_SRT,
            success=False,
            duration_seconds=duration,
            key_asset_paths=[],
            error_message=str(e),
            started_at=started_at,
            finished_at=finished_at,
        )
