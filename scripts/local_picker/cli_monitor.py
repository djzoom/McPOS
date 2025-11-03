#!/usr/bin/env python3
# coding: utf-8
"""
CLI监控命令

实时显示系统状态摘要
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.layout import Layout
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from core.metrics_manager import get_metrics_manager
from core.state_manager import get_state_manager


def create_monitor_dashboard(console: Console) -> Panel:
    """创建监控仪表板"""
    metrics_manager = get_metrics_manager()
    state_manager = get_state_manager()
    
    # 获取指标摘要
    summary = metrics_manager.get_summary(period="24h")
    
    # 获取全局状态
    global_state = {"total_episodes": 0, "pending": 0, "remixing": 0, "rendering": 0, "completed": 0, "error": 0}
    if state_manager:
        schedule = state_manager._load()
        if schedule:
            episodes = schedule.get("episodes", [])
            global_state["total_episodes"] = len(episodes)
            for ep in episodes:
                status = ep.get("status", "pending")
                if status in global_state:
                    global_state[status] += 1
    
    # 获取最近事件
    recent_events = metrics_manager.get_recent_events(limit=5)
    
    # 创建表格
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("指标", style="cyan")
    table.add_column("值", style="white", justify="right")
    
    table.add_row("总期数", str(global_state["total_episodes"]))
    table.add_row("已完成", f"[green]{global_state['completed']}[/green]")
    table.add_row("失败", f"[red]{global_state['error']}[/red]")
    table.add_row("进行中", f"[yellow]{global_state['remixing'] + global_state['rendering']}[/yellow]")
    table.add_row("待制作", str(global_state["pending"]))
    
    if summary.get("success_rate"):
        table.add_row("成功率", f"[green]{summary['success_rate']}%[/green]")
    
    # 阶段统计表格
    stage_table = Table(show_header=True, header_style="bold magenta", title="阶段耗时")
    stage_table.add_column("阶段", style="cyan")
    stage_table.add_column("平均耗时", style="white", justify="right")
    stage_table.add_column("完成", style="green", justify="right")
    stage_table.add_column("失败", style="red", justify="right")
    
    for stage, stats in summary.get("stages", {}).items():
        stage_table.add_row(
            stage,
            f"{stats.get('avg_duration', 0)}s",
            str(stats.get("completed", 0)),
            str(stats.get("failed", 0))
        )
    
    # 最近事件列表
    events_text = "\n".join([
        f"[{event.get('timestamp', '')[:19]}] {event.get('stage', 'unknown')} - {event.get('status', 'unknown')}"
        for event in recent_events
    ]) or "无最近事件"
    
    # 组合面板
    content = f"{table}\n\n{stage_table}\n\n[bold]最近事件:[/bold]\n{events_text}"
    
    return Panel(
        content,
        title="[bold]Kat Records 实时监控[/bold]",
        border_style="cyan"
    )


def main():
    parser = argparse.ArgumentParser(description="CLI监控工具")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="持续监控模式（每5秒刷新）"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="刷新间隔（秒），默认5秒"
    )
    
    args = parser.parse_args()
    
    if not RICH_AVAILABLE:
        print("❌ Rich库未安装")
        print("   请运行: pip install rich")
        sys.exit(1)
    
    console = Console()
    
    if args.watch:
        # 持续监控模式
        console.print("[cyan]启动持续监控模式（按Ctrl+C退出）[/cyan]")
        
        try:
            with Live(create_monitor_dashboard(console), refresh_per_second=1/args.interval, screen=True) as live:
                while True:
                    live.update(create_monitor_dashboard(console))
                    time.sleep(args.interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]监控已停止[/yellow]")
    else:
        # 单次显示
        dashboard = create_monitor_dashboard(console)
        console.print(dashboard)


if __name__ == "__main__":
    main()

