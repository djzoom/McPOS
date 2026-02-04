#!/usr/bin/env python3
# coding: utf-8
"""
检查批量制作进度

用法:
    python3 scripts/check_batch_progress.py kat 2026 2
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcpos.models import EpisodeSpec
from mcpos.adapters.filesystem import build_asset_paths, detect_episode_state_from_filesystem
from mcpos.config import get_config
import calendar


def check_batch_progress(channel_id: str, year: int, month: int):
    """检查批量制作进度"""
    _, last_day = calendar.monthrange(year, month)
    
    dates = []
    for day in range(1, last_day + 1):
        date_str = f"{year:04d}{month:02d}{day:02d}"
        dates.append(date_str)
    
    print(f"\n{'='*80}")
    print(f"📊 批量制作进度检查")
    print(f"{'='*80}")
    print(f"   频道: {channel_id}")
    print(f"   月份: {year}年{month}月")
    print(f"   总期数: {len(dates)}")
    print(f"{'='*80}\n")
    
    config = get_config()
    results = {
        "total": len(dates),
        "complete": 0,
        "in_progress": 0,
        "not_started": 0,
        "failed": 0,
    }
    
    episodes = []
    
    for date in dates:
        episode_id = f"{channel_id}_{date}"
        spec = EpisodeSpec(
            channel_id=channel_id,
            date=date,
            episode_id=episode_id,
        )
        
        paths = build_asset_paths(spec, config)
        state = detect_episode_state_from_filesystem(spec, paths)
        
        if state.is_core_complete():
            status = "✅ 已完成"
            results["complete"] += 1
        elif any(state.stage_completed.values()):
            status = "🔄 制作中"
            results["in_progress"] += 1
            # 显示当前阶段
            current_stage = state.current_stage
            if current_stage:
                status += f" ({current_stage.value})"
        else:
            status = "⚪ 未开始"
            results["not_started"] += 1
        
        if state.error_message:
            status += " ❌"
            results["failed"] += 1
        
        episodes.append({
            "date": date,
            "episode_id": episode_id,
            "status": status,
            "state": state,
        })
    
    # 显示详细列表
    print("📋 详细状态:\n")
    for ep in episodes:
        print(f"   {ep['status']} {ep['date']} ({ep['episode_id']})")
    
    # 显示汇总
    print(f"\n{'='*80}")
    print(f"📈 统计信息:")
    print(f"   ✅ 已完成: {results['complete']}/{results['total']} ({results['complete']/results['total']*100:.1f}%)")
    print(f"   🔄 制作中: {results['in_progress']}")
    print(f"   ⚪ 未开始: {results['not_started']}")
    if results['failed'] > 0:
        print(f"   ❌ 失败: {results['failed']}")
    print(f"{'='*80}\n")
    
    # 检查是否有正在运行的进程
    import subprocess
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True,
    )
    batch_processes = [line for line in result.stdout.split('\n') 
                      if 'batch_produce' in line and 'grep' not in line]
    
    if batch_processes:
        print("🔄 批量制作进程正在运行中...\n")
    else:
        print("ℹ️  未发现正在运行的批量制作进程\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="检查批量制作进度")
    parser.add_argument("channel_id", help="频道ID，如 kat")
    parser.add_argument("year", type=int, help="年份，如 2026")
    parser.add_argument("month", type=int, help="月份，如 2")
    
    args = parser.parse_args()
    check_batch_progress(args.channel_id, args.year, args.month)
