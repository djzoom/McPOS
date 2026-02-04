"""
McPOS 多频道歌库批量重命名工具

功能：
- 支持多频道（RBR、Kat等）
- 自动检测并修复问题标题
- 使用API生成富有创意的标题
- 确保标题唯一性
- 支持频道特定配置

遵循McPOS原则：
- 自包含：所有逻辑在mcpos/下
- 边界模块：通过adapter暴露接口
- 文件系统作为真相来源
"""

from __future__ import annotations

import csv
import json
import os
import random
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# 默认配置（可作为其他频道的模板）
DEFAULT_CONFIG = {
    "title_templates": [
        "Awaken the Champion", "Awaken the Journey", "Awaken the Thunder",
        "Awakening the Brave Heart", "Awakening the Journey",
        "Beyond Every Finish Line", "Beyond the Fading Light",
        "Boundless Journey Ahead", "Boundless Spirit",
        "Chasing New Horizons", "Chasing Radiant Dreams", "Chasing the Sunlight",
        "Chasing the Sunrise", "Conquer Every Distance", "Conquer the Open Road",
        "Elevate Your Journey", "Elevate Your Spirit",
        "Embrace the Journey", "Energize the Journey",
        "Find Your Rhythm", "Forging Ahead Together",
        "Fuel the Fire Within", "Fuel the Flame Within",
        "Ignite the Dawn", "Ignite the Journey", "Ignite Your Journey",
        "Ignite Your Momentum", "Ignite Your Passion", "Ignite Your Spirit",
        "Limitless Ambitions", "Limitless Horizons Await",
        "Pushing Past the Limits", "Pursue the Light",
        "Soar Beyond the Limit", "Soar Beyond Limits",
        "Soaring Above the Clouds", "Soaring Towards Tomorrow",
        "Soaring through the Stars", "Stride into the Dawn",
        "Stride into the Light", "Stride into Tomorrow",
        "Unstoppable in Motion", "Unstoppable Momentum",
        "Wings Beneath My Feet", "Wings of Determination",
    ],
    "artist_pool": [
        "Neon Echo", "Digital Flow", "Urban Pulse", "Crystal Waves", "Quantum Rhythm",
        "Synthetic Beats", "Nexus Lab", "Apex Studio", "Vertex Works", "Prism Tones",
        "Spectrum Zone", "Phantom Space", "Lunar Collective", "Solar Project", "Cosmic Unit",
        "Nova System", "Echo Circuit", "Arctic Flow", "Aurora Beats", "Blaze Waves",
        "Crimson Rhythm", "Dusk Sound", "Eclipse Lab", "Flux Studio", "Glow Works",
        "Haze Tones", "Iris Zone", "Jade Space", "Kaleid Realm", "Lux Collective",
        "Mirage Project", "Nebula Unit", "Onyx System", "Phoenix Network", "Quartz Circuit",
        "Radiant Field", "Stellar Grid", "Titan Vault", "Ultra Harbor", "Vapor Haven",
        "Luna Star", "Aria Moon", "Sage Willow", "Ivy Rose", "Zoe Sky",
        "Maya Dawn", "Eva Light", "Lily Bloom", "Ruby Fire", "Sage River",
    ],
    "special_artists": ["0xGarfield", "John Garfield"],
    "remix_djs": ["DJzoom", "DJWZ"],
    "version_suffixes": [
        "(Radio Edition)", "(Remix)", "(Extended Mix)", "(Club Mix)", 
        "(Original Mix)", "(Radio Edit)"
    ],
    "collab_artists": [
        "DJ Crystal", "DJ Spark", "DJ Pulse", "DJ Wave", "DJ Echo",
        "DJ Flow", "DJ Beat", "DJ Rhythm", "DJ Sound", "DJ Vibe",
        "DJ Luna", "DJ Aria", "DJ Sage", "DJ Ivy", "DJ Zoe",
    ],
    "forbidden_words": ["karma", "zen", "shadow", "void", "dark"],
    "max_artist_songs": 3,
    "max_special_artist_songs": 5,
    "use_api_for_problems": True,
}

def load_channel_config(channel_id: str, channels_root: Path) -> Dict:
    """加载频道配置，如果不存在则使用默认配置"""
    config_path = channels_root / channel_id / "config" / "library_rename.json"
    
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                channel_config = json.load(f)
            # 合并默认配置
            config = DEFAULT_CONFIG.copy()
            config.update(channel_config)
            return config
        except Exception:
            pass
    
    # 返回默认配置
    return DEFAULT_CONFIG.copy()

def get_audio_duration_seconds(file_path: Path) -> Optional[float]:
    """获取音频文件时长（秒）"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return None

def extract_base_title(filename: str) -> str:
    """从文件名提取基础标题"""
    stem = Path(filename).stem
    stem = re.sub(r"__\d+$", "", stem)  # 去掉 __0001
    stem = re.sub(r"\(\d+\)", "", stem)  # 去掉 (1)
    stem = re.sub(r"\[[^\]]*\]", "", stem)  # 去掉 [...]
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem

def is_uuid_format(text: str) -> bool:
    """检测是否为UUID格式（xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx）"""
    # UUID 格式：8-4-4-4-12 个十六进制字符
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    # 也检测清理后的 UUID（去掉了连字符）
    uuid_no_dash_pattern = r'^[0-9a-f]{32}$'
    text_lower = text.lower().replace(' ', '').replace('-', '')
    return bool(re.match(uuid_pattern, text.lower()) or re.match(uuid_no_dash_pattern, text_lower))

def clean_title(title: str) -> str:
    """清理标题"""
    title = re.sub(r"[^A-Za-z0-9\s'\-]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    # 修复没有空格的问题（如 RunBaby -> Run Baby）
    title = re.sub(r'([a-z])([A-Z])', r'\1 \2', title)
    if title:
        title = title[0].upper() + title[1:]
    return title

def clean_title_from_modifiers(title: str) -> str:
    """清理标题中的修饰词"""
    modifiers = ["Eternal", "Ultimate", "Final", "Prime", "Elite", "Supreme", "Absolute", 
                "Classic", "Premium", "Deluxe", "Special", "Extended", "Remastered",
                "New", "Fresh", "Next"]
    words = title.split()
    while words and words[-1] in modifiers:
        words.pop()
    return " ".join(words) if words else title

def is_problematic_title(title: str, config: Dict) -> bool:
    """检测问题标题"""
    title_lower = title.lower()
    
    # UUID 格式（优先检测）
    if is_uuid_format(title):
        return True
    
    # Run Baby Run 相关（RBR特定）
    if "run baby run" in title_lower or "run, run" in title_lower:
        return True
    
    # 长描述
    if any(phrase in title_lower for phrase in [
        "helps runners", "stay motivated", "feel empowered",
        "motivational high energy", "track for runn"
    ]):
        return True
    
    # 太长
    if len(title) > 60 or len(title.split()) > 10:
        return True
    
    # "New New" 重复
    if "New New" in title:
        return True
    
    # 数字重复
    if re.search(r'\b(\d+)\s+\1\b', title):
        return True
    
    # 以数字结尾
    if re.search(r'\s+\d+$', title):
        return True
    
    # 没有空格（如 RunBaby）
    if re.search(r'[a-z][A-Z]', title):
        return True
    
    return False

def generate_title_api(
    client: OpenAI,
    model: str,
    original_title: str,
    existing_titles: Set[str],
    config: Dict,
) -> Optional[str]:
    """使用API生成新标题"""
    clean_title = clean_title_from_modifiers(original_title)
    clean_title = re.sub(r'\s+\d+$', '', clean_title)
    clean_title = re.sub(r'New\s+New', 'New', clean_title)
    clean_title = re.sub(r'\b(\d+)\s+\1\b', r'\1', clean_title)
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    
    base_concept = clean_title
    base_concept = re.sub(r'\s+\d+$', '', base_concept)
    base_concept = re.sub(r'^\d+\s+', '', base_concept)
    
    prompt = f"""Generate a creative, unique, and memorable song title for a music track.

Original title concept: "{base_concept}"

Requirements:
- 2-6 words, natural and flowing
- Enthusiastic, motivational, evocative, and poetic
- Complete phrase (not a fragment)
- NO numbered suffixes like "(2)", "(3)", or standalone numbers at the end
- NO repetitive phrases
- NO "Episode" identifiers
- NO simple modifier additions
- NO "New New" patterns
- Must be unique and different from these existing titles: {', '.join(list(existing_titles)[:20])}

Output ONLY the title, nothing else. No quotes, no explanations."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a creative music title generator. Generate unique, memorable song titles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=32,
        )
        
        new_title = response.choices[0].message.content.strip()
        new_title = new_title.strip('"\'')
        new_title = new_title.strip()
        
        if new_title:
            new_title = new_title[0].upper() + new_title[1:] if len(new_title) > 1 else new_title.upper()
        
        return new_title
    except Exception:
        return None

def replace_problematic_title(
    title: str,
    used_templates: Set[str],
    config: Dict,
    client: Optional[OpenAI] = None,
    model: str = "gpt-4o-mini",
    existing_titles: Set[str] = None,
) -> str:
    """替换问题标题"""
    if existing_titles is None:
        existing_titles = set()
    
    # 如果启用API且有客户端，使用API
    if config.get("use_api_for_problems") and client:
        new_title = generate_title_api(client, model, title, existing_titles, config)
        if new_title:
            return new_title
    
    # 否则使用模板库
    templates = config.get("title_templates", [])
    available = [t for t in templates if t not in used_templates]
    if not available:
        available = templates
    
    new_title = random.choice(available)
    used_templates.add(new_title)
    return new_title

def replace_duplicate_title(
    title: str,
    used_titles: Set[str],
    used_templates: Set[str],
    config: Dict,
) -> str:
    """替换重复的标题"""
    base_title = clean_title_from_modifiers(title)
    templates = config.get("title_templates", [])
    
    available = [t for t in templates if t not in used_titles and t not in used_templates]
    if available:
        new_title = random.choice(available)
        used_titles.add(new_title)
        used_templates.add(new_title)
        return new_title
    
    available = [t for t in templates if t not in used_titles]
    if available:
        new_title = random.choice(available)
        used_titles.add(new_title)
        return new_title
    
    # 生成变体（不使用数字）
    modifiers = ["Eternal", "Ultimate", "Final", "Prime", "Elite", "Supreme", "Absolute"]
    for modifier in modifiers:
        variant = f"{base_title} {modifier}"
        if variant not in used_titles:
            used_titles.add(variant)
            return variant
    
    return base_title

def generate_artist_name(
    base_title: str,
    artist_counter: Dict[str, int],
    audio_duration_sec: Optional[float],
    config: Dict,
) -> Tuple[str, str]:
    """生成艺术家名字和版本后缀"""
    # 特殊艺术家
    use_special = random.random() < 0.02
    special_artists = config.get("special_artists", [])
    if use_special and special_artists:
        artist = random.choice(special_artists)
        max_songs = config.get("max_special_artist_songs", 5)
        if artist_counter.get(artist, 0) < max_songs:
            artist_counter[artist] = artist_counter.get(artist, 0) + 1
            version_suffix = ""
            if random.random() < 0.2:
                collab = random.choice(config.get("collab_artists", []))
                version_suffix = f" ft. {collab}"
            return artist, version_suffix
    
    # 版本后缀
    version_suffix = ""
    rand = random.random()
    
    if rand < 0.3:  # 30% remix
        remix_djs = config.get("remix_djs", [])
        dj = random.choice(remix_djs)
        max_songs = config.get("max_special_artist_songs", 5)
        if artist_counter.get(dj, 0) < max_songs:
            artist_counter[dj] = artist_counter.get(dj, 0) + 1
            artist_pool = config.get("artist_pool", [])
            available_artists = [
                a for a in artist_pool 
                if a not in remix_djs and artist_counter.get(a, 0) < config.get("max_artist_songs", 3)
            ]
            if not available_artists:
                available_artists = [a for a in artist_pool if a not in remix_djs]
            original_artist = random.choice(available_artists)
            artist_counter[original_artist] = artist_counter.get(original_artist, 0) + 1
            version_suffix = f" (remixed by {dj})"
            return original_artist, version_suffix
    elif rand < 0.5:  # 20% 其他版本
        version_suffix = f" {random.choice(config.get('version_suffixes', []))}"
    elif rand < 0.7:  # 20% ft.
        version_suffix = f" ft. {random.choice(config.get('collab_artists', []))}"
    
    if audio_duration_sec and audio_duration_sec > 240:
        version_suffix = " (Extended Version)"
    
    # 普通艺术家
    artist_pool = config.get("artist_pool", [])
    max_songs = config.get("max_artist_songs", 3)
    available_artists = [
        a for a in artist_pool 
        if artist_counter.get(a, 0) < max_songs
    ]
    
    if not available_artists:
        available_artists = artist_pool
    
    artist = random.choice(available_artists)
    artist_counter[artist] = artist_counter.get(artist, 0) + 1
    
    return artist, version_suffix

def rename_channel_library(
    channel_id: str,
    channels_root: Path,
    model: str = "gpt-4o-mini",
    execute: bool = False,
    use_api: bool = True,
    source_dir: Optional[str] = None,
) -> None:
    """
    McPOS 频道歌库批量重命名主函数
    
    Args:
        channel_id: 频道ID（如 "rbr", "kat"）
        channels_root: 频道根目录（默认：channels/）
        model: OpenAI模型名称
        execute: 是否执行实际重命名
        use_api: 是否使用API修复问题标题
        source_dir: 源目录名称（相对于 library/），如果为 None 则使用默认的 "songs"
                    例如："Suno 0127" 表示处理 channels/{channel_id}/library/Suno 0127/ 目录
    """
    if source_dir:
        songs_dir = channels_root / channel_id / "library" / source_dir
    else:
        songs_dir = channels_root / channel_id / "library" / "songs"
    
    if not songs_dir.exists():
        raise ValueError(f"歌曲目录不存在: {songs_dir}")
    
    # 加载频道配置
    config = load_channel_config(channel_id, channels_root)
    
    # 初始化API客户端
    client = None
    if use_api:
        if OpenAI is None:
            use_api = False
        else:
            api_key_path = Path("config/openai_api_key.txt")
            if api_key_path.exists():
                api_key = api_key_path.read_text().strip()
            else:
                api_key = os.getenv("OPENAI_API_KEY")
            
            if api_key:
                client = OpenAI(api_key=api_key)
            else:
                use_api = False
    
    # 查找所有MP3文件，但只处理尚未重命名的文件（不包含" - "的文件）
    all_mp3_files = list(songs_dir.glob("*.mp3"))
    files_to_process = [f for f in all_mp3_files if " - " not in f.name]
    
    if not files_to_process:
        print(f"⚠️  频道 {channel_id} 的歌曲目录中没有需要重命名的文件")
        print(f"   （所有文件都已使用新格式：\"歌曲名 - 艺术家名.mp3\"）")
        return
    
    print(f"频道: {channel_id}")
    print(f"总MP3文件数: {len(all_mp3_files)}")
    print(f"需要重命名的文件: {len(files_to_process)} 个\n")
    
    if execute:
        print("⚠️  执行模式：将真正重命名文件\n")
    else:
        print("⚠️  DRY-RUN 模式：不会真正重命名文件\n")
    
    # 初始化
    artist_counter: Dict[str, int] = {}
    seen_titles: Set[str] = set()
    used_titles: Set[str] = set()
    used_templates: Set[str] = set()
    plan = []
    
    # 处理每个文件
    for idx, file_path in enumerate(files_to_process, 1):
        filename = file_path.name
        
        # 提取基础标题
        base_title = extract_base_title(filename)
        base_title = clean_title(base_title)
        
        if not base_title:
            base_title = "Untitled"
        
        # 检查并替换问题标题
        if is_problematic_title(base_title, config):
            base_title = replace_problematic_title(
                base_title, used_templates, config, client, model, used_titles
            )
        
        # 检查并替换重复标题
        # Hard cap to prevent runaway generation cost/time.
        max_attempts = 2
        attempt = 0
        while base_title in used_titles and attempt < max_attempts:
            base_title = replace_duplicate_title(base_title, used_titles, used_templates, config)
            attempt += 1
        
        # 如果仍然重复，使用修饰词
        if base_title in used_titles:
            original_base = clean_title_from_modifiers(base_title)
            modifiers = ["Eternal", "Ultimate", "Final", "Prime", "Elite"]
            for modifier in modifiers:
                variant = f"{original_base} {modifier}"
                if variant not in used_titles:
                    base_title = variant
                    break
        
        used_titles.add(base_title)
        
        # 获取音频时长
        audio_duration_sec = get_audio_duration_seconds(file_path)
        
        # 生成艺术家和版本后缀
        artist, version_suffix = generate_artist_name(
            base_title, artist_counter, audio_duration_sec, config
        )
        
        # 生成新文件名
        suffix = file_path.suffix
        if version_suffix:
            new_name = f"{base_title} - {artist}{version_suffix}{suffix}"
        else:
            new_name = f"{base_title} - {artist}{suffix}"
        
        # 确保文件名唯一
        counter = 1
        base_new_name = new_name
        while new_name.lower() in seen_titles:
            new_name = f"{base_title} {counter} - {artist}{version_suffix}{suffix}"
            counter += 1
        seen_titles.add(new_name.lower())
        
        plan.append((filename, new_name, artist))
        
        if execute:
            new_path = songs_dir / new_name
            if new_path.exists() and file_path != new_path:
                print(f"[{idx}/{len(all_mp3_files)}] ⚠️  目标文件已存在: {new_name}")
                continue
            
            try:
                file_path.rename(new_path)
                if idx % 50 == 0 or idx == len(files_to_process):
                    print(f"[{idx}/{len(files_to_process)}] ✅ {filename} -> {new_name}")
            except Exception as exc:
                print(f"[{idx}/{len(files_to_process)}] ❌ 失败: {filename} -> {new_name} ({exc})")
        else:
            if idx % 50 == 0 or idx == len(files_to_process):
                print(f"[{idx}/{len(files_to_process)}] 📝 {filename} -> {new_name}")
    
    # 写入CSV计划
    output_csv = songs_dir / "rename_plan.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["old", "new", "artist"])
        for old, new, artist in plan:
            writer.writerow([old, new, artist])
    
    print(f"\n✅ 计划已写入: {output_csv}")
    print(f"   共 {len(plan)} 个文件")
