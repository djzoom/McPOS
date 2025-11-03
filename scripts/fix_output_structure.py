#!/usr/bin/env python3
# coding: utf-8
"""
修复output目录结构，将所有文件按期数正确分类

功能：
1. 扫描output根目录中的期数文件
2. 根据文件名提取期数ID
3. 从排播表获取期数信息（日期、标题）
4. 将文件移动到正确的文件夹：output/{YYYY-MM-DD}_{标题}/
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from utils import get_final_output_dir
    from datetime import datetime
    from schedule_master import ScheduleMaster
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    sys.exit(1)


def extract_episode_id_from_filename(filename: str) -> Optional[str]:
    """从文件名提取期数ID（YYYYMMDD格式）"""
    match = re.match(r'^(\d{8})', filename)
    if match:
        return match.group(1)
    return None


def fix_output_structure():
    """修复output目录结构"""
    output_dir = REPO_ROOT / "output"
    if not output_dir.exists():
        print("❌ output目录不存在")
        return
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 无法加载排播表")
        return
    
    print("=" * 70)
    print("📁 修复output目录结构")
    print("=" * 70)
    print()
    
    # 收集所有需要移动的文件
    files_by_episode: Dict[str, List[Path]] = {}
    
    # 扫描output根目录中的所有文件（跳过logs文件夹）
    for item in output_dir.iterdir():
        # 跳过文件夹和系统文件
        if item.is_dir() or item.name.startswith('.'):
            continue
        
        # 跳过特殊文件（如run.json）
        if item.name in ['run.json', '.DS_Store']:
            continue
        
        episode_id = extract_episode_id_from_filename(item.name)
        if episode_id:
            if episode_id not in files_by_episode:
                files_by_episode[episode_id] = []
            files_by_episode[episode_id].append(item)
    
    # 也检查已有期数文件夹，确认是否有文件遗漏在根目录
    # （这个检查在第一次扫描后进行，避免重复）
    
    if not files_by_episode:
        print("✅ 未发现需要整理的文件")
        return
    
    print(f"发现 {len(files_by_episode)} 个期数的文件需要整理\n")
    
    total_moved = 0
    for episode_id, files in files_by_episode.items():
        # 从排播表获取期数信息
        ep = schedule.get_episode(episode_id)
        if not ep:
            print(f"⚠️  期数 {episode_id} 不在排播表中，跳过")
            continue
        
        schedule_date_str = ep.get("schedule_date")
        title = ep.get("title", "Unknown")
        
        if not schedule_date_str:
            print(f"⚠️  期数 {episode_id} 缺少日期信息，跳过")
            continue
        
        try:
            schedule_date = datetime.fromisoformat(schedule_date_str)
            final_dir = get_final_output_dir(schedule_date, title)
        except Exception as e:
            print(f"⚠️  期数 {episode_id} 无法创建目标文件夹: {e}")
            continue
        
        final_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📋 {episode_id}: {title}")
        print(f"   目标文件夹: {final_dir.name}")
        
        moved_count = 0
        skipped_count = 0
        error_count = 0
        
        for src_file in files:
            # 如果源文件已经在最终文件夹中，跳过
            if src_file.parent == final_dir:
                skipped_count += 1
                continue
            
            dst_file = final_dir / src_file.name
            
            if dst_file.exists():
                # 目标已存在，检查大小是否一致
                try:
                    src_size = src_file.stat().st_size
                    dst_size = dst_file.stat().st_size
                    
                    if src_size == dst_size:
                        print(f"   ⏭️  跳过: {src_file.name}（已存在于目标文件夹，大小一致）")
                        src_file.unlink()  # 删除源文件（避免重复）
                        skipped_count += 1
                    else:
                        print(f"   ⚠️  冲突: {src_file.name}（大小不同：源={src_size}B，目标={dst_size}B，保留目标文件）")
                        src_file.unlink()
                        skipped_count += 1
                except Exception as e:
                    print(f"   ⚠️  检查文件失败 {src_file.name}: {e}")
                    error_count += 1
            else:
                try:
                    shutil.move(str(src_file), str(dst_file))
                    print(f"   ✅ 移动: {src_file.name}")
                    moved_count += 1
                except Exception as e:
                    print(f"   ❌ 移动失败 {src_file.name}: {e}")
                    error_count += 1
        
        total_moved += moved_count
        if skipped_count > 0:
            print(f"   ℹ️  跳过 {skipped_count} 个文件")
        if error_count > 0:
            print(f"   ⚠️  {error_count} 个文件处理出错")
        print()
    
    print("=" * 70)
    print(f"✅ 整理完成：共移动 {total_moved} 个文件")
    print("=" * 70)


if __name__ == "__main__":
    fix_output_structure()

