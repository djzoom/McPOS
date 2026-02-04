#!/usr/bin/env python3
# coding: utf-8
"""
批量制作指定月份的所有节目

用法:
    python3 scripts/batch_produce_month.py kat 2026 2
    python3 scripts/batch_produce_month.py kat 2026 2 --skip-completed
    python3 scripts/batch_produce_month.py kat 2026 2 --start-date 5  # 从5号开始
"""
from __future__ import annotations

import sys
import asyncio
from pathlib import Path
from typing import List, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcpos.core.pipeline import run_episode_batch, get_dates_for_month


async def batch_produce_month(
    channel_id: str,
    year: int,
    month: int,
    *,
    skip_completed: bool = True,
    start_date: int = 1,
    max_concurrent: int = 1,  # 默认串行处理，避免资源竞争
) -> List[Dict]:
    """批量制作指定月份的所有节目"""
    dates = get_dates_for_month(year, month, start_date)

    print(f"\n{'='*80}")
    print(f"📅 批量制作节目")
    print(f"{'='*80}")
    print(f"   频道: {channel_id}")
    print(f"   月份: {year}年{month}月")
    print(f"   日期范围: {dates[0]} 到 {dates[-1]}")
    print(f"   总期数: {len(dates)}")
    print(f"   跳过已完成: {skip_completed}")
    print(f"   最大并发数: {max_concurrent}")
    print(f"{'='*80}\n")

    def _progress(result: Dict, index: int, total: int) -> None:
        print(f"\n[{index}/{total}] 处理日期: {result.get('date')}")
        if result["status"] == "skipped":
            print(f"⏭️  跳过: {result['episode_id']} (已完成)")
        elif result["status"] == "success":
            print(f"✅ 完成: {result['episode_id']} (耗时: {result['duration_seconds']:.1f}秒)")
        else:
            print(f"❌ 失败: {result['episode_id']}")
            if "error" in result:
                print(f"   错误: {result['error']}")

    results = await run_episode_batch(
        channel_id=channel_id,
        dates=dates,
        skip_completed=skip_completed,
        max_concurrent=max_concurrent,
        progress_callback=_progress,
    )

    return results


def print_summary(results: List[Dict]):
    """打印汇总信息"""
    print(f"\n{'='*80}")
    print(f"📊 制作汇总")
    print(f"{'='*80}")
    
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] in ["failed", "error"])
    
    print(f"   总计: {total}")
    print(f"   ✅ 成功: {success}")
    print(f"   ⏭️  跳过: {skipped}")
    print(f"   ❌ 失败: {failed}")
    
    if failed > 0:
        print(f"\n失败的节目:")
        for r in results:
            if r["status"] in ["failed", "error"]:
                print(f"   - {r['episode_id']}: {r.get('error', 'Unknown error')}")
    
    # 计算总耗时
    total_duration = sum(r.get("duration_seconds", 0) for r in results)
    print(f"\n   总耗时: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)")
    
    print(f"{'='*80}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="批量制作指定月份的所有节目",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 制作2026年2月的所有节目
  python3 scripts/batch_produce_month.py kat 2026 2
  
  # 跳过已完成的节目
  python3 scripts/batch_produce_month.py kat 2026 2 --skip-completed
  
  # 从5号开始制作
  python3 scripts/batch_produce_month.py kat 2026 2 --start-date 5
  
  # 不跳过已完成的（重新制作）
  python3 scripts/batch_produce_month.py kat 2026 2 --no-skip-completed
        """
    )
    parser.add_argument("channel_id", help="频道ID，如 kat")
    parser.add_argument("year", type=int, help="年份，如 2026")
    parser.add_argument("month", type=int, help="月份，如 2")
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        default=True,
        help="跳过已完成的节目（默认：是）"
    )
    parser.add_argument(
        "--no-skip-completed",
        action="store_false",
        dest="skip_completed",
        help="不跳过已完成的节目（重新制作）"
    )
    parser.add_argument(
        "--start-date",
        type=int,
        default=1,
        help="从第几天开始（默认：1）"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=1,
        help="最大并发数（默认：1，串行处理）"
    )
    
    args = parser.parse_args()
    
    try:
        results = asyncio.run(
            batch_produce_month(
                channel_id=args.channel_id,
                year=args.year,
                month=args.month,
                skip_completed=args.skip_completed,
                start_date=args.start_date,
                max_concurrent=args.max_concurrent,
            )
        )
        print_summary(results)
        
        # 如果有失败的，返回非零退出码
        failed_count = sum(1 for r in results if r["status"] in ["failed", "error"])
        sys.exit(failed_count)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
