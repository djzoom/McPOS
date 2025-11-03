#!/usr/bin/env python3
# coding: utf-8
"""
生成 YouTube 相关资源：
1. SRT 字幕文件（曲目时间轴 + 介绍）
2. YouTube 标题（SEO优化）
3. YouTube 描述

用法：
    python scripts/local_picker/generate_youtube_assets.py \
        --playlist output/playlists/20251029_0526_mixtape_playlist.csv \
        --title "Midnight Dreams" \
        --output output/youtube
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Dict, List, Optional
import json

# Optional dependencies for API calls
try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None


def parse_timestamp(ts: str) -> tuple[int, int, int, int]:
    """解析时间戳 "2:39" 或 "1:23:45" -> (hours, minutes, seconds, milliseconds)"""
    if not ts or ":" not in ts:
        return (0, 0, 0, 0)
    parts = ts.strip().split(":")
    if len(parts) == 2:
        m, s = parts
        return (0, int(m), int(s), 0)
    elif len(parts) == 3:
        h, m, s = parts
        return (int(h), int(m), int(s), 0)
    return (0, 0, 0, 0)


def format_srt_time(hours: int, minutes: int, seconds: int, milliseconds: int) -> str:
    """格式化为 SRT 时间格式：HH:MM:SS,mmm"""
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_playlist(csv_path: Path) -> Dict:
    """解析歌单 CSV，提取元信息和曲目列表"""
    metadata = {}
    tracks_a: List[Dict] = []
    tracks_b: List[Dict] = []
    timeline: List[Dict] = []  # Needle timeline (保留兼容性)
    clean_timeline: List[Dict] = []  # Clean timeline (无唱针噪音)
    
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            section = (row.get("Section") or "").strip()
            field = (row.get("Field") or "").strip()
            value = (row.get("Value") or "").strip()
            
            if section == "Metadata":
                metadata[field] = value
            elif section == "Track":
                side = (row.get("Side") or "").strip()
                track = {
                    "side": side,
                    "order": row.get("Order", "").strip(),
                    "title": row.get("Title", "").strip(),
                    "duration": row.get("Duration", "").strip(),
                    "duration_seconds": row.get("DurationSeconds", "").strip(),
                }
                if side == "A":
                    tracks_a.append(track)
                elif side == "B":
                    tracks_b.append(track)
            elif section == "Timeline":
                timeline_type = (row.get("Timeline") or "").strip()
                event_data = {
                    "side": (row.get("Side") or "").strip(),
                    "timestamp": (row.get("Timestamp") or "").strip(),
                    "description": (row.get("Description") or "").strip(),
                }
                if timeline_type == "Needle":
                    timeline.append(event_data)
                elif timeline_type == "Clean":
                    clean_timeline.append(event_data)
    
    return {
        "metadata": metadata,
        "tracks_a": tracks_a,
        "tracks_b": tracks_b,
        "timeline": timeline,  # 保留兼容性
        "clean_timeline": clean_timeline,  # 新增
    }


def generate_welcoming_messages(
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> tuple[str, str]:
    """使用 API 生成欢迎和致谢消息（Kat Records 品牌风格）"""
    intro_default = "Welcome to Kat Records. A new vinyl LP pressed in silence, played in your world."
    outro_default = "Thank you for listening. Kat Records is where emotion meets algorithm. Subscribe for the next LP release."
    
    if not OpenAI or not api_key:
        return intro_default, outro_default
    
    try:
        client = OpenAI(api_key=api_key, base_url=api_base)
        # 一次性生成欢迎和致谢，节省 token
        prompt = """You are a music label narrative strategist for Kat Records.

Generate two short messages for a vinyl LP release:

1. Welcome message (max 100 chars): Welcoming listeners at the start, mention Kat Records, use vinyl/LP language, poetic tone.
2. Thank you message (max 120 chars): Thanking listeners at the end, mention subscribing for next LP release, keep it refined and brand-aligned.

Format as two lines, line 1 = welcome, line 2 = thank you. No emojis. English only.
Tone: Literary, refined, with vinyl collection feel. Avoid "playlist" — use "LP / Vinyl / Session"."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a music label narrative strategist for Kat Records. You write refined, literary content with vinyl collection feel."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        content = response.choices[0].message.content.strip()
        if content:
            parts = content.split("\n", 1)
            if len(parts) == 2:
                intro = parts[0].strip().strip('"').strip("'")
                outro = parts[1].strip().strip('"').strip("'")
                if intro and outro:
                    return intro, outro
    except Exception as e:
        print(f"[WARN] 欢迎/致谢消息生成失败: {e}，使用默认消息")
    
    return intro_default, outro_default


def generate_srt(
    playlist_data: Dict,
    output_path: Path,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> None:
    """生成 SRT 字幕文件"""
    tracks_a = playlist_data["tracks_a"]
    tracks_b = playlist_data["tracks_b"]
    # 优先使用 clean_timeline，如果没有则回退到过滤后的 timeline
    clean_timeline = playlist_data.get("clean_timeline", [])
    if clean_timeline:
        track_events = clean_timeline
    else:
        timeline = playlist_data.get("timeline", [])
        # 过滤出曲目（排除 Needle On Vinyl Record 和 Vinyl Noise）
        track_events = [
            ev for ev in timeline
            if ev.get("description", "") not in ("Needle On Vinyl Record", "Vinyl Noise", "Silence")
        ]
    
    lines = []
    subtitle_num = 1
    
    # 生成欢迎消息（使用 API 但精简）
    intro_msg, outro_msg = generate_welcoming_messages(api_key, api_base)
    
    # 开场欢迎词
    intro_start = (0, 0, 0, 0)
    intro_end = (0, 0, 5, 0)
    lines.append(f"{subtitle_num}\n")
    lines.append(f"{format_srt_time(*intro_start)} --> {format_srt_time(*intro_end)}\n")
    lines.append(f"{intro_msg}\n")
    lines.append("\n")
    subtitle_num += 1
    
    # 曲目时间轴
    current_time = intro_end
    for i, event in enumerate(track_events):
        # 开始时间
        h, m, s, ms = parse_timestamp(event["timestamp"])
        start_time = (h, m, s, ms)
        
        # 计算结束时间（下一曲目开始，或当前曲目结束）
        if i + 1 < len(track_events):
            next_h, next_m, next_s, next_ms = parse_timestamp(track_events[i + 1]["timestamp"])
            end_time = (next_h, next_m, next_s, next_ms)
        else:
            # 最后一个曲目，持续时间3秒
            end_seconds = s + 3
            end_minutes = m + (end_seconds // 60)
            end_seconds = end_seconds % 60
            end_hours = h + (end_minutes // 60)
            end_minutes = end_minutes % 60
            end_time = (end_hours, end_minutes, end_seconds, 0)
        
        # 生成曲目介绍
        track_title = event["description"]
        track_num = i + 1
        
        # 判断是 Side A 还是 Side B
        side = "A"
        if i >= len(tracks_a):
            side = "B"
            track_num = i - len(tracks_a) + 1
        
        lines.append(f"{subtitle_num}\n")
        lines.append(f"{format_srt_time(*start_time)} --> {format_srt_time(*end_time)}\n")
        lines.append(f"Track {track_num} (Side {side}): {track_title}\n")
        lines.append("\n")
        subtitle_num += 1
    
    # 结束语（在最后一个曲目结束后）
    if track_events:
        # 计算最后一个曲目的结束时间
        last_h, last_m, last_s, last_ms = parse_timestamp(track_events[-1]["timestamp"])
        # 最后曲目结束后1秒开始，持续5秒
        outro_start_s = last_s + 6
        outro_start_m = last_m + (outro_start_s // 60)
        outro_start_s = outro_start_s % 60
        outro_start_h = last_h + (outro_start_m // 60)
        outro_start_m = outro_start_m % 60
        outro_start = (outro_start_h, outro_start_m, outro_start_s, 0)
        
        outro_end_s = outro_start_s + 5
        outro_end_m = outro_start_m + (outro_end_s // 60)
        outro_end_s = outro_end_s % 60
        outro_end_h = outro_start_h + (outro_end_m // 60)
        outro_end_m = outro_end_m % 60
        outro_end = (outro_end_h, outro_end_m, outro_end_s, 0)
    else:
        outro_start = (0, 5, 0, 0)
        outro_end = (0, 10, 0, 0)
    
    lines.append(f"{subtitle_num}\n")
    lines.append(f"{format_srt_time(*outro_start)} --> {format_srt_time(*outro_end)}\n")
    lines.append(f"{outro_msg}\n")
    
    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        fh.writelines(lines)


def format_clean_timeline(clean_timeline: List[Dict]) -> str:
    """格式化 clean timeline 为文本时间轴"""
    if not clean_timeline:
        return ""
    
    lines = ["\nTrack Timeline:\n"]
    for event in clean_timeline:
        timestamp = event.get("timestamp", "")
        description = event.get("description", "")
        side = event.get("side", "")
        if timestamp and description:
            lines.append(f"{timestamp} - {description} (Side {side})\n")
    return "".join(lines)


def generate_youtube_title_desc(
    original_title: str,
    playlist_data: Dict,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> tuple[str, str]:
    """使用 API 生成 YouTube 标题和描述（Kat Records × Vibe Coding 品牌风格）"""
    tracks_a = playlist_data["tracks_a"]
    tracks_b = playlist_data["tracks_b"]
    clean_timeline = playlist_data.get("clean_timeline", [])
    
    # 准备曲目列表
    track_list = "\n".join([f"- {t['title']}" for t in tracks_a + tracks_b])
    total_tracks = len(tracks_a) + len(tracks_b)
    
    # Kat Records × Vibe Coding 品牌策略 Prompt
    prompt_title = f"""You are a music label narrative strategist for Kat Records and its creative system Vibe Coding.

Generate a vinyl release-style YouTube video title for this album:

Album Title: "{original_title}"
Total Tracks: {total_tracks}
Side A: {len(tracks_a)} tracks
Side B: {len(tracks_b)} tracks

**Brand Context:**
- Kat Records: A virtual vinyl label that records sounds of emotions and moments. Each LP is a story of nighttime.
- Vibe Coding: A creative philosophy of the AI era — sculpting emotions with algorithms, encoding souls with rhythm.

**Title Format:**
`[Album Name LP] | Kat Records Presents [Subtitle / Mood Phrase]`

**Requirements:**
1. Start with "{original_title} LP" or "{original_title} Vinyl" (use poetic imagery like Memory/Parade/Lines/Café/Dream)
2. Follow with "| Kat Records Presents" 
3. Add a mood phrase or subtitle that captures the album's atmosphere (night/city/quiet/dream/coded emotions)
4. Maximum 90 characters
5. Tone: Literary, refined, with vinyl collection feel
6. Avoid "playlist" — use "LP / Vinyl / Session / Collection" instead
7. Optionally end with (lofi edition / ambient cut / night take) in parentheses
8. English only

**Examples:**
- "Neon Memory LP | Kat Records Presents City Echoes at Midnight"
- "Rainlight Café LP | Kat Records Presents Soft Jazz for Quiet Days"
- "Parallel Lines LP | Kat Records Presents Soundtracks for the Unfinished Stories"

Return ONLY the title, no quotes or extra text."""

    # 格式化曲目列表用于时间轴（使用 clean_timeline 或 tracks）
    tracklist_text = ""
    all_tracks = tracks_a + tracks_b
    
    if clean_timeline and len(clean_timeline) >= len(all_tracks):
        # 如果有时间轴，使用时间轴生成曲目列表
        for i, track in enumerate(all_tracks):
            if i < len(clean_timeline):
                event = clean_timeline[i]
                timestamp = event.get("timestamp", "")
                if timestamp:
                    # 解析时间戳 (格式: HH:MM:SS)
                    parts = timestamp.split(":")
                    if len(parts) == 3:
                        try:
                            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                            minutes = h * 60 + m  # 转换为总分钟数
                            seconds = s
                        except ValueError:
                            # 如果解析失败，使用估算时间
                            track_duration = int(track.get('duration_seconds', 180) or 180)
                            minutes = (i * track_duration) // 60
                            seconds = (i * track_duration) % 60
                    else:
                        track_duration = int(track.get('duration_seconds', 180) or 180)
                        minutes = (i * track_duration) // 60
                        seconds = (i * track_duration) % 60
                else:
                    track_duration = int(track.get('duration_seconds', 180) or 180)
                    minutes = (i * track_duration) // 60
                    seconds = (i * track_duration) % 60
            else:
                # 超出时间轴范围，使用估算时间
                track_duration = int(track.get('duration_seconds', 180) or 180)
                minutes = (i * track_duration) // 60
                seconds = (i * track_duration) % 60
            
            # 添加 Side 标识
            side_label = ""
            if i == 0:
                side_label = f"Side A: "
            elif i == len(tracks_a):
                side_label = f"Side B: "
            
            tracklist_text += f"{minutes:02d}:{seconds:02d}  —  **{side_label}{track['title']}**\n"
    else:
        # 没有时间轴，按顺序生成（估算时间）
        current_time_sec = 0
        for i, track in enumerate(all_tracks):
            minutes = current_time_sec // 60
            seconds = current_time_sec % 60
            
            # 添加 Side 标识
            side_label = ""
            if i == 0:
                side_label = f"Side A: "
            elif i == len(tracks_a):
                side_label = f"Side B: "
            
            tracklist_text += f"{minutes:02d}:{seconds:02d}  —  **{side_label}{track['title']}**\n"
            track_duration = int(track.get('duration_seconds', 180) or 180)
            current_time_sec += track_duration

    prompt_desc = f"""You are a music label copywriter director for Kat Records, creating description copy for virtual vinyl LP releases.

**Style Requirements:** Elegant, warm, cool, soulful — like inner sleeve text from a midnight LP release. Read like a story, optimized for YouTube SEO and viewing rhythm.

**Album Information:**
- Album Title: "{original_title}"
- Total Tracks: {total_tracks} ({len(tracks_a)} on Side A, {len(tracks_b)} on Side B)
- Track List:
{track_list}

**Output Structure — Generate a complete YouTube description with:**

**1. Opening Paragraph (Label Voice):**
- MUST start with: "A new vinyl chapter from Kat Records."
- Include: "Where analog warmth meets digital calm — every note gently coded in emotion."
- Add: "This is Vibe Coding: music written between rhythm and silence."
- 3-4 sentences total, elegant and warm.

**3. Mood Description (Instruments, Imagery, Feelings):**
- Describe sound palette: piano, drums, bass, ambient textures, etc.
- Use poetic imagery: "Piano glows like candlelight.", "Drums breathe slow, wrapped in rain."
- Create atmosphere with 3-5 poetic sentences.
- End with: "Perfect for: vibe coding, night study, cozy coffee breaks, deep focus, journaling, slow mornings."

**4. Tracklist / Timecode Section:**
Format:
```
🕰️ Tracklist / Timecode  

00:00  —  **Side A: [Opening Track Title]**
[Continue with provided timestamps...]
[Side B tracks...]
```

Use this tracklist (with timestamps):
{tracklist_text}

**5. Closing Paragraph (Philosophical Sentence or Listening Advice):**
- Tone: calm but warm, like:
  "🎧 Press play and let this LP fill the room, not your mind."
  "Some records are meant to be heard; this one is meant to keep you company."
- Include: "Each Kat Rec release is a quiet experiment in Vibe Coding — crafted not for fame, but for resonance."
- 2-3 sentences, philosophical but accessible.

**6. Hashtag Section:**
Include these core tags:
#KatRecords #VibeCoding #vinylsession #jazzambient #nightmusic #cityrain #chillinstrumental #sounddiary #creativefocus #analogdreams #sleepmusic #studybeats #lofisoul #nightdrive #cozyvibes

Add 3-5 additional tags based on album theme/mood.

**Writing Guidelines:**
- Language: English only
- Tone: Combine Lofi Girl (episodic tracklist), Chill Chill Journal (rhythmic philosophy), Noir Jazz Cats (jazz narrative), Otterspace Lofi (gentle companionship)
- Voice: Quiet, scented, rhythmic, with a worldview
- Maximum 600 words (excluding tracklist and hashtags)
- Avoid: "playlist", "mix", "background music" — use "LP", "Vinyl", "Session", "Edition"
- Make it read like real vinyl inner sleeve text

Generate the complete description following this exact structure."""

    # 默认标题（Kat Records 风格）
    title = f"{original_title} LP | Kat Records Presents Night Session"
    
    # 生成默认描述（带时间轴）
    default_tracklist = ""
    current_time_sec = 0
    all_tracks_default = tracks_a + tracks_b
    for i, track in enumerate(all_tracks_default):
        minutes = current_time_sec // 60
        seconds = current_time_sec % 60
        
        # 添加 Side 标识
        side_label = ""
        if i == 0:
            side_label = f"Side A: "
        elif i == len(tracks_a):
            side_label = f"Side B: "
        
        default_tracklist += f"{minutes:02d}:{seconds:02d}  —  **{side_label}{track['title']}**\n"
        track_duration = int(track.get('duration_seconds', 180) or 180)
        current_time_sec += track_duration
    
    description = f"""{original_title} | Kat Records × Vibe Coding Presents Night Session

---------------------------------------------------------

A new vinyl chapter from Kat Records.
Where analog warmth meets digital calm — every note gently coded in emotion.
This is Vibe Coding: music written between rhythm and silence.

Piano glows like candlelight.
Drums breathe slow, wrapped in rain.
Bass walks softly through empty streets.
Each track spins like a quiet conversation between time and tenderness.

Perfect for: night study, cozy coffee breaks, deep focus, journaling, slow mornings.

---------------------------------------------------------

🕰️ Tracklist / Timecode

{default_tracklist}
---------------------------------------------------------

🎧 Press play and let this LP fill the room, not your mind.
Some records are meant to be heard; this one is meant to keep you company.
Each Kat Rec release is a quiet experiment in Vibe Coding — crafted not for fame, but for resonance.

#KatRecords #VibeCoding #vinylsession #jazzambient #nightmusic #cityrain #chillinstrumental #sounddiary #creativefocus #analogdreams #sleepmusic #studybeats #lofisoul #nightdrive #cozyvibes"""
    
    if not OpenAI:
        print("[WARN] OpenAI 库未安装，使用默认标题和描述。请运行: pip install openai")
    elif not api_key:
        print("[WARN] OPENAI_API_KEY 未设置，使用默认标题和描述。")
    else:
        try:
            print("[API] 正在调用 OpenAI API 生成 YouTube 标题和描述（Kat Records × Vibe Coding 风格）...")
            client = OpenAI(api_key=api_key, base_url=api_base)
            
            # 生成标题
            print("[API] 生成 YouTube 标题...")
            response_title = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a music label narrative strategist for Kat Records. You create vinyl release-style titles that combine poetic imagery with brand identity. Tone: literary, refined, with vinyl collection feel."},
                    {"role": "user", "content": prompt_title}
                ],
                max_tokens=120,
                temperature=0.7,
            )
            generated_title = response_title.choices[0].message.content.strip().strip('"').strip("'")
            if generated_title:
                title = generated_title
                print(f"[API] ✅ YouTube 标题生成成功: {title}")
            else:
                print("[WARN] API 返回空标题，使用默认标题")
            
            # 生成描述
            print("[API] 生成 YouTube 描述...")
            response_desc = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a music label copywriter director for Kat Records. You create elegant, warm, cool, soulful description copy for virtual vinyl LP releases. Style: like inner sleeve text from a midnight LP release, combining Lofi Girl's episodic tracklist, Chill Chill Journal's rhythmic philosophy, Noir Jazz Cats' jazz narrative, and Otterspace Lofi's gentle companionship. Tone: quiet, scented, rhythmic, with a worldview."},
                    {"role": "user", "content": prompt_desc}
                ],
                max_tokens=1200,
                temperature=0.7,
            )
            generated_desc = response_desc.choices[0].message.content.strip()
            if generated_desc:
                description = generated_desc
                print(f"[API] ✅ YouTube 描述生成成功（{len(description)} 字符）")
            else:
                print("[WARN] API 返回空描述，使用默认描述")
            
        except Exception as e:
            print(f"[WARN] OpenAI API 调用失败: {e}，使用默认值")
    
    # 注意：不再添加单独的 timeline_text，因为新格式的描述已经包含了完整的时间轴
    
    return title, description


def main():
    parser = argparse.ArgumentParser(description="生成 YouTube 资源（SRT、标题、描述）")
    parser.add_argument("--playlist", type=Path, required=True, help="歌单 CSV 路径")
    parser.add_argument("--title", type=str, required=True, help="专辑标题")
    parser.add_argument("--output", type=Path, required=True, help="输出目录（应输出到每期文件夹）")
    parser.add_argument("--openai-api-key", type=str, help="OpenAI API Key")
    parser.add_argument("--openai-base-url", type=str, help="OpenAI API Base URL（可选）")
    
    args = parser.parse_args()
    
    # 获取 API 配置
    api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY")
    api_base = args.openai_base_url or os.getenv("OPENAI_BASE_URL")
    
    # 解析歌单
    print(f"[解析] 读取歌单：{args.playlist}")
    playlist_data = parse_playlist(args.playlist)
    
    # 生成 SRT
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 使用 playlist stem 作为基础名称
    playlist_stem = args.playlist.stem.replace("_playlist", "")
    video_base_name = f"{playlist_stem}_youtube"
    srt_path = output_dir / f"{video_base_name}.srt"
    
    print(f"[生成] SRT 字幕：{srt_path}")
    generate_srt(playlist_data, srt_path, api_key=api_key, api_base=api_base)
    
    # 生成 YouTube 标题和描述
    
    print(f"[生成] YouTube 标题和描述...")
    title, description = generate_youtube_title_desc(
        args.title,
        playlist_data,
        api_key=api_key,
        api_base=api_base,
    )
    
    # 保存标题和描述（使用与SRT相同的基础名称）
    title_path = output_dir / f"{video_base_name}_title.txt"
    desc_path = output_dir / f"{video_base_name}_description.txt"
    
    title_path.write_text(title, encoding="utf-8")
    desc_path.write_text(description, encoding="utf-8")
    
    print(f"[完成] 标题：{title_path}")
    print(f"[完成] 描述：{desc_path}")
    print(f"[完成] SRT：{srt_path}")


if __name__ == "__main__":
    main()

