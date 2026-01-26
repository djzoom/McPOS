#!/usr/bin/env python3
# coding: utf-8
"""
统一状态同步工具

从文件系统（output目录）重建所有状态数据源：
1. schedule_master.json - 从文件系统同步状态
2. production_log.json - 从文件系统重建记录
3. song_usage.csv - 从schedule_master.json生成（可选）

设计原则：文件系统为真相来源（Source of Truth）
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster
    # ⚠️ REMOVED: episode_state_manager import (Stateflow V4)
    # EpisodeStateManager removed - use ScheduleMaster and file_detect.py instead
    # 注意：production_log导入用于重建production_log.json（向后兼容）
    # 新架构以schedule_master.json为单一数据源，production_log.json仅用于兼容旧工具
    from production_log import ProductionLog, LibrarySnapshot
    from utils import get_final_output_dir
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


def find_all_episode_folders(output_dir: Path) -> Dict[str, Dict]:
    """
    扫描output目录，找到所有期数文件夹
    
    Returns:
        {episode_id: {"folder": Path, "date": datetime, "title": str}}
    """
    episodes = {}
    
    # 扫描output下的文件夹（格式：YYYY-MM-DD_Title）
    pattern = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(.+)$")
    
    for folder in output_dir.iterdir():
        if not folder.is_dir() or folder.name == "logs":
            continue
        
        match = pattern.match(folder.name)
        if match:
            year, month, day = match.groups()[:3]
            title = match.group(4)
            try:
                date = datetime(int(year), int(month), int(day))
                episode_id = date.strftime("%Y%m%d")
                episodes[episode_id] = {
                    "folder": folder,
                    "date": date,
                    "title": title,
                }
            except ValueError:
                continue
    
    return episodes


def check_files_in_folder(folder: Path, episode_id: str) -> Dict[str, bool]:
    """检查文件夹中的文件完整性"""
    files = {
        "playlist": (folder / f"{episode_id}_playlist.csv").exists(),
        "cover": (folder / f"{episode_id}_cover.png").exists(),
        "audio": any((folder / f"{episode_id}_{suffix}.mp3").exists() 
                     for suffix in ["full_mix", "playlist_full_mix"]),
        "youtube_srt": (folder / f"{episode_id}_youtube.srt").exists(),
        "youtube_title": (folder / f"{episode_id}_youtube_title.txt").exists(),
        "youtube_desc": (folder / f"{episode_id}_youtube_description.txt").exists(),
        "video": any((folder / f"{episode_id}_youtube.{ext}").exists() 
                     for ext in ["mp4", "mov"]),
    }
    return files


def sync_schedule_from_filesystem(dry_run: bool = False) -> Dict:
    """
    从文件系统同步schedule_master.json状态
    
    Returns:
        同步统计
    """
    print("⚠️  此功能已弃用（Stateflow V4）")
    print("   EpisodeStateManager 已移除，请使用统一的文件检测 API 替代：")
    print("   - Backend: /api/t2r/episodes/{episode_id}/assets")
    print("   - Frontend: useEpisodeAssets() hook")
    print("   - 文件系统是单一数据源（SSOT）")
    return {"synced": 0, "errors": 0, "updated": [], "rolled_back": []}


def rebuild_production_log_from_filesystem(dry_run: bool = False) -> Dict:
    """
    从文件系统重建production_log.json
    
    Returns:
        重建统计
    """
    output_dir = REPO_ROOT / "output"
    episodes = find_all_episode_folders(output_dir)
    
    production_log = ProductionLog.load()
    stats = {"created": 0, "updated": 0, "skipped": 0}
    
    tracklist_path = REPO_ROOT / "data" / "song_library.csv"
    library_snapshot = None
    if tracklist_path.exists():
        library_snapshot = get_library_snapshot(tracklist_path, track_count=0)
    
    for episode_id, info in episodes.items():
        folder = info["folder"]
        date = info["date"]
        title = info.get("title", "")
        
        # 检查文件完整性
        files = check_files_in_folder(folder, episode_id)
        is_complete = all(files.values())
        
        # 查找或创建记录
        record = production_log.find_record(episode_id)
        if not record:
            if not dry_run and library_snapshot:
                production_log.create_record(
                    schedule_date=date,
                    library_snapshot=library_snapshot,
                    status="completed" if is_complete else "pending"
                )
            stats["created"] += 1
        else:
            if not dry_run:
                production_log.update_record(
                    episode_id=episode_id,
                    status="completed" if is_complete else "pending",
                    output_dir=str(folder),
                    title=title,
                )
            stats["updated"] += 1
    
    if not dry_run:
        production_log.save()
    
    print(f"\n📊 生产日志重建结果：")
    print(f"  ✅ 创建记录: {stats['created']} 条")
    print(f"  📝 更新记录: {stats['updated']} 条")
    
    return stats


def rebuild_song_usage_from_schedule(dry_run: bool = False) -> int:
    """
    从schedule_master.json重建song_usage.csv
    
    Returns:
        更新的歌曲数量
    """
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在")
        return 0
    
    # 读取song_library.csv建立标题到路径的映射
    library_path = REPO_ROOT / "data" / "song_library.csv"
    if not library_path.exists():
        print("⚠️  song_library.csv不存在，跳过歌曲使用记录重建")
        return 0
    
    title_to_path: Dict[str, str] = {}
    with library_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("title", "").strip()
            file_path = row.get("file_path", "").strip()
            if title and file_path:
                title_to_path[title] = file_path
    
    # 从排播表获取所有使用的歌曲
    all_used_tracks = schedule.get_all_used_tracks(include_pending=True)
    
    # 读取现有song_usage.csv
    usage_path = REPO_ROOT / "data" / "song_usage.csv"
    records: Dict[str, Dict] = {}
    
    if usage_path.exists():
        with usage_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_path = row.get("file_path", "")
                if file_path:
                    records[file_path] = row
    
    # 更新使用记录
    updated_count = 0
    now = datetime.now().isoformat()
    
    for track_title in all_used_tracks:
        file_path = title_to_path.get(track_title)
        if not file_path:
            continue
        
        if file_path in records:
            # 更新现有记录
            records[file_path]["last_used_date"] = now
            times_used = int(records[file_path].get("use_count", "0") or "0")
            records[file_path]["use_count"] = str(times_used + 1)
            updated_count += 1
        else:
            # 创建新记录（简化版，只标记使用）
            records[file_path] = {
                "file_path": file_path,
                "title": track_title,
                "last_used_date": now,
                "use_count": "1",
            }
            updated_count += 1
    
    # 保存
    if not dry_run and updated_count > 0:
        with usage_path.open("w", encoding="utf-8", newline="") as f:
            if records:
                fieldnames = list(records[list(records.keys())[0]].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for record in records.values():
                    writer.writerow(record)
    
    print(f"\n📊 歌曲使用记录重建：")
    print(f"  ✅ 更新记录: {updated_count} 首")
    
    return updated_count


def main():
    parser = argparse.ArgumentParser(
        description="统一状态同步工具（从文件系统重建所有状态）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检查状态（不修改）
  python scripts/local_picker/unified_sync.py
  
  # 同步所有状态（从文件系统重建）
  python scripts/local_picker/unified_sync.py --sync
  
  # 预览模式
  python scripts/local_picker/unified_sync.py --sync --dry-run
        """
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="执行同步（从文件系统重建状态）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际修改文件"
    )
    parser.add_argument(
        "--schedule-only",
        action="store_true",
        help="只同步排播表状态"
    )
    parser.add_argument(
        "--production-log-only",
        action="store_true",
        help="只重建生产日志"
    )
    parser.add_argument(
        "--song-usage-only",
        action="store_true",
        help="只重建歌曲使用记录"
    )
    
    args = parser.parse_args()
    
    if not args.sync:
        print("💡 使用 --sync 参数以执行同步")
        print("   使用 --dry-run 预览模式")
        return
    
    print("=" * 70)
    print("🔄 统一状态同步工具")
    print("=" * 70)
    print("原则：文件系统为真相来源")
    if args.dry_run:
        print("⚠️  预览模式（不会实际修改文件）")
    print("=" * 70)
    
    if args.schedule_only or (not args.production_log_only and not args.song_usage_only):
        print("\n📋 同步排播表状态...")
        sync_schedule_from_filesystem(args.dry_run)
    
    if args.production_log_only or (not args.schedule_only and not args.song_usage_only):
        print("\n📊 重建生产日志...")
        rebuild_production_log_from_filesystem(args.dry_run)
    
    if args.song_usage_only or (not args.schedule_only and not args.production_log_only):
        print("\n🎵 重建歌曲使用记录...")
        rebuild_song_usage_from_schedule(args.dry_run)
    
    print("\n" + "=" * 70)
    if args.dry_run:
        print("💡 这是预览模式，未实际修改")
        print("   运行不带 --dry-run 的参数以执行实际同步")
    else:
        print("✅ 状态同步完成")
    print("=" * 70)


if __name__ == "__main__":
    main()

