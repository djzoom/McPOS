"""
音频混音

Timeline 模式：基于 playlist.csv 的 Timeline 事件，包含 SFX，适合 Lo-Fi 频道

输出：final_mix.mp3（256 kbps CBR, 48 kHz, 16-bit）

注意：DJ 混音模式已移除，RBR 频道请使用 mcpos/adapters/rbr_mix_engine.py
"""

from pathlib import Path
from datetime import datetime
import csv
from typing import Optional

from ..models import EpisodeSpec, AssetPaths, StageResult, StageName
from ..core.logging import log_info, log_error, log_warning
from ..config import get_config
from ..adapters.mix_engine import mix_episode_audio

# SFX 目标时长：和时间轴/TotalDuration 完全对齐
NEEDLE_TARGET_DURATION = 3.0   # Needle On Vinyl Record 在时间轴上占 3 秒（前 3 秒单独播放）
NEEDLE_FULL_DURATION = 7.0    # Needle On Vinyl Record 源文件总长 7 秒（后 4 秒与第一首歌混音）
VINYL_TARGET_DURATION = 7.0    # Vinyl Noise 实际听到 7 秒：前 2 秒渐入，中间 3 秒 plateau，最后 2 秒渐出
SILENCE_DURATION = 3.0         # 静音事件 3 秒

# SFX 的淡入淡出窗口
SFX_FADE_IN = 2.0   # Vinyl: 2 秒淡入
SFX_FADE_OUT = 2.0  # Vinyl: 2 秒淡出
NEEDLE_FADE_OUT = 0.5  # Needle: 最后 0.5 秒淡出（在 6.5-7 秒处）


def _parse_timestamp_to_ms(timestamp: str) -> int:
    """
    将时间戳转换为毫秒
    
    支持格式：
    - "M:SS" (例如 "3:45" = 225000ms)
    - "H:MM:SS" (例如 "1:23:45" = 5025000ms)
    """
    parts = timestamp.strip().split(":")
    if len(parts) == 2:
        # M:SS
        minutes, seconds = int(parts[0]), int(parts[1])
        return (minutes * 60 + seconds) * 1000
    elif len(parts) == 3:
        # H:MM:SS
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return (hours * 3600 + minutes * 60 + seconds) * 1000
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}")


def _parse_playlist_timeline(playlist_path: Path) -> tuple[list[dict], dict[str, dict]]:
    """
    解析 playlist.csv 的 Timeline 部分（Needle timeline）和 Track 部分
    
    Returns:
        tuple[list[dict], dict[str, dict]]:
            - events: Timeline 事件列表（包含 side, timestamp, description）
            - track_info: 映射 {description: {"file_path": str, "duration_seconds": int}}
    """
    events = []
    track_info: dict[str, dict] = {}
    
    if not playlist_path.exists():
        raise FileNotFoundError(f"playlist.csv not found at {playlist_path}")
    
    with playlist_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            section = (row.get("Section") or "").strip()
            
            # 解析 Track 行，建立 description -> (file_path, duration_seconds) 映射
            if section == "Track":
                title = (row.get("Title") or "").strip()
                file_path = (row.get("Value") or "").strip()  # Field="Song", Value=file_path
                duration_str = (row.get("DurationSeconds") or "").strip()
                
                if title and file_path and duration_str:
                    try:
                        duration_seconds = int(duration_str)
                        track_info[title] = {
                            "file_path": file_path,
                            "duration_seconds": duration_seconds,
                        }
                    except ValueError:
                        log_warning(f"Invalid DurationSeconds for track {title}: {duration_str}")
            
            # 解析 Timeline 行
            timeline_type = (row.get("Timeline") or "").strip()
            if section == "Timeline" and timeline_type == "Needle":
                events.append({
                    "side": (row.get("Side") or "").strip(),
                    "timestamp": (row.get("Timestamp") or "").strip(),
                    "description": (row.get("Description") or "").strip(),
                })
    
    return events, track_info


def _resolve_track_path(description: str, library_root: Path, extensions: list[str]) -> Path:
    """
    根据描述（曲目标题）解析音频文件路径
    
    Args:
        description: 曲目标题（来自 Timeline Description）
        library_root: 曲库根目录
        extensions: 支持的音频扩展名列表
    
    Returns:
        Path: 音频文件路径
    
    Raises:
        FileNotFoundError: 如果找不到文件
    
    Note:
        Title 可能经过了转换（下划线替换为空格，应用了 .title()），
        需要尝试多种变体来匹配实际文件名。
    """
    import re
    
    # 策略 1: 将所有空格替换为下划线（init.py 的逆操作，最接近原始写入时的变换）
    # init.py 使用: stem.replace("_", " ").title()
    # 逆变换: description.replace(' ', '_')
    variant2 = description.replace(' ', '_')
    for ext in extensions:
        path = library_root / f"{variant2}{ext}"
        if path.exists():
            return path
    
    # 策略 2: 直接匹配（原样）
    for ext in extensions:
        path = library_root / f"{description}{ext}"
        if path.exists():
            return path
    
    # 策略 3: 将多个空格替换为下划线
    # 例如: "Futuristic Bloom Iii  Lunar Garden" -> "Futuristic Bloom Iii_ Lunar Garden"
    variant1 = re.sub(r'\s{2,}', '_', description)
    for ext in extensions:
        path = library_root / f"{variant1}{ext}"
        if path.exists():
            return path
    
    # 策略 4-6: 使用 rglob 递归搜索（支持子目录）
    description_lower = description.lower()
    
    # 策略 4: 不区分大小写的直接匹配（递归）
    for ext in extensions:
        for song_file in library_root.rglob(f"*{ext}"):
            if song_file.is_file() and song_file.suffix.lower() == ext.lower():
                if song_file.stem.lower() == description_lower:
                    return song_file
    
    # 策略 5: 不区分大小写的模糊匹配（去除空格、下划线和引号差异后比较，递归）
    for ext in extensions:
        for song_file in library_root.rglob(f"*{ext}"):
            if song_file.is_file() and song_file.suffix.lower() == ext.lower():
                # 规范化：去除空格、下划线，统一引号字符（处理 U+2019 vs U+0027）
                song_normalized = re.sub(r'[_\s]+', '', song_file.stem.lower())
                song_normalized = song_normalized.replace('\u2019', "'").replace('\u2018', "'")  # 统一引号
                desc_normalized = re.sub(r'[_\s]+', '', description_lower)
                desc_normalized = desc_normalized.replace('\u2019', "'").replace('\u2018', "'")  # 统一引号
                if song_normalized == desc_normalized:
                    return song_file
    
    # 策略 6: 使用通配符搜索（最后的手段，递归）
    for ext in extensions:
        # 将 description 转换为搜索模式（处理空格和下划线）
        search_patterns = [
            variant2,    # 所有空格 -> 下划线（最可能匹配）
            description,  # 原样
            variant1,     # 多个空格 -> 下划线
        ]
        
        for pattern in search_patterns:
            # 使用不区分大小写的搜索
            for song_file in library_root.rglob(f"*{pattern}*{ext}"):
                if song_file.is_file() and song_file.suffix.lower() == ext.lower():
                    # 进一步验证：检查文件名是否真的匹配（去除大小写、空格/下划线和引号差异）
                    song_normalized = re.sub(r'[_\s]+', '', song_file.stem.lower())
                    song_normalized = song_normalized.replace('\u2019', "'").replace('\u2018', "'")  # 统一引号
                    desc_normalized = re.sub(r'[_\s]+', '', description_lower)
                    desc_normalized = desc_normalized.replace('\u2019', "'").replace('\u2018', "'")  # 统一引号
                    if desc_normalized in song_normalized or song_normalized in desc_normalized:
                        return song_file
    
    raise FileNotFoundError(f"Track not found: {description} in {library_root}")




def _generate_timeline_csv(
    events: list[dict],
    track_info: dict[str, dict],
    timeline_path: Path,
    episode_id: str,
) -> None:
    """
    生成时间轴 CSV 文件（基于 Timeline 事件和 Track 信息）
    
    这是混音和字幕对齐的权威时间轴，包含真实的 start_time、end_time 和 file_path。
    
    Args:
        events: Timeline 事件列表（包含 side, timestamp, description）
        track_info: 映射 {description: {"file_path": str, "duration_seconds": int}}
        timeline_path: 输出 CSV 文件路径
        episode_id: Episode ID（用于错误信息）
    
    Raises:
        ValueError: 如果 Timeline 事件中的曲目在 track_info 中找不到，说明 playlist.csv 数据不完整
    """
    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    
    with timeline_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["start_time", "end_time", "track_path", "track_title"])
        
        # 只记录曲目事件（排除 SFX）
        sfx_keywords = {"Needle On Vinyl Record", "Vinyl Noise", "Silence"}
        
        for event in events:
            desc = event.get("description", "").strip()
            if desc and desc not in sfx_keywords:
                timestamp = event.get("timestamp", "").strip()
                if not timestamp:
                    continue
                
                start_time = _parse_timestamp_to_ms(timestamp) / 1000.0
                
                # 从 track_info 获取真实的 duration_seconds 和 file_path
                if desc in track_info:
                    track_data = track_info[desc]
                    duration_seconds = track_data["duration_seconds"]
                    file_path = track_data["file_path"]
                    
                    # 结束时间 = 开始时间 + 完整 duration_seconds
                    # 与混音逻辑一致：每首曲目使用完整时长，只在最后2秒淡出
                    end_time = start_time + float(duration_seconds)
                else:
                    # 违反 Asset Contract：Timeline 中的曲目必须在 Track 部分有对应数据
                    # 不允许使用占位值，必须立即报错以暴露 playlist.csv 的数据缺陷
                    error_msg = (
                        f"Track info not found for '{desc}' in playlist.csv for episode {episode_id}. "
                        f"This indicates a data integrity issue: the Timeline section references a track "
                        f"that is missing from the Track section. Please check playlist.csv generation logic."
                    )
                    log_error(error_msg)
                    raise ValueError(error_msg)
                
                writer.writerow([
                    f"{start_time:.3f}",
                    f"{end_time:.3f}",
                    file_path,  # 真实的文件路径（来自 playlist.csv Track 行）
                    desc,       # 曲目标题
                ])


async def run_remix_for_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    """
    运行音频混音
    
    Interface Contract: async def run_remix_for_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult
    
    按照文档标准实现：
    - 只生成 final_mix.mp3（256 kbps CBR, 48 kHz, 16-bit）
    - 使用 FFmpeg filtergraph 处理 Timeline
    - 包含 SFX（Needle On Vinyl Record, Vinyl Noise）
    - 应用响度标准化（loudnorm: I=-14, TP=-1.5, LRA=11）
    
    时间轴语义（与 init.py 的 _calculate_needle_timeline_duration 一致）：
    - 每首曲目使用完整 duration_seconds（不再减2秒），只在最后2秒淡出
    - SFX 长度：
      * Needle On Vinyl Record: 源文件 7 秒，前 3 秒单独播放（时间轴上占 3 秒），后 4 秒与第一首歌混音播放，最后 0.5 秒淡出
      * Vinyl Noise: 7秒音频，但时间轴上只占3秒间隔
      * Silence: 3秒
    - Vinyl Noise 的7秒音频会重叠在前后曲目上，但时间轴只推进3秒（表示"间隔"）
    - Needle 的后 4 秒会与第一首歌混音播放（第一首歌从第 3 秒开始），音量不调整，最后 0.5 秒淡出
    - 使用 atrim 限制曲目播放长度，使用 afade 应用淡出效果
    - 确保实际 MP3 总长与 playlist.csv 的 TotalDuration 一致
    
    输出文件：
    - paths.final_mix_mp3 (<episode_id>_final_mix.mp3, MP3 格式, 256kbps, 48kHz)
    - paths.timeline_csv (<episode_id>_final_mix_timeline.csv) - 包含真实的 start_time、end_time、file_path（对应 final_mix_mp3）
    """
    started_at = datetime.now()
    
    try:
        # 幂等性检查：如果文件已存在，跳过生成
        if paths.final_mix_mp3.exists() and paths.timeline_csv.exists():
            log_info(f"Mix already complete for {spec.episode_id}, skipping")
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            
            return StageResult(
                stage=StageName.MIX,
                success=True,
                duration_seconds=duration,
                key_asset_paths=[
                    paths.final_mix_mp3,
                    paths.timeline_csv,
                ],
                started_at=started_at,
                finished_at=finished_at,
            )
        
        # 确保输出目录存在
        paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 解析 playlist.csv Timeline 部分和 Track 部分
        log_info(f"Parsing playlist.csv Timeline and Track sections from {paths.playlist_csv}")
        events, track_info = _parse_playlist_timeline(paths.playlist_csv)
        
        if not events:
            raise ValueError(f"No Timeline events found in playlist.csv for {spec.episode_id}")
        
        log_info(f"Found {len(events)} timeline events, {len(track_info)} track info entries")
        
        # 获取配置
        config = get_config()
        library_root = config.channels_root / spec.channel_id / "library" / "songs"
        sfx_dir = config.repo_root / "assets" / "sfx"
        
        # 检查 SFX 文件
        needle_start = sfx_dir / "Needle_Start.mp3"
        vinyl_noise = sfx_dir / "Vinyl_Noise.mp3"
        
        if not needle_start.exists():
            raise FileNotFoundError(f"SFX file not found: {needle_start}")
        if not vinyl_noise.exists():
            raise FileNotFoundError(f"SFX file not found: {vinyl_noise}")
        
        # 音频参数
        TRACK_SAMPLE_RATE = 48000  # McPOS 全局音频标准：48 kHz
        extensions = [".mp3", ".wav", ".flac", ".m4a", ".aac"]
        vinyl_noise_db = -18.0
        needle_gain_db = -18.0
        lufs = -14.0
        tp = -1.5
        
        # 构建 FFmpeg filtergraph
        input_paths: list[Path] = []
        filters: list[str] = []
        labels: list[str] = []
        filter_idx = 0
        
        MAX_DELAY_MS = 2 * 3600 * 1000  # 2 hours
        
        for event in events:
            desc = event.get("description", "").strip()
            timestamp = event.get("timestamp", "").strip()
            
            if not desc or not timestamp:
                continue
            
            delay_ms = _parse_timestamp_to_ms(timestamp)
            
            if delay_ms > MAX_DELAY_MS:
                log_warning(f"Skipping unreasonable delay: {delay_ms}ms for event: {desc}")
                continue
            
            is_sfx = False
            sfx_duration = None
            track_duration_seconds = None
            
            # 1) 先分类: Needle / Vinyl / Silence / 曲目
            if desc == "Needle On Vinyl Record":
                path = needle_start
                vol = 10 ** (needle_gain_db / 20.0)  # -18dB
                is_sfx = True
                sfx_duration = NEEDLE_TARGET_DURATION
            elif desc == "Vinyl Noise":
                path = vinyl_noise
                vol = 10 ** (vinyl_noise_db / 20.0)  # -18dB
                is_sfx = True
                sfx_duration = VINYL_TARGET_DURATION
            elif desc == "Silence":
                # 静音 3 秒，直接用 anullsrc，不需要文件输入
                lbl = f"a{filter_idx}"
                filters.append(
                    f"anullsrc=r={TRACK_SAMPLE_RATE}:cl=stereo,"
                    f"atrim=0:{SILENCE_DURATION},"
                    f"adelay={delay_ms}|{delay_ms}[{lbl}]"
                )
                labels.append(lbl)
                filter_idx += 1
                continue
            else:
                # 曲目文件
                try:
                    path = _resolve_track_path(desc, library_root, extensions)
                except FileNotFoundError as e:
                    log_warning(f"Track not found: {desc}, skipping: {e}")
                    continue
                vol = 1.0
                
                # 从 track_info 获取曲目的真实时长
                if desc in track_info:
                    track_duration_seconds = track_info[desc]["duration_seconds"]
                else:
                    log_warning(f"Track duration not found in playlist.csv for: {desc}, using full file length")
            
            if not path.exists():
                log_warning(f"Audio file not found: {path}, skipping")
                continue
            
            input_paths.append(path)
            audio_input_idx = len(input_paths) - 1
            lbl = f"a{filter_idx}"
            
            # 2) 构建 filter: SFX 和曲目分别处理
            if is_sfx:
                # SFX 分支：源文件 7 秒，按目标时长裁剪并加淡入淡出
                if desc == "Needle On Vinyl Record":
                    # Needle: 播放源文件完整长度（约 7.18 秒），然后淡出
                    # - 前 3 秒单独播放（时间轴上占 3 秒）
                    # - 后 4 秒（3-7秒）与第一首歌混音播放，音量不调整
                    # - 最后 0.5 秒（6.5-7秒）淡出
                    # 注意：不使用 atrim，直接播放源文件完整长度（参考旧世界实现）
                    # 这样可以避免 amix duration=longest 计算错误导致的截断问题
                    fade_out_start = max(0.0, NEEDLE_FULL_DURATION - NEEDLE_FADE_OUT)  # 6.5 秒处开始淡出
                    filters.append(
                        f"[{audio_input_idx}:a]"
                        f"aformat=sample_fmts=fltp:sample_rates={TRACK_SAMPLE_RATE}:channel_layouts=stereo,"
                        f"volume={vol},"
                        f"afade=t=out:st={fade_out_start}:d={NEEDLE_FADE_OUT},"
                        f"adelay={delay_ms}|{delay_ms}[{lbl}]"
                    )
                elif desc == "Vinyl Noise":
                    # Vinyl: 总长 7 秒。前 2 秒渐入，中间 3 秒 plateau，最后 2 秒渐出
                    dur = VINYL_TARGET_DURATION  # 7.0
                    fade_in_start = 0.0
                    fade_in_d = min(SFX_FADE_IN, dur / 3.0)   # 2.0
                    fade_out_start = max(0.0, dur - SFX_FADE_OUT)  # 5.0
                    fade_out_d = SFX_FADE_OUT                  # 2.0
                    filters.append(
                        f"[{audio_input_idx}:a]"
                        f"aformat=sample_fmts=fltp:sample_rates={TRACK_SAMPLE_RATE}:channel_layouts=stereo,"
                        f"volume={vol},"
                        f"atrim=0:{dur},"
                        f"afade=t=in:st={fade_in_start}:d={fade_in_d},"
                        f"afade=t=out:st={fade_out_start}:d={fade_out_d},"
                        f"adelay={delay_ms}|{delay_ms}[{lbl}]"
                    )
                else:
                    # 理论上不会到这里，防御性兜底
                    filters.append(
                        f"[{audio_input_idx}:a]"
                        f"aformat=sample_fmts=fltp:sample_rates={TRACK_SAMPLE_RATE}:channel_layouts=stereo,"
                        f"volume={vol},"
                        f"adelay={delay_ms}|{delay_ms}[{lbl}]"
                    )
            else:
                # 曲目分支：使用完整时长，最后 2 秒淡出（不再减2秒）
                if track_duration_seconds is not None:
                    trim_duration = float(track_duration_seconds)  # 完整时长，不减2
                    fade_start = max(0.0, trim_duration - 2.0)  # 在最后2秒淡出
                    filters.append(
                        f"[{audio_input_idx}:a]"
                        f"aformat=sample_fmts=fltp:sample_rates={TRACK_SAMPLE_RATE}:channel_layouts=stereo,"
                        f"volume={vol},"
                        f"atrim=0:{trim_duration},"
                        f"afade=t=out:st={fade_start}:d=2,"
                        f"adelay={delay_ms}|{delay_ms}[{lbl}]"
                    )
                else:
                    # 极端兜底：没拿到 DurationSeconds 的曲目，不裁剪，只延时叠加
                    filters.append(
                        f"[{audio_input_idx}:a]"
                        f"aformat=sample_fmts=fltp:sample_rates={TRACK_SAMPLE_RATE}:channel_layouts=stereo,"
                        f"volume={vol},"
                        f"adelay={delay_ms}|{delay_ms}[{lbl}]"
                    )
            
            labels.append(lbl)
            filter_idx += 1
        
        if not labels or not filters:
            raise ValueError("No valid audio events found in timeline")
        
        log_info(f"Built filtergraph: {len(labels)} filters, {len(input_paths)} audio inputs")
        
        # 构建 amix filter（混音叠加 + 响度标准化）
        label_concat = "".join(f"[{l}]" for l in labels)
        if len(labels) > 1:
            post = f"{label_concat}amix=inputs={len(labels)}:normalize=0:duration=longest,loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=summary[mix]"
        else:
            post = f"[{labels[0]}]loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=summary[mix]"
        
        filter_complex = filters + [post]
        
        # 生成 final_mix.mp3（MP3 格式, 256 kbps CBR, 48 kHz）
        # McPOS 全局音频标准：256 kbps CBR, 48 kHz
        log_info(f"Generating final_mix.mp3 (MP3, 256kbps CBR, 48kHz) to {paths.final_mix_mp3}")
        
        # 构建 filtergraph 字符串
        filtergraph_str = ";".join(filter_complex)
        
        # 调用边界函数进行混音（所有 ffmpeg 命令细节都在 mix_engine 中）
        # mix_engine 会根据输出文件扩展名（.mp3）自动使用 libmp3lame 编码
        config = get_config()
        mix_result = await mix_episode_audio(
            spec=spec,
            paths=paths,
            cfg=config,
            filtergraph=filtergraph_str,
            input_paths=input_paths,
            output_path=paths.final_mix_mp3,
        )
        
        log_info(f"Mix complete: {mix_result.size_bytes} bytes")
        
        # 生成时间轴 CSV（使用真实的 track_info）
        log_info(f"Generating timeline.csv to {paths.timeline_csv}")
        _generate_timeline_csv(events, track_info, paths.timeline_csv, spec.episode_id)
        
        # 验证文件是否存在
        if not paths.final_mix_mp3.exists():
            raise FileNotFoundError(f"final_mix.mp3 not found at {paths.final_mix_mp3}")
        if not paths.timeline_csv.exists():
            raise FileNotFoundError(f"timeline.csv not found at {paths.timeline_csv}")
        
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        log_info(f"✅ Mix complete for {spec.episode_id}: "
                f"final_mix={paths.final_mix_mp3.exists()}, "
                f"timeline={paths.timeline_csv.exists()}")
        
        return StageResult(
            stage=StageName.MIX,
            success=True,
            duration_seconds=duration,
            key_asset_paths=[
                paths.final_mix_mp3,
                paths.timeline_csv,
            ],
            started_at=started_at,
            finished_at=finished_at,
        )
        
    except Exception as e:
        import traceback
        log_error(f"run_remix_for_episode exception for {spec.episode_id}: {e}\n{traceback.format_exc()}")
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        return StageResult(
            stage=StageName.MIX,
            success=False,
            duration_seconds=duration,
            key_asset_paths=[],
            error_message=str(e),
            started_at=started_at,
            finished_at=finished_at,
        )


