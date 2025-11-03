#!/usr/bin/env python3
# coding: utf-8
"""
KAT REC 工作流程菜单重构方案 - 实现文件

按照新的菜单结构重构终端界面，符合工作流程逻辑
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# 尝试导入rich
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.layout import Layout
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def get_schedule_status_summary() -> Optional[Dict]:
    """获取排播表状态摘要"""
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
        from schedule_master import ScheduleMaster
        from episode_status import (
            STATUS_待制作,
            STATUS_制作中,
            STATUS_已完成,
            normalize_status,
            is_pending_status,
        )
        
        schedule = ScheduleMaster.load()
        if not schedule:
            return None
        
        # 统计各状态数量
        status_counts = {}
        for ep in schedule.episodes:
            status = normalize_status(ep.get("status", STATUS_待制作))
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 获取下一期待制作
        next_pending = schedule.get_next_pending_episode()
        
        # 剩余图片
        remaining, _ = schedule.check_remaining_images()
        
        return {
            "total": schedule.total_episodes,
            "pending": status_counts.get(STATUS_待制作, 0) + status_counts.get(STATUS_待制作, 0),
            "in_progress": status_counts.get(STATUS_制作中, 0),
            "completed": status_counts.get(STATUS_已完成, 0),
            "remaining_images": remaining,
            "next_pending": next_pending,
        }
    except Exception:
        return None


def format_status_bar(status: Optional[Dict]) -> str:
    """格式化状态栏"""
    if not status:
        return "当前排播表: 未创建 | 请先创建排播表"
    
    parts = [
        f"总期数: {status['total']} 期",
        f"待制作: {status['pending']}",
        f"已完成: {status['completed']}",
    ]
    
    if status['remaining_images'] < 10:
        parts.append(f"⚠️  图片仅剩 {status['remaining_images']} 张")
    else:
        parts.append(f"剩余图片: {status['remaining_images']} 张")
    
    if status['next_pending']:
        ep = status['next_pending']
        parts.append(f"下一期: {ep.get('schedule_date', '')} (#{ep.get('episode_id', '')})")
    
    return " | ".join(parts)

