#!/usr/bin/env python3
# coding: utf-8
"""
创建永恒排播表

一次性生成所有排播计划，一旦确认就不再变更。

用法：
    python scripts/local_picker/create_schedule_master.py --episodes 100
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from schedule_master import ScheduleMaster

def main():
    parser = argparse.ArgumentParser(description="创建永恒排播表")
    parser.add_argument(
        "--episodes",
        type=int,
        required=True,
        help="总期数（必须小于等于可用图片数量）"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="起始日期（YYYY-MM-DD格式，默认：系统当前日期）"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="排播间隔（天，默认：2）"
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        help="图片目录（默认：assets/design/images）"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已存在的排播表"
    )
    
    args = parser.parse_args()
    
    # 检查是否已存在
    if ScheduleMaster.load() and not args.force:
        print("⚠️  永恒排播表已存在！")
        print("   如需重新创建，请使用 --force 参数")
        sys.exit(1)
    
    # 解析起始日期
    start_date = None
    if args.start_date:
        from datetime import datetime
        start_date = datetime.fromisoformat(args.start_date)
    
    try:
        print(f"正在创建永恒排播表（{args.episodes} 期）...")
        master = ScheduleMaster.create(
            total_episodes=args.episodes,
            start_date=start_date,
            schedule_interval_days=args.interval,
            images_dir=args.images_dir
        )
        # 确保图片使用标记已同步（基于分配）
        images_synced = master.sync_images_from_assignments()
        master.save()
        
        # 注意：新架构以schedule_master.json为单一数据源，不再需要同步到production_log
        # 如果需要重建production_log.json，使用 unified_sync.py
        
        print(f"✅ 永恒排播表创建成功！")
        print(f"   总期数：{args.episodes}")
        print(f"   起始日期：{master.start_date}")
        print(f"   排播间隔：{master.schedule_interval_days} 天")
        print(f"   可用图片：{len(master.images_pool)} 张")
        print(f"   已使用图片：{len(master.images_used)} 张（排播表中分配的图片）")
        from schedule_master import SCHEDULE_MASTER_PATH
        print(f"   保存位置：{SCHEDULE_MASTER_PATH}")
        
        # 显示前5期的信息
        print(f"\n前 5 期预览：")
        for i in range(min(5, len(master.episodes))):
            ep = master.episodes[i]
            print(f"  第 {ep['episode_number']} 期：{ep['schedule_date']} (ID: {ep['episode_id']})")
        
    except ValueError as e:
        print(f"❌ 错误：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 创建失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

