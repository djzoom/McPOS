#!/usr/bin/env python3
# coding: utf-8
"""
检查指定日期范围内的节目制作情况

用法:
    python scripts/check_episode_date_range.py --start-date 20260201 --end-date 20260207
    python scripts/check_episode_date_range.py --start-date 2026-02-01 --end-date 2026-02-07
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcpos.models import EpisodeSpec, StageName
from mcpos.adapters.filesystem import detect_episode_state_from_filesystem, build_asset_paths
from mcpos.config import get_config


def parse_date(date_str: str) -> str:
    """解析日期字符串，支持 YYYYMMDD 和 YYYY-MM-DD 格式"""
    date_str = date_str.strip()
    if len(date_str) == 8:
        # YYYYMMDD 格式
        return date_str
    elif len(date_str) == 10 and date_str.count('-') == 2:
        # YYYY-MM-DD 格式
        return date_str.replace('-', '')
    else:
        raise ValueError(f"不支持的日期格式: {date_str}，请使用 YYYYMMDD 或 YYYY-MM-DD")


def format_date(date_str: str) -> str:
    """格式化日期字符串为 YYYY-MM-DD"""
    if len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str


def get_date_range(start_date: str, end_date: str) -> List[str]:
    """生成日期范围内的所有日期（YYYYMMDD格式）"""
    start = parse_date(start_date)
    end = parse_date(end_date)
    
    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    
    dates = []
    current = start_dt
    while current <= end_dt:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    
    return dates


def get_stage_display_name(stage: StageName | None) -> str:
    """获取阶段的显示名称"""
    if stage is None:
        return "未开始"
    
    stage_names = {
        StageName.INIT: "初始化",
        StageName.TEXT_BASE: "文本生成",
        StageName.COVER: "封面生成",
        StageName.MIX: "混音",
        StageName.TEXT_SRT: "字幕生成",
        StageName.RENDER: "渲染",
    }
    return stage_names.get(stage, str(stage))


def check_episodes_for_date_range(
    channel_id: str,
    start_date: str,
    end_date: str,
) -> Dict[str, Dict]:
    """检查指定日期范围内的所有episode状态"""
    dates = get_date_range(start_date, end_date)
    config = get_config()
    results = {}
    
    for date in dates:
        episode_id = f"{channel_id}_{date}"
        spec = EpisodeSpec(
            channel_id=channel_id,
            date=date,
            episode_id=episode_id,
        )
        
        try:
            state = detect_episode_state_from_filesystem(spec)
            results[episode_id] = {
                "spec": spec,
                "state": state,
                "exists": any(state.stage_completed.values()),
            }
        except Exception as e:
            results[episode_id] = {
                "spec": spec,
                "state": None,
                "exists": False,
                "error": str(e),
            }
    
    return results


def print_status_report(results: Dict[str, Dict], channel_id: str):
    """打印状态报告"""
    print("=" * 80)
    print(f"📊 节目制作情况检查报告 - 频道: {channel_id}")
    print("=" * 80)
    print()
    
    # 统计信息
    total = len(results)
    exists = sum(1 for r in results.values() if r.get("exists", False))
    complete = sum(
        1 for r in results.values()
        if r.get("state") and r["state"].is_core_complete()
    )
    
    print(f"📈 统计信息:")
    print(f"  总日期数: {total}")
    print(f"  已开始制作: {exists}")
    print(f"  已完成制作: {complete}")
    print(f"  未开始: {total - exists}")
    print()
    
    # 详细列表
    print("📋 详细状态:")
    print()
    
    for episode_id, result in sorted(results.items()):
        spec = result["spec"]
        state = result.get("state")
        date_display = format_date(spec.date)
        
        if "error" in result:
            print(f"❌ {date_display} ({episode_id})")
            print(f"   错误: {result['error']}")
            print()
            continue
        
        if not result.get("exists", False):
            print(f"⚪ {date_display} ({episode_id}) - 未开始")
            print()
            continue
        
        # 显示当前阶段
        current_stage = state.current_stage
        stage_display = get_stage_display_name(current_stage)
        
        # 显示完成状态
        completed_stages = [
            stage for stage, completed in state.stage_completed.items()
            if completed
        ]
        completed_count = len(completed_stages)
        total_stages = len(state.stage_completed)
        
        # 判断整体状态
        if state.is_core_complete():
            status_icon = "✅"
            status_text = "已完成"
        elif completed_count > 0:
            status_icon = "🔄"
            status_text = f"制作中 ({completed_count}/{total_stages})"
        else:
            status_icon = "⚪"
            status_text = "已初始化"
        
        print(f"{status_icon} {date_display} ({episode_id}) - {status_text}")
        print(f"   当前阶段: {stage_display}")
        
        # 显示各阶段完成情况
        stage_status = []
        for stage in [StageName.INIT, StageName.TEXT_BASE, StageName.COVER, 
                      StageName.MIX, StageName.TEXT_SRT, StageName.RENDER]:
            completed = state.stage_completed.get(stage, False)
            icon = "✓" if completed else "✗"
            stage_status.append(f"{icon} {get_stage_display_name(stage)}")
        
        print(f"   阶段状态: {' | '.join(stage_status)}")
        
        if state.error_message:
            print(f"   ⚠️  错误: {state.error_message}")
        
        print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="检查指定日期范围内的节目制作情况",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检查 2026年2月1日到7日
  python scripts/check_episode_date_range.py --channel kat --start-date 20260201 --end-date 20260207
  
  # 使用日期格式
  python scripts/check_episode_date_range.py --channel kat --start-date 2026-02-01 --end-date 2026-02-07
        """
    )
    parser.add_argument(
        "--channel",
        default="kat",
        help="频道ID (默认: kat)"
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="开始日期 (格式: YYYYMMDD 或 YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="结束日期 (格式: YYYYMMDD 或 YYYY-MM-DD)"
    )
    
    args = parser.parse_args()
    
    try:
        results = check_episodes_for_date_range(
            channel_id=args.channel,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        print_status_report(results, args.channel)
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
