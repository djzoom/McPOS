#!/usr/bin/env python3
"""
修复问题标题 - 使用API生成新标题

修复以下问题：
- "New New" 重复
- 数字重复（如 "2 2", "3 2"）
- 其他奇怪的重复模式

保持艺术家和后缀不变，只修改标题部分。
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

def is_problematic_title(title: str) -> bool:
    """检测问题标题"""
    # 检测 "New New" 重复
    if "New New" in title:
        return True
    
    # 检测数字重复（如 "2 2", "3 2"）
    if re.search(r'\b(\d+)\s+\1\b', title):  # 相同数字重复
        return True
    
    if re.search(r'\b(\d+)\s+\d+\b', title):  # 多个数字（可能是 "2 2" 或 "3 2"）
        # 检查是否是正常的数字（如 "2024", "160 BPM"）
        words = title.split()
        for i, word in enumerate(words):
            if word.isdigit() and i < len(words) - 1:
                next_word = words[i + 1]
                # 如果下一个词也是数字，可能是问题
                if next_word.isdigit() and len(word) == 1 and len(next_word) == 1:
                    return True
    
    # 检测以数字结尾（如 "Title 2", "Title 3", "Title 4"）
    if re.search(r'\s+\d+$', title):
        return True
    
    return False

def extract_artist_and_suffix(new_name: str) -> Tuple[str, str]:
    """从新文件名中提取艺术家和后缀"""
    if " - " not in new_name:
        return "", ""
    
    parts = new_name.split(" - ", 1)
    if len(parts) != 2:
        return "", ""
    
    artist_part = parts[1]
    # 去掉扩展名
    artist_part = artist_part.replace(".mp3", "")
    
    # 提取版本后缀
    version_suffix = ""
    artist_name = artist_part
    
    # 检查各种后缀
    suffix_patterns = [
        r'\s+\(remixed by [^)]+\)$',
        r'\s+\(Extended Version\)$',
        r'\s+\(Radio Edition\)$',
        r'\s+\(Remix\)$',
        r'\s+\(Extended Mix\)$',
        r'\s+\(Club Mix\)$',
        r'\s+\(Original Mix\)$',
        r'\s+\(Radio Edit\)$',
        r'\s+ft\.\s+[^)]+$',
    ]
    
    for pattern in suffix_patterns:
        match = re.search(pattern, artist_part)
        if match:
            version_suffix = match.group(0)
            artist_name = artist_part[:match.start()].strip()
            break
    
    return artist_name, version_suffix

def generate_new_title_api(client: OpenAI, model: str, original_title: str, existing_titles: set) -> str:
    """使用API生成新的标题"""
    # 清理原标题，去掉问题部分
    clean_title = original_title
    # 去掉 "New New"
    clean_title = re.sub(r'New\s+New', 'New', clean_title)
    # 去掉重复的数字
    clean_title = re.sub(r'\b(\d+)\s+\1\b', r'\1', clean_title)
    # 去掉多个连续数字
    clean_title = re.sub(r'\b(\d+)\s+(\d+)\b', r'\1', clean_title)
    # 规范化空格
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    
    # 提取基础概念
    base_concept = clean_title
    # 去掉序号
    base_concept = re.sub(r'\s+\d+$', '', base_concept)
    base_concept = re.sub(r'^\d+\s+', '', base_concept)
    
    prompt = f"""Generate a creative, unique, and memorable song title for a running/workout music track.

Original title concept: "{base_concept}"

Requirements:
- 2-6 words, natural and flowing
- Enthusiastic, motivational, evocative, and poetic
- Complete phrase (not a fragment)
- NO numbered suffixes like "(2)", "(3)", or standalone numbers
- NO repetitive phrases like "Run Baby Run", "Run, Run"
- NO "Episode" identifiers
- NO simple modifier additions
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
        # 清理输出（去掉引号等）
        new_title = new_title.strip('"\'')
        new_title = new_title.strip()
        
        # 确保标题大小写正确（首字母大写）
        if new_title:
            new_title = new_title[0].upper() + new_title[1:] if len(new_title) > 1 else new_title.upper()
        
        return new_title
    except Exception as e:
        print(f"  ⚠️  API调用失败: {e}")
        return None

def main() -> None:
    parser = argparse.ArgumentParser(description="修复问题标题（使用API）")
    parser.add_argument(
        "--plan-csv",
        type=Path,
        default=Path("channels/rbr/library/songs/rename_plan_simple.csv"),
        help="重命名计划CSV文件",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI模型",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际修改",
    )
    args = parser.parse_args()
    
    if OpenAI is None:
        sys.exit("需要安装 openai 包: pip install openai")
    
    if not args.plan_csv.exists():
        sys.exit(f"计划文件不存在: {args.plan_csv}")
    
    # 读取API密钥
    api_key_path = Path("config/openai_api_key.txt")
    if api_key_path.exists():
        api_key = api_key_path.read_text().strip()
    else:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        sys.exit("需要 OpenAI API 密钥（config/openai_api_key.txt 或 OPENAI_API_KEY 环境变量）")
    
    client = OpenAI(api_key=api_key)
    
    # 读取CSV
    rows = []
    problems = []
    existing_titles = set()
    
    with args.plan_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            new_name = row.get("new", "")
            if " - " in new_name:
                title = new_name.split(" - ")[0]
                existing_titles.add(title.lower())
                
                if is_problematic_title(title):
                    problems.append((len(rows), row))
            rows.append(row)
    
    print(f"读取到 {len(rows)} 条记录")
    print(f"发现 {len(problems)} 个问题标题\n")
    
    if args.dry_run:
        print("⚠️  预览模式：不会实际修改CSV\n")
    else:
        print("⚠️  执行模式：将修改CSV文件\n")
    
    if not problems:
        print("✅ 没有发现问题标题")
        return
    
    # 修复问题标题
    fixed_count = 0
    failed_count = 0
    
    for idx, (row_idx, row) in enumerate(problems, 1):
        old_name = row.get("old", "")
        new_name = row.get("new", "")
        artist = row.get("artist", "")
        
        if " - " not in new_name:
            continue
        
        title = new_name.split(" - ")[0]
        artist_name, version_suffix = extract_artist_and_suffix(new_name)
        
        print(f"[{idx}/{len(problems)}] 修复: {old_name[:50]}...")
        print(f"  原标题: {title}")
        
        # 生成新标题
        new_title = generate_new_title_api(client, args.model, title, existing_titles)
        
        if not new_title:
            print(f"  ❌ 生成失败，跳过")
            failed_count += 1
            continue
        
        # 检查新标题是否重复，如果重复则重新生成（不使用数字后缀）
        max_retries = 5
        retry_count = 0
        while new_title.lower() in existing_titles and retry_count < max_retries:
            print(f"  ⚠️  新标题重复: {new_title}，重新生成...")
            # 重新生成标题，添加更多上下文避免重复
            new_title = generate_new_title_api(
                client, args.model, 
                f"{title} unique creative different", 
                existing_titles
            )
            if not new_title:
                break
            retry_count += 1
        
        # 如果还是重复，使用修饰词而不是数字
        if new_title and new_title.lower() in existing_titles:
            modifiers = ["Eternal", "Ultimate", "Final", "Prime", "Elite"]
            for modifier in modifiers:
                variant = f"{new_title} {modifier}"
                if variant.lower() not in existing_titles:
                    new_title = variant
                    break
        
        # 构建新文件名
        suffix = ".mp3"
        if version_suffix:
            new_full_name = f"{new_title} - {artist_name}{version_suffix}{suffix}"
        else:
            new_full_name = f"{new_title} - {artist_name}{suffix}"
        
        print(f"  新标题: {new_title}")
        print(f"  新文件名: {new_full_name}")
        
        # 更新行
        rows[row_idx]["new"] = new_full_name
        existing_titles.add(new_title.lower())
        fixed_count += 1
        
        print()
    
    # 写入CSV
    if not args.dry_run and fixed_count > 0:
        with args.plan_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["old", "new", "artist"])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        
        print(f"✅ 已修复 {fixed_count} 个标题")
        print(f"❌ 失败 {failed_count} 个标题")
        print(f"✅ CSV已更新: {args.plan_csv}")
    else:
        print(f"📝 预览：将修复 {fixed_count} 个标题")
        print(f"📝 预览：将失败 {failed_count} 个标题")

if __name__ == "__main__":
    main()

