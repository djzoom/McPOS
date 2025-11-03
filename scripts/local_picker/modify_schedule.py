#!/usr/bin/env python3
# coding: utf-8
"""
修改排播表

功能：
1. 修改起始日期（重新计算所有期数日期）
2. 修改排播间隔（重新计算所有期数日期）
3. 删除指定期数
4. 自动同步资源标记

用法：
    python scripts/local_picker/modify_schedule.py --start-date 2025-11-15
    python scripts/local_picker/modify_schedule.py --interval 3
    python scripts/local_picker/modify_schedule.py --delete-episode 20251101
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster, ScheduleEpisode, STATUS_待制作
    from dataclasses import asdict
    SCHEDULE_AVAILABLE = True
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    SCHEDULE_AVAILABLE = False
    sys.exit(1)


def modify_start_date(schedule: ScheduleMaster, new_start_date: datetime) -> None:
    """修改起始日期，重新计算所有期数日期"""
    old_start = datetime.fromisoformat(schedule.start_date)
    schedule.start_date = new_start_date.strftime("%Y-%m-%d")
    
    # 重新计算所有期数的日期
    for i, ep in enumerate(schedule.episodes):
        schedule_date = new_start_date + timedelta(days=i * schedule.schedule_interval_days)
        ep["schedule_date"] = schedule_date.strftime("%Y-%m-%d")
        ep["episode_id"] = schedule_date.strftime("%Y%m%d")
    
    # 同步图片使用标记（基于分配）
    images_synced = schedule.sync_images_from_assignments()
    
    # 注意：新架构以schedule_master.json为单一数据源，不再需要同步到production_log
    # 如果需要重建production_log.json，使用 unified_sync.py
    
    print(f"✅ 起始日期已修改：{old_start.strftime('%Y-%m-%d')} -> {new_start_date.strftime('%Y-%m-%d')}")
    print(f"   所有 {len(schedule.episodes)} 期的日期已重新计算")
    if images_synced != 0:
        print(f"   图片使用标记已同步：{images_synced:+d} 张")


def modify_interval(schedule: ScheduleMaster, new_interval: int) -> None:
    """修改排播间隔，重新计算所有期数日期"""
    old_interval = schedule.schedule_interval_days
    schedule.schedule_interval_days = new_interval
    
    start_date = datetime.fromisoformat(schedule.start_date)
    
    # 重新计算所有期数的日期
    for i, ep in enumerate(schedule.episodes):
        schedule_date = start_date + timedelta(days=i * new_interval)
        ep["schedule_date"] = schedule_date.strftime("%Y-%m-%d")
        ep["episode_id"] = schedule_date.strftime("%Y%m%d")
    
    # 同步图片使用标记（基于分配）
    images_synced = schedule.sync_images_from_assignments()
    
    # 注意：新架构以schedule_master.json为单一数据源，不再需要同步到production_log
    # 如果需要重建production_log.json，使用 unified_sync.py
    
    print(f"✅ 排播间隔已修改：{old_interval} 天 -> {new_interval} 天")
    print(f"   所有 {len(schedule.episodes)} 期的日期已重新计算")
    if images_synced != 0:
        print(f"   图片使用标记已同步：{images_synced:+d} 张")


def delete_episode(schedule: ScheduleMaster, episode_id: str) -> bool:
    """删除指定期数"""
    ep = schedule.get_episode(episode_id)
    if not ep:
        print(f"❌ 期数 {episode_id} 不存在")
        return False
    
    # 移除该期数
    schedule.episodes = [e for e in schedule.episodes if e.get("episode_id") != episode_id]
    schedule.total_episodes = len(schedule.episodes)
    
    # 重新编号期数
    for i, e in enumerate(schedule.episodes, 1):
        e["episode_number"] = i
    
    # 同步图片使用标记（基于分配，会自动移除已删除期数的图片标记）
    images_synced = schedule.sync_images_from_assignments()
    
    print(f"✅ 期数 {episode_id} 已删除")
    print(f"   剩余期数：{schedule.total_episodes} 期")
    if images_synced != 0:
        print(f"   图片使用标记已同步：{images_synced:+d} 张")
    return True


def main():
    parser = argparse.ArgumentParser(description="修改排播表")
    parser.add_argument(
        "--start-date",
        type=str,
        help="新的起始日期（YYYY-MM-DD格式）"
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="新的排播间隔（天）"
    )
    parser.add_argument(
        "--delete-episode",
        type=str,
        help="删除指定期数ID（YYYYMMDD格式）"
    )
    
    args = parser.parse_args()
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在，请先创建排播表")
        sys.exit(1)
    
    print("=" * 70)
    print("🔧 修改排播表")
    print("=" * 70)
    print(f"当前排播表：")
    print(f"  起始日期：{schedule.start_date}")
    print(f"  结束日期：{schedule.get_end_date()}")
    print(f"  排播间隔：{schedule.schedule_interval_days} 天")
    print(f"  总期数：{schedule.total_episodes} 期")
    print()
    
    modified = False
    
    # 修改起始日期
    if args.start_date:
        try:
            new_start = datetime.fromisoformat(args.start_date)
            modify_start_date(schedule, new_start)
            modified = True
        except ValueError as e:
            print(f"❌ 日期格式错误: {e}")
            sys.exit(1)
    
    # 修改间隔
    if args.interval:
        if args.interval <= 0:
            print("❌ 排播间隔必须大于0")
            sys.exit(1)
        modify_interval(schedule, args.interval)
        modified = True
    
    # 删除期数
    if args.delete_episode:
        if delete_episode(schedule, args.delete_episode):
            modified = True
    
    if not modified:
        print("ℹ️  没有指定任何修改操作")
        print("   用法：")
        print("     --start-date YYYY-MM-DD  修改起始日期")
        print("     --interval N             修改排播间隔（天）")
        print("     --delete-episode ID      删除指定期数")
        sys.exit(0)
    
    # 保存排播表
    schedule.save()
    print("\n✅ 排播表已保存")
    
    # 自动同步图片使用标记（基于分配）
    print("\n🔄 自动同步图片使用标记...")
    try:
        images_synced = schedule.sync_images_from_assignments()
        if images_synced != 0:
            print(f"✅ 图片使用标记已同步（{images_synced:+d} 张）")
        else:
            print(f"✅ 图片使用标记已是最新状态")
    except Exception as e:
        print(f"⚠️  同步图片标记失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ 修改完成")


if __name__ == "__main__":
    main()

