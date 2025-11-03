#!/usr/bin/env python3
# coding: utf-8
"""
查看排播表信息

用法：
    python scripts/local_picker/show_schedule.py
    python scripts/local_picker/show_schedule.py --pending  # 只看pending的
    python scripts/local_picker/show_schedule.py --id 20251101  # 查看指定ID的详情
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from schedule_master import ScheduleMaster
    from episode_status import (
        STATUS_待制作,
        STATUS_制作中,
        STATUS_上传中,
        STATUS_排播完毕待播出,
        STATUS_已完成,
        STATUS_已跳过,
        normalize_status,
        is_pending_status,
        get_status_display,
    )
except ImportError:
    print("❌ 无法导入 schedule_master")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="查看排播表信息")
    parser.add_argument(
        "--pending",
        action="store_true",
        help="只显示pending状态的期数"
    )
    parser.add_argument(
        "--id",
        type=str,
        help="查看指定ID的详细信息"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="显示数量限制（默认20）"
    )
    
    args = parser.parse_args()
    
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在！")
        print("   请先创建：python scripts/local_picker/create_schedule_master.py --episodes 100")
        sys.exit(1)
    
    print("=" * 70)
    print("📋 排播表信息")
    print("=" * 70)
    print(f"总期数：{schedule.total_episodes}")
    
    # 计算结束日期（最后一个episode的日期）
    end_date = schedule.start_date
    if schedule.episodes:
        last_ep = schedule.episodes[-1]
        end_date = last_ep.get("schedule_date", schedule.start_date)
    
    print(f"起始日期：{schedule.start_date}")
    print(f"结束日期：{end_date}")
    print(f"排播间隔：{schedule.schedule_interval_days} 天")
    
    # 检查剩余图片（显示剩余可用图片）
    remaining, _ = schedule.check_remaining_images()
    print(f"剩余可用图片：{remaining} 张")
    
    # 统计（使用规范化状态）
    status_counts = {}
    for ep in schedule.episodes:
        status = normalize_status(ep.get("status", STATUS_待制作))
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"\n状态统计：")
    print(f"  已完成：{status_counts.get(STATUS_已完成, 0)} 期")
    print(f"  制作中：{status_counts.get(STATUS_制作中, 0)} 期")
    print(f"  上传中：{status_counts.get(STATUS_上传中, 0)} 期")
    print(f"  排播完毕待播出：{status_counts.get(STATUS_排播完毕待播出, 0)} 期")
    print(f"  待制作：{status_counts.get(STATUS_待制作, 0)} 期")
    print(f"  已跳过：{status_counts.get(STATUS_已跳过, 0)} 期")
    if remaining < 10:
        print(f"  ⚠️  警告：剩余图片不足10张！")
    
    # 查看指定ID
    if args.id:
        ep = schedule.get_episode(args.id)
        if not ep:
            print(f"\n❌ ID {args.id} 不存在")
            sys.exit(1)
        
        print(f"\n{'='*70}")
        print(f"📺 期数详情：{args.id}")
        print(f"{'='*70}")
        print(f"期数：第 {ep['episode_number']} 期")
        print(f"排播日期：{ep['schedule_date']}")
        print(f"状态：{get_status_display(ep.get('status', STATUS_待制作))}")
        print(f"图片：{Path(ep.get('image_path', '')).name if ep.get('image_path') else '未分配'}")
        if ep.get('dominant_color_hex'):
            print(f"背景色：#{ep['dominant_color_hex']}")
        if ep.get('title'):
            print(f"标题：{ep['title']}")
        if ep.get('starting_track'):
            print(f"起始曲目：{ep['starting_track']}")
        
        # 显示所有曲目
        tracks_used = ep.get('tracks_used', [])
        if tracks_used:
            print(f"\n📀 曲目列表（共 {len(tracks_used)} 首）：")
            print("-" * 70)
            # 显示起始曲目标记
            starting_track = ep.get('starting_track')
            for i, track in enumerate(tracks_used, 1):
                marker = "🎵" if track == starting_track else "  "
                print(f"{marker} {i:2d}. {track}")
        else:
            print(f"\n📀 曲目列表：未生成")
        
        sys.exit(0)
    
    # 显示期数列表
    print(f"\n{'='*70}")
    if args.pending:
        print(f"📋 待处理期数（前 {args.limit} 个）：")
        episodes = [ep for ep in schedule.episodes if is_pending_status(ep.get("status", STATUS_待制作))][:args.limit]
    else:
        print(f"📋 所有期数（前 {args.limit} 个）：")
        episodes = schedule.episodes[:args.limit]
    
    # 动态计算标题列宽度（至少40，根据最长标题调整）
    max_title_len = max((len(ep.get("title", "") or "") for ep in episodes), default=0)
    title_width = max(40, min(50, max_title_len + 2))  # 最小40，最大50，为起始曲目留空间
    
    # 计算起始曲目列宽度
    max_starting_len = max((len(ep.get("starting_track", "") or "") for ep in episodes), default=0)
    starting_width = max(30, min(40, max_starting_len + 2))  # 最小30，最大40
    
    print(f"{'='*100}")
    print(f"{'ID':<12} {'日期':<12} {'状态':<14} {'标题':<{title_width}} {'起始曲目':<{starting_width}} {'曲目数':<8}")
    print("-" * 100)
    
    for ep in episodes:
        status = get_status_display(ep.get("status", STATUS_待制作))
        title = ep.get("title", "") or "-"  # 完整显示标题，不再截断
        starting_track = ep.get("starting_track", "") or "-"
        tracks_count = len(ep.get('tracks_used', [])) if ep.get('tracks_used') else 0
        tracks_display = f"{tracks_count}首" if tracks_count > 0 else "-"
        print(f"{ep['episode_id']:<12} {ep['schedule_date']:<12} {status:<14} {title:<{title_width}} {starting_track:<{starting_width}} {tracks_display:<8}")
    
    if len(episodes) < len(schedule.episodes):
        print(f"\n... (共 {schedule.total_episodes} 期，显示前 {len(episodes)} 个)")
    
    print(f"\n💡 提示：")
    print(f"  - 生成单期：python scripts/local_picker/create_mixtape.py --episode-id <ID> --font_name Lora-Regular")
    print(f"  - 批量生成：python scripts/local_picker/batch_generate_by_id.py --pending 10")
    print(f"  - 查看详情：python scripts/local_picker/show_schedule.py --id <ID>")


if __name__ == "__main__":
    main()

