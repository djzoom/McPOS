#!/usr/bin/env python3
# coding: utf-8
"""
排播表状态监视脚本

功能：
1. 监视output目录中新生成的期数文件夹
2. 自动检测视频文件是否已生成
3. 更新排播表状态为 completed
4. 支持单次扫描或持续监视模式

用法：
    # 单次扫描
    python scripts/local_picker/watch_schedule_status.py

    # 持续监视（每10秒扫描一次）
    python scripts/local_picker/watch_schedule_status.py --watch --interval 10
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
import time
from pathlib import Path
from typing import List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from schedule_master import ScheduleMaster
    from episode_status import STATUS_已完成, STATUS_制作中, is_completed_status, normalize_status
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    print("[WARN] 无法导入 schedule_master，无法更新排播表状态")
    sys.exit(1)


def extract_episode_id_from_path(output_path: Path) -> Optional[str]:
    """
    从输出路径中提取期数ID
    
    支持的格式：
    - output/20251101_Title/
    - output/20251101_123456_Title/
    
    返回：
    - 如果是YYYYMMDD格式，返回YYYYMMDD
    """
    folder_name = output_path.name
    
    # 尝试提取YYYYMMDD格式
    match = re.match(r'^(\d{8})', folder_name)
    if match:
        return match.group(1)
    
    return None


def check_episode_complete(episode_dir: Path) -> bool:
    """
    检查期数文件夹是否已包含完整的视频文件
    
    检查文件：
    - *_youtube.mp4 或 *.mp4（视频文件）
    - *_cover.png（封面）
    - *_full_mix.mp3（混音）
    - *_description.txt（描述，可选）
    """
    video_files = list(episode_dir.glob("*_youtube.mp4"))
    if not video_files:
        # 回退：查找任何mp4文件
        video_files = list(episode_dir.glob("*.mp4"))
    
    cover_files = list(episode_dir.glob("*_cover.png"))
    audio_files = list(episode_dir.glob("*_full_mix.mp3"))
    
    # 至少需要视频和音频文件
    has_video = len(video_files) > 0
    has_audio = len(audio_files) > 0
    
    return has_video and has_audio


def scan_and_update(output_dir: Path, schedule: ScheduleMaster) -> int:
    """
    扫描output目录，更新排播表状态
    
    返回：更新的期数数量
    """
    if not output_dir.exists():
        print(f"⚠️  输出目录不存在: {output_dir}")
        return 0
    
    updated_count = 0
    
    # 查找所有期数文件夹（格式：YYYY-MM-DD_Title）
    episode_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
    
    for episode_dir in episode_dirs:
        episode_id = extract_episode_id_from_path(episode_dir)
        
        if not episode_id:
            continue  # 跳过不匹配的文件夹
        
        # 检查排播表中是否存在该期数
        ep = schedule.get_episode(episode_id)
        if not ep:
            continue  # 排播表中没有此期数
        
        # 检查状态是否已完成
        if is_completed_status(ep.get("status", "")):
            continue  # 已经完成，跳过
        
        # 检查文件夹是否包含完整文件
        if check_episode_complete(episode_dir):
            # 更新状态为已完成（视频已生成，视为已完成）
            success = schedule.update_episode(
                episode_id=episode_id,
                status=STATUS_已完成
            )
            
            if success:
                schedule.save()
                print(f"✅ 更新期数状态: {episode_id} -> {STATUS_已完成} (文件夹: {episode_dir.name})")
                updated_count += 1
                
                # 自动同步图片使用标记
                try:
                    images_synced = schedule.sync_images_from_assignments()
                    schedule.save()
                    if images_synced != 0:
                        print(f"✅ 图片使用标记已自动同步（{images_synced:+d} 张）")
                    else:
                        print(f"✅ 图片使用标记已是最新状态")
                except Exception as e:
                    print(f"⚠️  同步图片标记失败: {e}")
            else:
                print(f"⚠️  更新期数状态失败: {episode_id}")
    
    return updated_count


def main():
    parser = argparse.ArgumentParser(description="监视排播表状态并自动更新")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="持续监视模式（默认：单次扫描）"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="监视间隔（秒，默认：10）"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output",
        help="输出目录（默认：output/）"
    )
    
    args = parser.parse_args()
    
    if not SCHEDULE_AVAILABLE:
        print("❌ 无法加载排播表模块")
        sys.exit(1)
    
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在。请先创建排播表。")
        sys.exit(1)
    
    print("=" * 70)
    print("📋 排播表状态监视")
    print("=" * 70)
    print(f"输出目录: {args.output_dir}")
    print(f"排播表期数: {schedule.total_episodes}")
    print(f"模式: {'持续监视' if args.watch else '单次扫描'}")
    if args.watch:
        print(f"扫描间隔: {args.interval} 秒")
    print("=" * 70)
    print()
    
    if args.watch:
        # 持续监视模式
        print("🔍 开始持续监视（按 Ctrl+C 停止）...")
        print()
        
        try:
            while True:
                updated = scan_and_update(args.output_dir, schedule)
                if updated > 0:
                    print(f"\n📊 本次扫描更新了 {updated} 期状态")
                else:
                    print(".", end="", flush=True)  # 无更新时显示进度点
                
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\n✅ 监视已停止")
    else:
        # 单次扫描模式
        print("🔍 开始单次扫描...")
        updated = scan_and_update(args.output_dir, schedule)
        
        print()
        print("=" * 70)
        if updated > 0:
            print(f"✅ 扫描完成，更新了 {updated} 期状态")
        else:
            print("✅ 扫描完成，无需更新")
        print("=" * 70)


if __name__ == "__main__":
    main()

