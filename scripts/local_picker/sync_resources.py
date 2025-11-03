#!/usr/bin/env python3
# coding: utf-8
"""
【已废弃】同步排播表资源标记到歌库和图库

⚠️  此脚本已废弃，不再使用。

新架构使用：
- schedule.sync_images_from_assignments() - 基于分配的图片使用标记同步
- 歌曲使用从排播表动态查询，不需要单独的CSV文件

此文件保留仅用于向后兼容，但不应再被调用。
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster
    SCHEDULE_AVAILABLE = True
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    SCHEDULE_AVAILABLE = False
    sys.exit(1)


def sync_images(schedule: ScheduleMaster, dry_run: bool = False) -> int:
    """
    同步图片使用标记
    
    标记原则：
    - 只有状态为"已完成"的期数才标记图片为已使用
    - demo模式不算使用
    - 如果排播表只有15期，且都已完成，则应该有15张图被标记使用
    
    Returns:
        同步的图片数量
    """
    from episode_status import STATUS_已完成, normalize_status
    
    # 从排播表中提取所有已完成的期数使用的图片
    used_images_from_episodes = set()
    for ep in schedule.episodes:
        # 只标记状态为"已完成"的期数的图片
        status = normalize_status(ep.get("status", ""))
        if status == STATUS_已完成:
            image_path = ep.get("image_path")
            if image_path:
                used_images_from_episodes.add(image_path)
    
    # 添加缺失的标记（已完成的期数但图片未标记）
    added_count = 0
    for img in used_images_from_episodes:
        if img not in schedule.images_used:
            if not dry_run:
                schedule.mark_image_used(img)
            added_count += 1
    
    # 清理多余的标记（已标记但对应期数未完成）
    removed_count = 0
    extra_marked = schedule.images_used - used_images_from_episodes
    for img in extra_marked:
        if not dry_run:
            schedule.images_used.discard(img)
        removed_count += 1
    
    if not dry_run and (added_count > 0 or removed_count > 0):
        schedule.save()
    
    return added_count - removed_count


def sync_songs(schedule: ScheduleMaster, dry_run: bool = False) -> int:
    """
    同步歌曲使用记录到 song_usage.csv
    
    Returns:
        更新的歌曲数量
    """
    # 加载 song_usage.csv
    usage_path = REPO_ROOT / "data" / "song_usage.csv"
    if not usage_path.exists():
        print(f"⚠️  警告：song_usage.csv 不存在，跳过歌曲同步")
        return 0
    
    # 读取现有记录
    records: Dict[str, Dict] = {}
    if usage_path.exists():
        with usage_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_path = row.get("file_path", "")
                if file_path:
                    records[file_path] = row
    
    # 从排播表中提取所有使用的歌曲
    all_used_tracks = schedule.get_all_used_tracks()
    
    # 需要将曲目标题映射到文件路径
    # 读取 song_library.csv 来建立映射
    library_path = REPO_ROOT / "data" / "song_library.csv"
    if not library_path.exists():
        print(f"⚠️  警告：song_library.csv 不存在，无法映射曲目到文件路径")
        return 0
    
    title_to_path: Dict[str, str] = {}
    with library_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("title", "").strip()
            file_path = row.get("file_path", "").strip()
            if title and file_path:
                title_to_path[title] = file_path
    
    # 更新使用记录
    updated_count = 0
    now = datetime.now().isoformat()
    
    for track_title in all_used_tracks:
        file_path = title_to_path.get(track_title)
        if not file_path:
            # 如果找不到映射，跳过
            continue
        
        if file_path in records:
            # 更新现有记录
            record = records[file_path]
            record["last_used_at"] = now
            times_used = int(record.get("times_used", "0") or "0")
            record["times_used"] = str(times_used + 1)
            updated_count += 1
        else:
            # 创建新记录（但需要从 library 获取完整信息）
            # 这里简化处理：只标记使用，不创建完整记录
            # 完整记录应该由 generate_song_library.py 创建
            pass
    
    # 保存更新后的记录
    if not dry_run and updated_count > 0:
        with usage_path.open("w", encoding="utf-8", newline="") as f:
            if records:
                fieldnames = list(records[list(records.keys())[0]].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for record in records.values():
                    writer.writerow(record)
    
    return updated_count


def main():
    parser = argparse.ArgumentParser(description="同步排播表资源标记到歌库和图库")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际修改文件")
    args = parser.parse_args()
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在，请先创建排播表")
        sys.exit(1)
    
    print("=" * 70)
    print("🔄 同步排播表资源标记")
    print("=" * 70)
    print()
    
    if args.dry_run:
        print("🔍 预览模式（不会实际修改文件）")
        print()
    
    # 同步图片
    print("📸 同步图片使用标记...")
    images_synced = sync_images(schedule, dry_run=args.dry_run)
    if images_synced > 0:
        print(f"  ✅ 已同步 {images_synced} 个图片标记")
    elif images_synced < 0:
        print(f"  ✅ 已清理 {abs(images_synced)} 个多余的图片标记")
    else:
        print(f"  ℹ️  图片标记已是最新状态")
    
    # 同步歌曲
    print()
    print("🎵 同步歌曲使用记录...")
    songs_synced = sync_songs(schedule, dry_run=args.dry_run)
    if songs_synced > 0:
        print(f"  ✅ 已更新 {songs_synced} 首歌曲的使用记录")
    else:
        print(f"  ℹ️  歌曲使用记录已是最新状态")
    
    print()
    print("=" * 70)
    if args.dry_run:
        print("💡 这是预览模式，未实际修改文件")
        print("   运行不带 --dry-run 的参数以执行实际同步")
    else:
        print("✅ 同步完成")
    print("=" * 70)


if __name__ == "__main__":
    main()

