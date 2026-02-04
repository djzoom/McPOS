"""
优化 Poor_Titles 目录中的歌曲标题

功能：
- 只处理 Poor_Titles 目录中的文件
- 确保不与 RBR_Songs_Library 中的标题重复
- 自动检测并修复问题标题
- 使用API生成富有创意的标题
"""

from __future__ import annotations

import csv
import os
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .library_renamer import (
    DEFAULT_CONFIG,
    clean_title,
    clean_title_from_modifiers,
    extract_base_title,
    generate_artist_name,
    get_audio_duration_seconds,
    is_problematic_title,
    load_channel_config,
    replace_duplicate_title,
    replace_problematic_title,
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def extract_used_titles_from_ok_library(ok_dir: Path) -> Set[str]:
    """从OK库中提取所有已使用的标题"""
    used_titles = set()
    
    if not ok_dir.exists():
        return used_titles
    
    for mp3_file in ok_dir.glob("*.mp3"):
        name = mp3_file.name
        if " - " in name:
            title = name.split(" - ")[0]
            used_titles.add(title.lower())
    
    return used_titles


def optimize_poor_titles(
    channel_id: str,
    channels_root: Path,
    model: str = "gpt-4o-mini",
    execute: bool = False,
    use_api: bool = True,
) -> None:
    """
    优化 Poor_Titles 目录中的歌曲标题
    
    Args:
        channel_id: 频道ID（如 "rbr"）
        channels_root: 频道根目录
        model: OpenAI模型名称
        execute: 是否执行实际重命名
        use_api: 是否使用API修复问题标题
    """
    songs_dir = channels_root / channel_id / "library" / "songs"
    poor_dir = songs_dir / "Poor_Titles"
    ok_dir = songs_dir / "RBR_Songs_Library"
    
    if not poor_dir.exists():
        print(f"⚠️  Poor_Titles 目录不存在: {poor_dir}")
        return
    
    # 提取已使用的标题
    used_titles_from_ok = extract_used_titles_from_ok_library(ok_dir)
    print(f"从 RBR_Songs_Library 提取了 {len(used_titles_from_ok)} 个已使用的标题")
    
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
    
    # 查找 Poor_Titles 中的所有MP3文件
    poor_files = list(poor_dir.glob("*.mp3"))
    
    if not poor_files:
        print(f"⚠️  Poor_Titles 目录中没有MP3文件")
        return
    
    print(f"Poor_Titles 目录: {len(poor_files)} 个文件需要优化\n")
    
    if execute:
        print("⚠️  执行模式：将真正重命名文件\n")
    else:
        print("⚠️  DRY-RUN 模式：不会真正重命名文件\n")
    
    # 初始化
    artist_counter: Dict[str, int] = {}
    seen_titles: Set[str] = set()
    used_titles: Set[str] = used_titles_from_ok.copy()  # 包含OK库中的标题
    used_templates: Set[str] = set()
    plan = []
    
    # 处理每个文件
    for idx, file_path in enumerate(poor_files, 1):
        filename = file_path.name
        
        # 如果文件已经重命名过（包含" - "），先提取标题部分
        if " - " in filename:
            # 已经重命名的文件，提取标题部分（" - "之前的部分）
            title_part = filename.split(" - ")[0]
            # 清理可能的版本后缀（如 (2), (Extended Version) 等）
            title_part = re.sub(r'\s*\([^)]*\)\s*$', '', title_part)  # 去掉末尾的括号内容
            title_part = re.sub(r'\s*(Extended|Remix|Version|Edition|Mix|Radio)\s*$', '', title_part, flags=re.IGNORECASE)
            
            # 检查标题是否包含了艺术家名字（通常是两个单词的组合，且第二个单词看起来像艺术家名字）
            # 常见的艺术家名字模式：两个单词，首字母都大写
            words = title_part.split()
            if len(words) >= 3:
                # 如果最后两个单词都是首字母大写，且不是常见的标题词，可能是艺术家名字
                last_two = ' '.join(words[-2:])
                # 检查是否是已知的艺术家名字模式（两个单词，都是首字母大写）
                if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', last_two):
                    # 检查是否在已知的艺术家池中（简单启发式：如果看起来不像标题词，就可能是艺术家）
                    common_title_words = {'the', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'from', 'by', 'and', 'or', 'but'}
                    if words[-2].lower() not in common_title_words and words[-1].lower() not in common_title_words:
                        # 可能是艺术家名字，去掉最后两个单词
                        title_part = ' '.join(words[:-2])
            
            base_title = title_part.strip()
        else:
            # 未重命名的文件，使用标准提取方法
            base_title = extract_base_title(filename)
        
        base_title = clean_title(base_title)
        
        # 如果标题太短（只有一个词），尝试从原始文件名提取更多信息
        if len(base_title.split()) < 2:
            # 尝试从原始文件名提取更多信息
            if " - " in filename:
                # 如果原始文件名有" - "，说明可能标题被过度清理了
                # 尝试提取" - "之前的所有内容，但去掉明显的版本后缀
                title_part = filename.split(" - ")[0]
                # 只去掉末尾的版本后缀，保留更多内容
                title_part = re.sub(r'\s*\([^)]*\)\s*$', '', title_part)
                title_part = re.sub(r'\s*(Extended|Remix|Version|Edition|Mix|Radio)\s*$', '', title_part, flags=re.IGNORECASE)
                if len(title_part.split()) >= 2:
                    base_title = clean_title(title_part)
        
        # 如果标题仍然包含问题词汇，标记为问题标题（会在后续处理）
        if any(word.lower() in ['edm', 'trance', 'energy', 'motivative', 'deep', 'thinkin', 'edit'] for word in base_title.split()):
            # 包含描述性词汇，标记为问题标题
            pass  # 会在后续的 is_problematic_title 检查中处理
        
        if not base_title:
            base_title = "Untitled"
        
        # 检查并替换问题标题
        if is_problematic_title(base_title, config):
            base_title = replace_problematic_title(
                base_title, used_templates, config, client, model, used_titles
            )
        
        # 检查是否与OK库重复
        # Hard cap to prevent runaway generation cost/time.
        max_attempts = 2
        attempt = 0
        while base_title.lower() in used_titles and attempt < max_attempts:
            # 如果与OK库重复，必须生成新标题
            if base_title.lower() in used_titles_from_ok:
                # 使用API生成新标题（如果可用）
                if use_api and client:
                    new_title = replace_problematic_title(
                        base_title, used_templates, config, client, model, used_titles
                    )
                    if new_title and new_title.lower() not in used_titles:
                        base_title = new_title
                        break
                
                # 否则使用模板库
                base_title = replace_duplicate_title(base_title, used_titles, used_templates, config)
            else:
                # 只是与当前批次重复，使用变体
                base_title = replace_duplicate_title(base_title, used_titles, used_templates, config)
            attempt += 1
        
        # 如果仍然重复，使用修饰词
        if base_title.lower() in used_titles:
            original_base = clean_title_from_modifiers(base_title)
            modifiers = ["Eternal", "Ultimate", "Final", "Prime", "Elite", "Supreme", "Absolute"]
            for modifier in modifiers:
                variant = f"{original_base} {modifier}"
                if variant.lower() not in used_titles:
                    base_title = variant
                    break
        
        used_titles.add(base_title.lower())
        
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
            new_path = poor_dir / new_name
            if new_path.exists() and file_path != new_path:
                print(f"[{idx}/{len(poor_files)}] ⚠️  目标文件已存在: {new_name}")
                continue
            
            try:
                file_path.rename(new_path)
                if idx % 10 == 0 or idx == len(poor_files):
                    print(f"[{idx}/{len(poor_files)}] ✅ {filename} -> {new_name}")
            except Exception as exc:
                print(f"[{idx}/{len(poor_files)}] ❌ 失败: {filename} -> {new_name} ({exc})")
        else:
            if idx % 10 == 0 or idx == len(poor_files):
                print(f"[{idx}/{len(poor_files)}] 📝 {filename} -> {new_name}")
    
    # 写入CSV计划
    output_csv = poor_dir / "optimize_plan.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["old", "new", "artist"])
        for old, new, artist in plan:
            writer.writerow([old, new, artist])
    
    print(f"\n✅ 计划已写入: {output_csv}")
    print(f"   共 {len(plan)} 个文件")
    
    # 验证结果
    print(f"\n验证结果:")
    final_titles = set()
    duplicates_found = []
    for _, new_name, _ in plan:
        if " - " in new_name:
            title = new_name.split(" - ")[0].lower()
            if title in final_titles:
                duplicates_found.append(new_name)
            final_titles.add(title)
    
    if duplicates_found:
        print(f"  ⚠️  发现 {len(duplicates_found)} 个重复标题:")
        for dup in duplicates_found[:10]:
            print(f"    {dup}")
    else:
        print(f"  ✅ 所有标题都是唯一的")
    
    # 检查与OK库的重复
    conflicts = []
    for _, new_name, _ in plan:
        if " - " in new_name:
            title = new_name.split(" - ")[0].lower()
            if title in used_titles_from_ok:
                conflicts.append(new_name)
    
    if conflicts:
        print(f"  ⚠️  发现 {len(conflicts)} 个与 RBR_Songs_Library 冲突的标题:")
        for conflict in conflicts[:10]:
            print(f"    {conflict}")
    else:
        print(f"  ✅ 没有与 RBR_Songs_Library 冲突的标题")
