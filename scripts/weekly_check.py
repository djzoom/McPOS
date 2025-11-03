#!/usr/bin/env python3
# coding: utf-8
"""
每周检查脚本：检查是否需要重新测试，并提示用户

此脚本可以：
- 在应用启动时调用
- 通过 cron 定期运行
- 手动运行检查状态
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.weekly_bench import check_and_prompt, load_best_encoder_config

if __name__ == "__main__":
    config = load_best_encoder_config()
    check_and_prompt(config)

