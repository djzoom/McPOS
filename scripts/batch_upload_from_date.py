#!/usr/bin/env python3
# coding: utf-8
"""
批量上传从指定日期开始的视频（统一入口）

本脚本仅作为兼容入口，实际逻辑委托给 scripts/upload_when_ready.py 的
run_upload_range()，以保持单一路径。

用法:
    python3 scripts/batch_upload_from_date.py --start-date 20260208
    python3 scripts/batch_upload_from_date.py --start-date 20260208 --channel kat --max-days 30
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.upload_when_ready import run_upload_range


def main() -> None:
    parser = argparse.ArgumentParser(
        description="批量上传从指定日期开始的视频（统一入口）"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="开始日期 (YYYYMMDD格式，如: 20260208)",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default="kat",
        help="频道ID (默认: kat)",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=365,
        help="最大上传天数 (默认: 365，即一年)",
    )
    parser.add_argument(
        "--upload-interval",
        type=int,
        default=5,
        help="上传间隔（秒）(默认: 5)",
    )
    args = parser.parse_args()

    try:
        start_date = datetime.strptime(args.start_date, "%Y%m%d")
    except ValueError:
        print(f"❌ 错误: 无效的日期格式 '{args.start_date}'，请使用 YYYYMMDD 格式（如: 20260208）")
        sys.exit(1)

    end_date = start_date + timedelta(days=args.max_days)

    exit_code = asyncio.run(
        run_upload_range(
            channel_id=args.channel,
            start_date=start_date,
            end_date=end_date,
            poll_interval=300,
            continue_on_failure=True,
            wait_for_ready=False,
            upload_interval=args.upload_interval,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
