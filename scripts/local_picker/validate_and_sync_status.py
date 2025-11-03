#!/usr/bin/env python3
# coding: utf-8
"""
验证并同步排播表状态

功能：
1. 精确检查每个期数文件夹是否包含完整的上传所需文件
2. 根据实际文件状态修正排播表状态
3. 同步资源标记（图片、歌曲）到正确状态
4. 支持DEMO和正式模式的混合检查

核心原则：
- 只有文件完整时才标记为"已完成"
- 只有"已完成"的期数才标记资源为已使用
- 确保排播表、文件系统、资源标记三者一致
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from schedule_master import ScheduleMaster
    from episode_status import (
        STATUS_待制作,
        STATUS_已完成,
        normalize_status,
        is_completed_status,
    )
    SCHEDULE_AVAILABLE = True
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    sys.exit(1)


# 上传所需文件清单（按优先级）
REQUIRED_FILES = {
    "必需": [
        ("cover", "*_cover.png", "封面图片"),
        ("playlist", "*_playlist.csv", "歌单文件"),
        ("full_mix", "*_full_mix.mp3", "完整混音音频"),
    ],
    "YouTube上传": [
        ("srt", "*_youtube.srt", "SRT字幕文件"),
        ("title", "*_youtube_title.txt", "YouTube标题"),
        ("desc", "*_youtube_description.txt", "YouTube描述"),
        ("video", "*_youtube.mp4", "YouTube视频文件"),
    ],
}


def extract_episode_id_from_folder(folder_path: Path) -> Optional[str]:
    """
    从文件夹名提取期数ID
    
    支持格式：
    - YYYY-MM-DD_Title -> YYYYMMDD
    - YYYYMMDD_Title -> YYYYMMDD
    - 2025-11-01_Title -> 20251101
    """
    folder_name = folder_path.name
    
    # 格式1: YYYY-MM-DD_Title
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})_", folder_name)
    if match:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}"
    
    # 格式2: YYYYMMDD_Title
    match = re.match(r"^(\d{8})", folder_name)
    if match:
        return match.group(1)
    
    return None


def check_episode_files_complete(episode_dir: Path, id_str: str) -> Tuple[bool, Dict[str, List[str]]]:
    """
    检查期数文件夹是否包含完整的上传所需文件
    
    Returns:
        (是否完整, {缺失类型: [缺失文件描述]})
    """
    missing = {
        "必需": [],
        "YouTube上传": [],
    }
    
    # 检查必需文件
    for key, pattern, desc in REQUIRED_FILES["必需"]:
        # 尝试多种可能的命名
        found = False
        if key == "full_mix":
            # full_mix可能有两种命名
            v1 = episode_dir / f"{id_str}_full_mix.mp3"
            v2 = episode_dir / f"{id_str}_playlist_full_mix.mp3"
            if v1.exists() or v2.exists():
                found = True
        else:
            files = list(episode_dir.glob(pattern.replace("*", id_str)))
            if files:
                found = True
        
        if not found:
            missing["必需"].append(desc)
    
    # 检查YouTube上传文件
    for key, pattern, desc in REQUIRED_FILES["YouTube上传"]:
        files = list(episode_dir.glob(pattern.replace("*", id_str)))
        if not files:
            missing["YouTube上传"].append(desc)
    
    # 完整 = 必需文件齐全 + YouTube上传文件齐全
    is_complete = len(missing["必需"]) == 0 and len(missing["YouTube上传"]) == 0
    
    return is_complete, missing


def find_episode_folders(output_base: Path) -> Dict[str, Path]:
    """
    查找所有期数文件夹
    
    Returns:
        {episode_id: folder_path}
    """
    episode_folders = {}
    
    # 检查 output/ 根目录下的文件夹
    if output_base.exists():
        for folder in output_base.iterdir():
            if folder.is_dir():
                ep_id = extract_episode_id_from_folder(folder)
                if ep_id:
                        episode_folders[ep_id] = folder
    
    return episode_folders


def validate_and_sync(schedule: ScheduleMaster, fix: bool = False, dry_run: bool = False) -> Dict:
    """
    验证并同步排播表状态
    
    Returns:
        统计信息
    """
    output_base = REPO_ROOT / "output"
    
    # 1. 查找所有期数文件夹
    episode_folders = find_episode_folders(output_base)
    
    print(f"📁 找到 {len(episode_folders)} 个期数文件夹")
    
    # 2. 检查每个期数的文件完整性
    stats = {
        "total_episodes": len(schedule.episodes),
        "checked_folders": len(episode_folders),
        "status_correct": 0,
        "status_incorrect": 0,
        "should_be_completed": [],
        "should_not_be_completed": [],
        "missing_files": {},
    }
    
    print("\n" + "=" * 70)
    print("🔍 检查期数文件完整性...")
    print("=" * 70)
    
    for ep in schedule.episodes:
        ep_id = ep.get("episode_id")
        current_status = normalize_status(ep.get("status", ""))
        is_completed = is_completed_status(current_status)
        
        # 查找对应的文件夹
        folder_path = episode_folders.get(ep_id)
        
        if folder_path:
            # 检查文件完整性
            is_complete, missing = check_episode_files_complete(folder_path, ep_id)
            
            if is_complete:
                # 文件完整
                if not is_completed:
                    # 状态应该是"已完成"但当前不是
                    stats["should_be_completed"].append({
                        "id": ep_id,
                        "title": ep.get("title", ""),
                        "current_status": current_status,
                        "folder": folder_path.name,
                    })
                    stats["status_incorrect"] += 1
                    
                    if fix and not dry_run:
                        schedule.update_episode(ep_id, status=STATUS_已完成)
                        schedule.save()
                        print(f"  ✅ 修正状态: {ep_id} -> {STATUS_已完成} (文件完整)")
                else:
                    stats["status_correct"] += 1
                    print(f"  ✓ {ep_id}: 状态正确（已完成）")
            else:
                # 文件不完整
                if is_completed:
                    # 状态标记为"已完成"但文件不完整
                    stats["should_not_be_completed"].append({
                        "id": ep_id,
                        "title": ep.get("title", ""),
                        "current_status": current_status,
                        "folder": folder_path.name,
                        "missing": missing,
                    })
                    stats["status_incorrect"] += 1
                    
                    if fix and not dry_run:
                        schedule.update_episode(ep_id, status=STATUS_待制作)
                        schedule.save()
                        print(f"  ⚠️  修正状态: {ep_id} -> {STATUS_待制作} (文件不完整)")
                else:
                    stats["status_correct"] += 1
                
                stats["missing_files"][ep_id] = {
                    "title": ep.get("title", ""),
                    "folder": folder_path.name,
                    "missing": missing,
                }
        else:
            # 没有找到文件夹
            if is_completed:
                # 状态标记为"已完成"但没有文件夹
                stats["should_not_be_completed"].append({
                    "id": ep_id,
                    "title": ep.get("title", ""),
                    "current_status": current_status,
                    "folder": "未找到",
                    "missing": {"必需": ["所有文件"], "YouTube上传": ["所有文件"]},
                })
                stats["status_incorrect"] += 1
                
                if fix and not dry_run:
                    schedule.update_episode(ep_id, status=STATUS_待制作)
                    schedule.save()
                    print(f"  ⚠️  修正状态: {ep_id} -> {STATUS_待制作} (文件夹不存在)")
    
    # 3. 同步资源标记（只有"已完成"且文件完整的期数才标记资源）
    if fix and not dry_run:
        print("\n" + "=" * 70)
        print("🔄 同步图片使用标记...")
        print("=" * 70)
        
        try:
            images_synced = schedule.sync_images_from_assignments()
            schedule.save()
            print(f"  ✅ 图片标记: {images_synced:+d} 张")
            # 在新架构中，歌曲使用从排播表动态查询，不需要单独的CSV文件
        except Exception as e:
            print(f"  ⚠️  同步图片标记失败: {e}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="验证并同步排播表状态",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检查状态（不修改）
  python scripts/local_picker/validate_and_sync_status.py
  
  # 检查并自动修正状态
  python scripts/local_picker/validate_and_sync_status.py --fix
  
  # 预览修正（不实际修改）
  python scripts/local_picker/validate_and_sync_status.py --fix --dry-run
        """
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="自动修正不正确的状态"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际修改文件"
    )
    
    args = parser.parse_args()
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在，请先创建排播表")
        sys.exit(1)
    
    print("=" * 70)
    print("📋 验证并同步排播表状态")
    print("=" * 70)
    print(f"总期数: {schedule.total_episodes}")
    print(f"模式: {'修正模式' if args.fix else '检查模式'}")
    if args.dry_run:
        print("⚠️  预览模式（不会实际修改文件）")
    print("=" * 70)
    
    # 执行验证和同步
    stats = validate_and_sync(schedule, fix=args.fix, dry_run=args.dry_run)
    
    # 显示结果
    print("\n" + "=" * 70)
    print("📊 验证结果")
    print("=" * 70)
    print(f"总期数: {stats['total_episodes']}")
    print(f"找到文件夹: {stats['checked_folders']}")
    print(f"状态正确: {stats['status_correct']}")
    print(f"状态不正确: {stats['status_incorrect']}")
    
    if stats["should_be_completed"]:
        print(f"\n⚠️  应该标记为'已完成'但当前不是（{len(stats['should_be_completed'])} 期）:")
        for item in stats["should_be_completed"]:
            print(f"  • {item['id']}: {item['title']} (当前: {item['current_status']})")
    
    if stats["should_not_be_completed"]:
        print(f"\n❌ 标记为'已完成'但文件不完整（{len(stats['should_not_be_completed'])} 期）:")
        for item in stats["should_not_be_completed"]:
            print(f"  • {item['id']}: {item['title']} (文件夹: {item['folder']})")
            if "missing" in item:
                for category, files in item["missing"].items():
                    if files:
                        print(f"    缺失{category}: {', '.join(files)}")
    
    if stats["missing_files"]:
        print(f"\n📝 文件不完整的期数（{len(stats['missing_files'])} 期）:")
        for ep_id, info in list(stats["missing_files"].items())[:10]:  # 只显示前10个
            print(f"  • {ep_id}: {info['title']}")
            for category, files in info["missing"].items():
                if files:
                    print(f"    缺失{category}: {', '.join(files)}")
        if len(stats["missing_files"]) > 10:
            print(f"  ... 还有 {len(stats['missing_files']) - 10} 期文件不完整")
    
    print("\n" + "=" * 70)
    if args.fix:
        if args.dry_run:
            print("💡 这是预览模式，未实际修改")
            print("   运行不带 --dry-run 的参数以执行实际修正")
        else:
            print("✅ 状态已修正并同步资源标记")
    else:
        print("💡 运行 --fix 参数以自动修正不正确的状态")
    print("=" * 70)


if __name__ == "__main__":
    main()

