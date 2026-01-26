#!/usr/bin/env python3
"""
修复12月所有期数的description文件：
1. 移除所有"**"（双星号）
2. 移除所有"------"（长串的"-"，3个或以上）
"""

import sys
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent


def fix_description_file(file_path: Path) -> bool:
    """修复单个description文件"""
    try:
        # 读取文件
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # 1. 移除所有"**"
        content = content.replace('**', '')
        
        # 2. 移除所有长串的"-"（3个或以上）
        # 使用正则表达式匹配3个或以上的连续"-"
        content = re.sub(r'-{3,}', '', content)
        
        # 如果内容有变化，保存
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        return False


def main():
    print("=" * 60)
    print("🔧 修复12月所有期数的description文件")
    print("=" * 60)
    print("操作:")
    print("  1. 移除所有 '**' (双星号)")
    print("  2. 移除所有 '---' 或更长的 '-' 串")
    print("=" * 60)
    print()
    
    # 查找所有12月的description文件
    # 文件可能在两个位置：
    # 1. channels/kat_lofi/output/{episode_id}/{episode_id}_youtube_description.txt
    # 2. output/2025-12-XX_Title/{episode_id}_youtube_description.txt
    
    description_files = []
    
    # 位置1: channels/kat_lofi/output/
    channel_output_dir = REPO_ROOT / "channels" / "kat_lofi" / "output"
    for episode_dir in sorted(channel_output_dir.glob("202512*")):
        if episode_dir.is_dir():
            desc_file = episode_dir / f"{episode_dir.name}_youtube_description.txt"
            if desc_file.exists():
                description_files.append(desc_file)
    
    # 位置2: output/ 根目录下的最终打包文件夹
    output_root = REPO_ROOT / "output"
    if output_root.exists():
        for folder in sorted(output_root.glob("2025-12-*")):
            if folder.is_dir():
                # 查找文件夹内的description文件
                for desc_file in folder.glob("202512*_youtube_description.txt"):
                    if desc_file not in description_files:  # 避免重复
                        description_files.append(desc_file)
    
    if not description_files:
        print("❌ 未找到12月的description文件")
        return
    
    print(f"📋 找到 {len(description_files)} 个description文件")
    print()
    
    # 处理每个文件
    fixed_count = 0
    unchanged_count = 0
    
    for desc_file in description_files:
        episode_id = desc_file.parent.name
        print(f"处理: {episode_id}...", end=" ")
        
        if fix_description_file(desc_file):
            print("✅ 已修复")
            fixed_count += 1
        else:
            print("⏭️  无需修改")
            unchanged_count += 1
    
    print()
    print("=" * 60)
    print("📊 修复完成")
    print("=" * 60)
    print(f"✅ 已修复: {fixed_count} 个文件")
    print(f"⏭️  无需修改: {unchanged_count} 个文件")
    print("=" * 60)


if __name__ == "__main__":
    main()

