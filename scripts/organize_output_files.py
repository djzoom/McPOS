#!/usr/bin/env python3
# coding: utf-8
"""
整理output目录文件，将所有文件按期数分类存放到正确的文件夹

功能：
1. 扫描output根目录中的期数文件（如 20251121_cover.png）
2. 扫描output/youtube目录中的文件
3. 根据文件名提取期数ID
4. 从排播表获取期数信息（日期、标题）
5. 将文件移动到正确的文件夹：output/{YYYY-MM-DD}_{标题}/
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from utils import get_final_output_dir
    from datetime import datetime
except ImportError:
    print("❌ 无法导入必要模块")
    sys.exit(1)


def extract_episode_id_from_filename(filename: str) -> Optional[str]:
    """从文件名提取期数ID（YYYYMMDD格式）"""
    # 匹配 20251121_ 或 20251121 开头的文件名
    match = re.match(r'^(\d{8})', filename)
    if match:
        return match.group(1)
    return None


def load_schedule() -> Optional[Dict]:
    """加载排播表"""
    schedule_path = REPO_ROOT / "config" / "schedule_master.json"
    if not schedule_path.exists():
        return None
    
    try:
        with schedule_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  加载排播表失败: {e}")
        return None


def get_episode_info(episode_id: str, schedule: Dict) -> Optional[Tuple[str, str]]:
    """从排播表获取期数信息（日期、标题）"""
    episodes = schedule.get('episodes', [])
    for ep in episodes:
        if ep.get('episode_id') == episode_id:
            schedule_date = ep.get('schedule_date', '')
            title = ep.get('title', '')
            return schedule_date, title
    return None


def organize_files():
    """整理文件"""
    output_base = REPO_ROOT / "output"
    
    # 加载排播表
    schedule = load_schedule()
    if not schedule:
        print("⚠️  未找到排播表，将使用文件名中的日期")
    
    # 扫描output根目录
    print("📂 扫描 output 根目录...")
    root_files = []
    for file_path in output_base.iterdir():
        if file_path.is_file() and file_path.name[0].isdigit():
            # 跳过 .DS_Store 等系统文件
            if file_path.name.startswith('.'):
                continue
            episode_id = extract_episode_id_from_filename(file_path.name)
            if episode_id:
                root_files.append((file_path, episode_id))
    
    # 扫描output/youtube目录
    youtube_dir = output_base / "youtube"
    youtube_files = []
    if youtube_dir.exists():
        print("📂 扫描 output/youtube 目录...")
        for file_path in youtube_dir.iterdir():
            if file_path.is_file():
                episode_id = extract_episode_id_from_filename(file_path.name)
                if episode_id:
                    youtube_files.append((file_path, episode_id))
    
    # 按期数ID分组
    files_by_episode: Dict[str, List[Path]] = {}
    
    for file_path, episode_id in root_files + youtube_files:
        if episode_id not in files_by_episode:
            files_by_episode[episode_id] = []
        files_by_episode[episode_id].append(file_path)
    
    print(f"\n📊 找到 {len(files_by_episode)} 个期数的文件")
    
    # 整理每个期数的文件
    moved_total = 0
    skipped_total = 0
    
    for episode_id, files in sorted(files_by_episode.items()):
        print(f"\n📦 期数: {episode_id}")
        
        # 获取期数信息
        schedule_date = None
        title = None
        
        if schedule:
            info = get_episode_info(episode_id, schedule)
            if info:
                schedule_date_str, title = info
                try:
                    schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                except:
                    pass
        
        # 如果没有排播表信息，尝试从文件名解析日期
        if not schedule_date:
            try:
                schedule_date = datetime.strptime(episode_id, "%Y%m%d")
            except:
                print(f"  ⚠️  无法解析日期，跳过 {episode_id}")
                continue
        
        # 如果没有标题，使用默认标题
        if not title:
            title = f"Episode_{episode_id}"
        
        # 获取目标文件夹
        final_dir = get_final_output_dir(schedule_date, title)
        final_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"  📁 目标: {final_dir.name}")
        
        # 移动文件
        moved_count = 0
        skipped_count = 0
        
        for src_file in files:
            dst_file = final_dir / src_file.name
            
            if dst_file.exists():
                print(f"  ⚠️  跳过（已存在）: {src_file.name}")
                skipped_count += 1
            else:
                try:
                    shutil.move(str(src_file), str(dst_file))
                    print(f"  ✓ 移动: {src_file.name}")
                    moved_count += 1
                except Exception as e:
                    print(f"  ❌ 移动失败 {src_file.name}: {e}")
        
        print(f"  📊 {moved_count} 个文件已移动, {skipped_count} 个已跳过")
        moved_total += moved_count
        skipped_total += skipped_count
    
    print(f"\n✅ 整理完成!")
    print(f"   📦 总共移动: {moved_total} 个文件")
    print(f"   ⚠️  总共跳过: {skipped_total} 个文件")
    
    # 检查是否可以删除空的youtube目录
    if youtube_dir.exists():
        remaining = list(youtube_dir.iterdir())
        if not remaining or all(f.name.startswith('.') for f in remaining):
            try:
                youtube_dir.rmdir()
                print(f"\n🗑️  已删除空的 output/youtube 目录")
            except:
                pass
    


if __name__ == "__main__":
    print("🎵 Kat Records - 文件整理工具")
    print("=" * 50)
    
    # 确认
    response = input("\n是否开始整理文件？(y/N): ").strip().lower()
    if response != 'y':
        print("❌ 已取消")
        sys.exit(0)
    
    organize_files()

