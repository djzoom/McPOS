#!/usr/bin/env python3
# coding: utf-8
"""
KAT Records Studio - 交互式终端界面

美观的命令行工具，支持菜单导航和完整的帮助系统

用法：
    python scripts/kat_terminal.py
    python scripts/kat_terminal.py --help  # 显示帮助
    python scripts/kat_terminal.py help     # 显示帮助（非交互模式）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    # 类型检查时的导入（仅用于类型提示）
    from local_picker.greet_garfield import greet_garfield  # noqa: F401
    from local_picker.schedule_master import ScheduleMaster  # noqa: F401
    from local_picker.episode_status import (  # noqa: F401
        STATUS_待制作,
        STATUS_制作中,
        STATUS_已完成,
        normalize_status,
        is_pending_status,
    )

REPO_ROOT = Path(__file__).resolve().parent.parent

# 尝试导入rich，如果失败则使用简单输出
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.layout import Layout
    from rich.live import Live
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️  建议安装 rich 库以获得更好的界面体验: pip install rich")


class KatTerminal:
    """KAT Records Studio 交互式终端"""
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "uploader"))
        sys.path.insert(0, str(REPO_ROOT / "src"))
    
    def greet_garfield_on_startup(self):
        """启动时向加菲众问好并验证API
        
        如果API未配置或验证失败，引导用户配置，而不是直接退出
        """
        try:
            from greet_garfield import greet_garfield  # type: ignore[import-untyped]
            
            if self.console:
                self.print("[bold cyan]🔔 正在问候加菲众老板...[/bold cyan]")
            else:
                print("🔔 正在问候加菲众老板...")
            
            success, message = greet_garfield()
            
            if success:
                if self.console:
                    self.print(Panel(
                        f"[bold green]✨ {message}[/bold green]\n\n"
                        "[dim]✅ API验证成功，已准备就绪[/dim]",
                        title="[bold cyan]来自AI的问候[/bold cyan]",
                        border_style="green",
                        box=box.ROUNDED
                    ))
                else:
                    print(f"\n✨ {message}")
                    print("✅ API验证成功，已准备就绪\n")
            else:
                # API验证失败，引导用户配置而不是退出
                if self.console:
                    self.print(Panel(
                        f"[bold yellow]{message}[/bold yellow]\n\n"
                        "[bold]⚠️  API未配置或验证失败[/bold]\n\n"
                        "[dim]系统需要API密钥才能正常工作[/dim]\n"
                        "[dim]您是否要现在配置API密钥？[/dim]",
                        title="[bold yellow]🔑 API配置提示[/bold yellow]",
                        border_style="yellow",
                        box=box.ROUNDED
                    ))
                else:
                    print(f"\n{message}")
                    print("\n⚠️  API未配置或验证失败")
                    print("系统需要API密钥才能正常工作")
                
                # 询问用户是否要配置API
                if self.console:
                    from rich.prompt import Confirm
                    should_configure = Confirm.ask("\n是否现在配置API密钥？", default=True)
                else:
                    choice = input("\n是否现在配置API密钥？(Y/n): ").strip().lower()
                    should_configure = choice != 'n'
                
                if should_configure:
                    # 引导用户进入配置菜单
                    if self.console:
                        self.print("\n[cyan]正在打开API配置向导...[/cyan]\n")
                    else:
                        print("\n正在打开API配置向导...\n")
                    
                    # 调用配置向导
                    self._run_api_config_wizard()
                    
                    # 配置完成后，再次尝试问候
                    if self.console:
                        self.print("\n[bold cyan]🔔 重新问候加菲众老板...[/bold cyan]")
                    else:
                        print("\n🔔 重新问候加菲众老板...")
                    
                    success, message = greet_garfield()
                    if success:
                        if self.console:
                            self.print(Panel(
                                f"[bold green]✨ {message}[/bold green]\n\n"
                                "[dim]✅ API配置成功，已准备就绪[/dim]",
                                title="[bold cyan]来自AI的问候[/bold cyan]",
                                border_style="green",
                                box=box.ROUNDED
                            ))
                        else:
                            print(f"\n✨ {message}")
                            print("✅ API配置成功，已准备就绪\n")
                    else:
                        # 配置后仍然失败，提示但允许继续
                        if self.console:
                            self.print(Panel(
                                f"[bold yellow]⚠️  {message}[/bold yellow]\n\n"
                                "[dim]API配置可能不完整，您可以稍后在菜单中配置[/dim]\n"
                                "[dim]或继续使用其他功能[/dim]",
                                title="[bold yellow]⚠️  API验证警告[/bold yellow]",
                                border_style="yellow",
                                box=box.ROUNDED
                            ))
                        else:
                            print(f"\n⚠️  {message}")
                            print("API配置可能不完整，您可以稍后在菜单中配置")
                            print("或继续使用其他功能\n")
                else:
                    # 用户选择不配置，提示但允许继续
                    if self.console:
                        self.print(Panel(
                            "[bold yellow]⚠️  未配置API密钥[/bold yellow]\n\n"
                            "[dim]您可以在主菜单 → 4. 环境配置 → 2. 配置API密钥 中配置[/dim]\n"
                            "[dim]或直接运行: python scripts/local_picker/configure_api.py[/dim]\n\n"
                            "[dim]部分功能可能无法使用[/dim]",
                            title="[bold yellow]💡 提示[/bold yellow]",
                            border_style="yellow",
                            box=box.ROUNDED
                        ))
                    else:
                        print("\n⚠️  未配置API密钥")
                        print("您可以在主菜单 → 4. 环境配置 → 2. 配置API密钥 中配置")
                        print("或直接运行: python scripts/local_picker/configure_api.py")
                        print("\n部分功能可能无法使用\n")
        except ImportError:
            # 模块无法导入，视为严重错误，退出程序
            if self.console:
                self.print(Panel(
                    "[bold red]❌ 无法加载API验证模块[/bold red]\n\n"
                    "[dim]程序无法继续运行，请检查环境配置[/dim]",
                    title="[bold red]🚫 系统错误[/bold red]",
                    border_style="red",
                    box=box.ROUNDED
                ))
            else:
                print("\n❌ 无法加载API验证模块")
                print("程序无法继续运行，请检查环境配置")
            sys.exit(1)
        except Exception as e:
            # 其他异常，也视为严重错误，退出程序
            if self.console:
                self.print(Panel(
                    f"[bold red]❌ API验证功能异常: {e}[/bold red]\n\n"
                    "[dim]程序无法继续运行，请检查环境配置[/dim]",
                    title="[bold red]🚫 系统错误[/bold red]",
                    border_style="red",
                    box=box.ROUNDED
                ))
            else:
                print(f"\n❌ API验证功能异常: {e}")
                print("程序无法继续运行，请检查环境配置")
            sys.exit(1)
    
    def _run_api_config_wizard(self):
        """运行API配置向导"""
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "configure_api.py"),
        ]
        result_code = self.execute_command(cmd, "配置API密钥")
        
        if result_code == 0:
            if self.console:
                self.print("[green]✅ API配置完成[/green]")
            else:
                print("✅ API配置完成")
        else:
            if self.console:
                self.print("[yellow]⚠️  API配置未完成或已取消[/yellow]")
            else:
                print("⚠️  API配置未完成或已取消")
        
        return result_code == 0
    
    def print(self, *args, **kwargs):
        """统一输出方法"""
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)
    
    def show_header(self):
        """显示标题"""
        header_text = """
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║              🎵  KAT Records Studio  🎵                              ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
        """
        if self.console:
            self.print(Panel(header_text.strip(), border_style="cyan", box=box.DOUBLE))
        else:
            print(header_text)
    
    def get_schedule_status_summary(self) -> Optional[Dict]:
        """获取排播表状态摘要"""
        try:
            sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
            from schedule_master import ScheduleMaster  # type: ignore[import-untyped]
            try:
                from episode_status import (  # type: ignore[import-untyped]
                    STATUS_待制作,
                    STATUS_制作中,
                    STATUS_已完成,
                    normalize_status,
                    is_pending_status,
                )
            except ImportError:
                # 兼容旧版本
                STATUS_待制作 = "待制作"
                STATUS_制作中 = "制作中"
                STATUS_已完成 = "已完成"
                def normalize_status(s): return s or "待制作"
                def is_pending_status(s): return normalize_status(s) not in ["已完成", "已跳过"]
            
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
            
            # 计算待制作数量（包括待制作和制作中）
            pending = status_counts.get(STATUS_待制作, 0) + status_counts.get(STATUS_制作中, 0)
            
            return {
                "total": schedule.total_episodes,
                "pending": pending,
                "in_progress": status_counts.get(STATUS_制作中, 0),
                "completed": status_counts.get(STATUS_已完成, 0),
                "remaining_images": remaining,
                "next_pending": next_pending,
            }
        except Exception:
            return None
    
    def show_main_menu(self):
        """显示主菜单（重构版：工作流导向）"""
        # 获取状态摘要
        status = self.get_schedule_status_summary()
        
        # 快速操作（1-3）
        quick_ops = [
            ("1", "📊 查看排播表状态", "总期数、状态统计、下一期信息"),
            ("2", "🎬 快速生成单期", "自动选择下一期或指定ID生成"),
            ("3", "🔍 检查文件状态", "快速检查缺失文件或详细报告"),
        ]
        
        # 工作流管理（4-6）
        workflow_ops = [
            ("4", "📚 资源库管理", "歌库和图片库的管理与维护"),
            ("5", "📅 排播表管理", "创建、修改、查看排播表"),
            ("6", "🎵 内容生成", "单期、批量、广度优先生成"),
        ]
        
        # 系统工具（7-9）
        system_ops = [
            ("7", "⚙️  系统配置与状态", "环境、API、编码器配置"),
            ("8", "📖 帮助文档", "快速参考、完整文档、API指南"),
            ("9", "🌐 Web 控制台", "启动 Web 仪表板（快捷键：w）"),
            ("0", "🚪 退出", "退出程序"),
        ]
        
        if self.console:
            # 使用 Rich 显示分区的菜单
            from rich.layout import Layout
            from rich.text import Text
            
            # 创建分区布局
            layout = Layout()
            
            # 顶部标题
            header = Panel(
                "[bold cyan]KAT REC 工作流程控制台[/bold cyan]",
                border_style="cyan",
                box=box.DOUBLE
            )
            
            # 快速操作区
            quick_table = Table(show_header=False, box=None, padding=(0, 2))
            quick_table.add_column(style="cyan", width=4)
            quick_table.add_column(style="bold cyan", width=30)
            quick_table.add_column(style="dim", width=35)
            
            quick_table.add_row("", "[bold]⚡ 快速操作[/bold]", "")
            for key, name, desc in quick_ops:
                quick_table.add_row(f"  {key}.", name, f"[dim]{desc}[/dim]")
            
            # 工作流管理区
            workflow_table = Table(show_header=False, box=None, padding=(0, 2))
            workflow_table.add_column(style="cyan", width=4)
            workflow_table.add_column(style="bold green", width=30)
            workflow_table.add_column(style="dim", width=35)
            
            workflow_table.add_row("", "[bold]📋 工作流管理[/bold]", "")
            for key, name, desc in workflow_ops:
                workflow_table.add_row(f"  {key}.", name, f"[dim]{desc}[/dim]")
            
            # 系统工具区
            system_table = Table(show_header=False, box=None, padding=(0, 2))
            system_table.add_column(style="cyan", width=4)
            system_table.add_column(style="bold yellow", width=30)
            system_table.add_column(style="dim", width=35)
            
            system_table.add_row("", "[bold]🔧 系统工具[/bold]", "")
            for key, name, desc in system_ops:
                system_table.add_row(f"  {key}.", name, f"[dim]{desc}[/dim]")
            
            # 状态栏
            if status:
                status_text = f"总期数: {status['total']} 期 | 待制作: {status['pending']} | 已完成: {status['completed']}"
                if status['remaining_images'] < 10:
                    status_text += f" | ⚠️  图片仅剩 {status['remaining_images']} 张"
                else:
                    status_text += f" | 剩余图片: {status['remaining_images']} 张"
                if status['next_pending']:
                    ep = status['next_pending']
                    status_text += f" | 下一期: {ep.get('schedule_date', '')} (#{ep.get('episode_id', '')})"
            else:
                status_text = "当前排播表: 未创建 | 请先创建排播表"
            
            status_bar = Panel(
                status_text,
                border_style="dim",
                box=box.SIMPLE
            )
            
            # 组合显示 - 直接打印 Rich 对象，而不是转换为字符串
            self.print(header)
            self.print()
            self.print(quick_table)
            self.print()
            self.print(workflow_table)
            self.print()
            self.print(system_table)
            self.print()
            self.print(status_bar)
        else:
            # 简单文本模式
            print("\n" + "=" * 70)
            print("KAT REC 工作流程控制台")
            print("=" * 70)
            
            print("\n⚡ 快速操作")
            for key, name, desc in quick_ops:
                print(f"  {key}. {name:30} - {desc}")
            
            print("\n📋 工作流管理")
            for key, name, desc in workflow_ops:
                print(f"  {key}. {name:30} - {desc}")
            
            print("\n🔧 系统工具")
            for key, name, desc in system_ops:
                print(f"  {key}. {name:30} - {desc}")
            
            # 状态栏
            if status:
                status_text = f"总期数: {status['total']} 期 | 待制作: {status['pending']} | 已完成: {status['completed']}"
                if status['remaining_images'] < 10:
                    status_text += f" | ⚠️  图片仅剩 {status['remaining_images']} 张"
                else:
                    status_text += f" | 剩余图片: {status['remaining_images']} 张"
                if status['next_pending']:
                    ep = status['next_pending']
                    status_text += f" | 下一期: {ep.get('schedule_date', '')} (#{ep.get('episode_id', '')})"
            else:
                status_text = "当前排播表: 未创建 | 请先创建排播表"
            
            print("\n" + "-" * 70)
            print(status_text)
            print("=" * 70)
    
    def show_schedule_menu(self):
        """排播表管理菜单（完整功能）"""
        menu_items = [
            ("1", "创建/扩展排播表", "创建新排播表或扩展现有排播表"),
            ("2", "查看排播表（完整选项）", "显示排播表状态和详情（支持筛选）"),
            ("3", "修改排播表", "修改起始日期、间隔或删除期数"),
            ("4", "删除排播表", "删除现有排播表"),
            ("5", "检查排播表", "检查排播表完整性和资源一致性"),
            ("6", "监视状态（持续模式）", "持续监视output目录，自动更新状态"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("排播表管理（完整）", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5", "6"], default="0")
        else:
            choice = input("\n请选择操作 [0-6]: ").strip() or "0"
        
        return choice
    
    def show_generate_menu(self):
        """视频生成菜单（完整功能）"""
        menu_items = [
            ("1", "生成单期（完整选项）", "按ID生成单期视频（支持更多参数）"),
            ("2", "批量生成（完整选项）", "批量生成多期视频（支持测试模式等）"),
            ("3", "仅生成封面", "快速生成封面和歌单"),
            ("4", "广度优先生成", "按阶段批量生成所有期数（推荐）"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("视频生成（完整）", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4"], default="0")
        else:
            choice = input("\n请选择操作 [0-4]: ").strip() or "0"
        
        return choice
    
    def show_status_config_menu(self):
        """状态与配置菜单（合并查看状态和环境配置）"""
        menu_items = [
            ("1", "排播表状态", "查看排播表摘要和状态"),
            ("2", "环境状态", "检查环境初始化状态"),
            ("3", "API状态", "检查API配置和连接"),
            ("4", "初始化环境", "首次使用或环境变化时测试编码器"),
            ("5", "配置API密钥", "一次性配置OpenAI、Gemini等API"),
            ("6", "修复SSL证书", "修复macOS SSL证书验证问题"),
            ("7", "测试编码器", "基准测试（手动指定文件）"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("状态与配置", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="0")
        else:
            choice = input("\n请选择操作 [0-7]: ").strip() or "0"
        
        return choice
    
    def show_help_menu(self):
        """帮助文档菜单"""
        menu_items = [
            ("1", "快速参考", "显示常用命令快速参考"),
            ("2", "完整命令辞典", "查看所有可用命令"),
            ("3", "API使用指南", "OpenAI API使用说明"),
            ("4", "API安全指南", "API密钥安全配置"),
            ("5", "文档索引", "列出所有文档"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("帮助文档", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5"], default="0")
        else:
            choice = input("\n请选择操作 [0-5]: ").strip() or "0"
        
        return choice
    
    def show_tools_menu(self):
        """工具与分析菜单"""
        menu_items = [
            ("1", "批量生成（批量处理）", "批量生成多期视频（自动从排播表获取）"),
            ("2", "监视排播表（单次扫描）", "单次扫描output目录，自动更新状态"),
            ("3", "分析排播表", "分析排播表中曲目使用情况和统计信息"),
            ("4", "检查期数文件（详细模式）", "检查期数文件夹文件完整性，显示详细报告"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("工具与分析", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4"], default="0")
        else:
            choice = input("\n请选择操作 [0-4]: ").strip() or "0"
        
        return choice
    
    def _show_submenu(self, title: str, items: list):
        """显示子菜单"""
        if self.console:
            table = Table(title=title, show_header=True, header_style="bold cyan", box=box.ROUNDED)
            table.add_column("选项", style="cyan", width=8)
            table.add_column("功能", style="green", width=25)
            table.add_column("说明", style="white", width=40)
            
            for key, name, desc in items:
                table.add_row(key, name, desc)
            
            self.print(table)
        else:
            print(f"\n{'=' * 70}")
            print(title)
            print("=" * 70)
            for key, name, desc in items:
                print(f"  {key}. {name:25} - {desc}")
            print("=" * 70)
    
    def execute_command(self, cmd: list[str], description: str = ""):
        """执行命令"""
        if description:
            if self.console:
                self.print(f"[cyan]🔧 {description}...[/cyan]")
            else:
                print(f"🔧 {description}...")
            print()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=REPO_ROOT,
                check=False,
            )
            return result.returncode
        except KeyboardInterrupt:
            print("\n\n❌ 已取消")
            return 130
        except Exception as e:
            if self.console:
                self.print(f"[red]❌ 错误: {e}[/red]")
            else:
                print(f"❌ 错误: {e}")
            return 1
    
    def run_interactive(self):
        """运行交互式界面"""
        self.show_header()
        
        # 启动时问候加菲众并验证API
        self.greet_garfield_on_startup()
        
        while True:
            self.print()  # 空行
            self.show_main_menu()
            
            if self.console:
                choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "w", "W"], default="0")
            else:
                choice = input("\n请选择操作 [0-9/w]: ").strip() or "0"
            
            # 支持 'w' 或 'W' 快捷键
            if choice.lower() == "w":
                choice = "9"
            
            if choice == "0":
                if self.console:
                    self.print("[yellow]👋 再见！[/yellow]")
                else:
                    print("👋 再见！")
                break
            
            elif choice == "1":
                # 📊 查看排播表状态（快速操作）
                self._handle_view_schedule_status()
            
            elif choice == "2":
                # 🎬 快速生成单期（快速操作）
                self._handle_quick_generate_episode()
            
            elif choice == "3":
                # 🔍 检查文件状态（快速操作）
                self._handle_check_file_status()
            
            elif choice == "4":
                # 📚 资源库管理（工作流阶段一）
                self._handle_resource_library_menu()
            
            elif choice == "5":
                # 📅 排播表管理（工作流阶段二）
                self._handle_schedule_management_menu()
            
            elif choice == "6":
                # 🎵 内容生成（工作流阶段三至九）
                self._handle_content_generation_menu()
            
            elif choice == "7":
                # ⚙️  系统配置与状态（系统工具）
                self._handle_system_config_menu()
            
            elif choice == "8":
                # 📖 帮助文档（系统工具）
                self._handle_help_documentation_menu()
            
            elif choice == "9":
                # 🌐 Web 控制台（系统工具）
                self._handle_web_console()
            
            # 移除"按Enter继续"，操作完成后自动返回菜单
    
    def _handle_view_schedule_status(self):
        """查看排播表状态（快速操作）- 直接显示摘要"""
        try:
            sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
            from schedule_master import ScheduleMaster  # type: ignore[import-untyped]
            try:
                from episode_status import (  # type: ignore[import-untyped]
                    STATUS_待制作,
                    STATUS_制作中,
                    STATUS_上传中,
                    STATUS_已完成,
                    STATUS_已跳过,
                    normalize_status,
                    is_pending_status,
                    get_status_display,
                )
            except ImportError:
                STATUS_待制作 = "待制作"
                STATUS_制作中 = "制作中"
                STATUS_上传中 = "上传中"
                STATUS_已完成 = "已完成"
                STATUS_已跳过 = "已跳过"
                def normalize_status(s): return s or "待制作"
                def is_pending_status(s): return normalize_status(s) not in ["已完成", "已跳过"]
                def get_status_display(s): return s
            
            schedule = ScheduleMaster.load()
            if not schedule:
                if self.console:
                    self.print(Panel(
                        "[yellow]❌ 排播表不存在！[/yellow]\n\n"
                        "[dim]请先创建排播表：[/dim]\n"
                        "[dim]python scripts/local_picker/create_schedule_master.py --episodes 100[/dim]",
                        title="[bold yellow]⚠️  提示[/bold yellow]",
                        border_style="yellow"
                    ))
                else:
                    print("\n❌ 排播表不存在！")
                    print("请先创建排播表：")
                    print("python scripts/local_picker/create_schedule_master.py --episodes 100")
                return
            
            # 统计各状态
            status_counts = {}
            for ep in schedule.episodes:
                status = normalize_status(ep.get("status", STATUS_待制作))
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # 计算待制作数量
            pending = status_counts.get(STATUS_待制作, 0) + status_counts.get(STATUS_制作中, 0)
            completed = status_counts.get(STATUS_已完成, 0)
            in_progress = status_counts.get(STATUS_制作中, 0)
            uploading = status_counts.get(STATUS_上传中, 0)
            
            # 剩余图片
            remaining, _ = schedule.check_remaining_images()
            
            # 下一期待制作
            next_pending = schedule.get_next_pending_episode()
            
            # 最近5期状态
            recent_episodes = schedule.episodes[-5:]
            
            if self.console:
                from rich.table import Table
                
                # 摘要表格
                summary_table = Table(title="📊 排播表状态摘要", box=box.ROUNDED, show_header=False)
                summary_table.add_column(style="cyan", width=20)
                summary_table.add_column(style="white", width=30)
                
                summary_table.add_row("总期数", f"{schedule.total_episodes} 期")
                summary_table.add_row("起始日期", schedule.start_date)
                summary_table.add_row("排播间隔", f"{schedule.schedule_interval_days} 天")
                summary_table.add_row("剩余图片", f"{remaining} 张" + (" ⚠️" if remaining < 10 else ""))
                
                # 状态统计表格
                status_table = Table(title="📈 状态统计", box=box.ROUNDED, show_header=False)
                status_table.add_column(style="cyan", width=20)
                status_table.add_column(style="white", width=20)
                
                status_table.add_row("✅ 已完成", f"{completed} 期")
                status_table.add_row("⏳ 待制作", f"{status_counts.get(STATUS_待制作, 0)} 期")
                status_table.add_row("🔄 制作中", f"{in_progress} 期")
                if uploading > 0:
                    status_table.add_row("📤 上传中", f"{uploading} 期")
                
                # 下一期信息
                if next_pending:
                    image_path = next_pending.get('image_path', '')
                    image_name = Path(image_path).name if image_path else '未分配'
                    # 如果文件名太长，截断
                    if len(image_name) > 60:
                        image_name = image_name[:57] + "..."
                    next_info = Panel(
                        f"[bold]日期：[/bold] {next_pending.get('schedule_date', '')}\n"
                        f"[bold]ID：[/bold] {next_pending.get('episode_id', '')}\n"
                        f"[bold]图片：[/bold] {image_name}",
                        title="[bold cyan]下一期待制作[/bold cyan]",
                        border_style="cyan"
                    )
                else:
                    next_info = Panel(
                        "[dim]所有期数已完成或已跳过[/dim]",
                        title="[bold cyan]下一期待制作[/bold cyan]",
                        border_style="dim"
                    )
                
                # 最近5期
                recent_table = Table(title="📋 最近5期状态", box=box.ROUNDED, show_header=True)
                recent_table.add_column("ID", style="cyan", width=12, no_wrap=True)
                recent_table.add_column("日期", style="white", width=12, no_wrap=True)
                recent_table.add_column("状态", style="yellow", width=14, no_wrap=True)
                recent_table.add_column("标题", style="green", width=None, max_width=40)
                
                for ep in recent_episodes:
                    status = get_status_display(ep.get("status", STATUS_待制作))
                    title = ep.get("title", "") or "-"
                    recent_table.add_row(
                        ep['episode_id'],
                        ep['schedule_date'],
                        status,
                        title[:28] + "..." if len(title) > 28 else title
                    )
                
                self.print("\n")
                self.print(summary_table)
                self.print("\n")
                self.print(status_table)
                self.print("\n")
                self.print(next_info)
                self.print("\n")
                self.print(recent_table)
            else:
                print("\n" + "=" * 70)
                print("📊 排播表状态摘要")
                print("=" * 70)
                print(f"总期数：{schedule.total_episodes} 期")
                print(f"起始日期：{schedule.start_date}")
                print(f"排播间隔：{schedule.schedule_interval_days} 天")
                print(f"剩余图片：{remaining} 张" + (" ⚠️" if remaining < 10 else ""))
                
                print(f"\n📈 状态统计：")
                print(f"  ✅ 已完成：{completed} 期")
                print(f"  ⏳ 待制作：{status_counts.get(STATUS_待制作, 0)} 期")
                print(f"  🔄 制作中：{in_progress} 期")
                if uploading > 0:
                    print(f"  📤 上传中：{uploading} 期")
                
                if next_pending:
                    print(f"\n下一期待制作：")
                    print(f"  日期：{next_pending.get('schedule_date', '')}")
                    print(f"  ID：{next_pending.get('episode_id', '')}")
                    print(f"  图片：{Path(next_pending.get('image_path', '')).name if next_pending.get('image_path') else '未分配'}")
                
                print(f"\n📋 最近5期状态：")
                for ep in recent_episodes:
                    status = get_status_display(ep.get("status", STATUS_待制作))
                    title = ep.get("title", "") or "-"
                    print(f"  {ep['episode_id']} | {ep['schedule_date']} | {status} | {title[:40]}")
                print("=" * 70)
                
        except Exception as e:
            if self.console:
                self.print(f"[red]❌ 获取排播表状态失败: {e}[/red]")
            else:
                print(f"❌ 获取排播表状态失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_quick_generate_episode(self):
        """快速生成单期（快速操作）- 支持自动选择下一期"""
        try:
            sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
            from schedule_master import ScheduleMaster  # type: ignore[import-untyped]
            
            schedule = ScheduleMaster.load()
            next_pending = None
            if schedule:
                next_pending = schedule.get_next_pending_episode()
            
            if self.console:
                if next_pending:
                    ep_id_default = next_pending.get('episode_id', '')
                    ep_date = next_pending.get('schedule_date', '')
                    
                    self.print(Panel(
                        f"[bold]检测到下一期待制作：[/bold]\n"
                        f"日期：{ep_date}\n"
                        f"ID：{ep_id_default}",
                        title="[bold cyan]📅 下一期信息[/bold cyan]",
                        border_style="cyan"
                    ))
                    
                    use_next = Confirm.ask("是否生成这一期？", default=True)
                    if use_next:
                        ep_id = ep_id_default
                    else:
                        ep_id = Prompt.ask("请输入期数ID (YYYYMMDD格式)", default=ep_id_default)
                else:
                    ep_id = Prompt.ask("请输入期数ID (YYYYMMDD格式)", default="20251101")
            else:
                if next_pending:
                    ep_id_default = next_pending.get('episode_id', '')
                    ep_date = next_pending.get('schedule_date', '')
                    print(f"\n检测到下一期待制作：{ep_date} (ID: {ep_id_default})")
                    use_next = input("是否生成这一期？(Y/n): ").strip().lower() != 'n'
                    if use_next:
                        ep_id = ep_id_default
                    else:
                        ep_id = input(f"请输入期数ID (YYYYMMDD格式) [{ep_id_default}]: ").strip() or ep_id_default
                else:
                    ep_id = input("请输入期数ID (YYYYMMDD格式) [20251101]: ").strip() or "20251101"
            
            # 询问是否跳过某些阶段
            if self.console:
                skip_stages = Prompt.ask(
                    "跳过哪些阶段？（用逗号分隔，例如：4,5 表示跳过视频和打包，留空不跳过）",
                    default=""
                ).strip()
            else:
                skip_stages = input("跳过哪些阶段？（用逗号分隔，例如：4,5，留空不跳过）: ").strip()
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
                "--font_name", "Lora-Regular",
                "--episode-id", ep_id,
            ]
            
            # 添加跳过阶段的参数（如果需要）
            if skip_stages:
                # 这里可以根据需要解析 skip_stages 并添加相应参数
                pass
            
            self.execute_command(cmd, f"快速生成单期（ID: {ep_id}）")
            
        except Exception as e:
            if self.console:
                self.print(f"[red]❌ 生成失败: {e}[/red]")
            else:
                print(f"❌ 生成失败: {e}")
    
    def _handle_check_file_status(self):
        """检查文件状态（快速操作）"""
        if self.console:
            check_type = Prompt.ask(
                "检查类型",
                choices=["1", "2", "3", "4", "0"],
                default="1"
            )
        else:
            print("\n检查类型：")
            print("  1. 快速检查（显示缺失文件）")
            print("  2. 详细检查（显示所有文件状态）")
            print("  3. 检查指定期数")
            print("  4. 批量检查多期")
            print("  0. 返回")
            check_type = input("\n请选择 [1-4, 0]: ").strip() or "0"
        
        if check_type == "0":
            return
        elif check_type == "1":
            # 快速检查
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "check_episode_files.py"),
            ]
            self.execute_command(cmd, "快速检查文件状态")
        elif check_type == "2":
            # 详细检查（check_episode_files.py 默认就会显示详细信息，无需额外参数）
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "check_episode_files.py"),
            ]
            self.execute_command(cmd, "详细检查文件状态")
        elif check_type == "3":
            # 检查指定期数
            if self.console:
                ep_id = Prompt.ask("请输入期数ID (YYYYMMDD格式)")
            else:
                ep_id = input("请输入期数ID (YYYYMMDD格式): ").strip()
            
            if ep_id:
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "local_picker" / "check_episode_files.py"),
                    "--episode-id", ep_id,
                ]
                self.execute_command(cmd, f"检查期数文件（ID: {ep_id}）")
        elif check_type == "4":
            # 批量检查
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "check_episode_files.py"),
            ]
            self.execute_command(cmd, "批量检查所有期数文件")
    
    def _handle_resource_library_menu(self):
        """资源库管理菜单（工作流阶段一）"""
        menu_items = [
            ("1", "生成/更新歌库索引", "扫描音频文件，生成/更新歌库CSV"),
            ("2", "查看歌库统计", "显示歌库总曲目数、使用情况"),
            ("3", "监听模式（自动更新）", "监听文件变更，自动更新索引"),
            ("4", "清理歌库（移除无效记录）", "清理不存在的文件记录"),
            ("5", "查看图片池状态", "显示图片总数、已使用、剩余数量"),
            ("6", "扫描新图片", "扫描图片目录，更新图片池"),
            ("7", "查看图片使用情况", "显示每张图片的使用状态"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("📚 资源库管理", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="0")
        else:
            choice = input("\n请选择操作 [0-7]: ").strip() or "0"
        
        if choice == "0":
            return
        elif choice == "1":
            # 生成/更新歌库索引
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "generate_song_library.py"),
            ]
            self.execute_command(cmd, "生成/更新歌库索引")
        elif choice == "2":
            # 查看歌库统计
            try:
                import csv
                song_lib_path = REPO_ROOT / "data" / "song_library.csv"
                if song_lib_path.exists():
                    with song_lib_path.open("r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                        total = len(rows)
                        used = sum(1 for r in rows if r.get("times_used", "0") != "0" and r.get("times_used", "") != "")
                        
                        if self.console:
                            from rich.table import Table
                            table = Table(title="📊 歌库统计", box=box.ROUNDED)
                            table.add_column("指标", style="cyan")
                            table.add_column("数量", style="green")
                            table.add_row("总曲目数", f"{total} 首")
                            table.add_row("已使用", f"{used} 首")
                            table.add_row("未使用", f"{total - used} 首")
                            self.print(table)
                        else:
                            print(f"\n📊 歌库统计：")
                            print(f"  总曲目数：{total} 首")
                            print(f"  已使用：{used} 首")
                            print(f"  未使用：{total - used} 首")
                else:
                    if self.console:
                        self.print("[yellow]⚠️  歌库文件不存在，请先生成歌库索引[/yellow]")
                    else:
                        print("⚠️  歌库文件不存在，请先生成歌库索引")
            except Exception as e:
                if self.console:
                    self.print(f"[red]❌ 读取歌库统计失败: {e}[/red]")
                else:
                    print(f"❌ 读取歌库统计失败: {e}")
        elif choice == "3":
            # 监听模式
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "generate_song_library.py"),
                "--watch",
            ]
            self.execute_command(cmd, "监听模式（自动更新歌库）")
        elif choice == "4":
            # 清理歌库（通过重新生成实现）
            if self.console:
                confirm = Confirm.ask("确认清理歌库？将移除不存在的文件记录", default=False)
            else:
                confirm = input("确认清理歌库？将移除不存在的文件记录 (y/N): ").strip().lower() == 'y'
            
            if confirm:
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "local_picker" / "generate_song_library.py"),
                ]
                self.execute_command(cmd, "清理歌库（重新扫描）")
        elif choice == "5":
            # 查看图片池状态
            try:
                sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
                from schedule_master import ScheduleMaster  # type: ignore[import-untyped]
                schedule = ScheduleMaster.load()
                if schedule:
                    remaining, unused = schedule.check_remaining_images()
                    total = len(schedule.images_pool)
                    used = len(schedule.images_used)
                    
                    if self.console:
                        from rich.table import Table
                        table = Table(title="🖼️  图片池状态", box=box.ROUNDED)
                        table.add_column("指标", style="cyan")
                        table.add_column("数量", style="green")
                        table.add_row("总图片数", f"{total} 张")
                        table.add_row("已使用", f"{used} 张")
                        table.add_row("剩余可用", f"{remaining} 张" + (" ⚠️" if remaining < 10 else ""))
                        self.print(table)
                    else:
                        print(f"\n🖼️  图片池状态：")
                        print(f"  总图片数：{total} 张")
                        print(f"  已使用：{used} 张")
                        print(f"  剩余可用：{remaining} 张" + (" ⚠️" if remaining < 10 else ""))
                else:
                    if self.console:
                        self.print("[yellow]⚠️  排播表不存在，无法查看图片池状态[/yellow]")
                    else:
                        print("⚠️  排播表不存在，无法查看图片池状态")
            except Exception as e:
                if self.console:
                    self.print(f"[red]❌ 获取图片池状态失败: {e}[/red]")
                else:
                    print(f"❌ 获取图片池状态失败: {e}")
        elif choice == "6":
            # 扫描新图片（通过重新创建排播表或扩展实现，这里提示用户）
            if self.console:
                self.print("[yellow]ℹ️  图片池会在创建或扩展排播表时自动扫描[/yellow]")
                self.print("[dim]如需扫描新图片，请在排播表管理中扩展排播表[/dim]")
            else:
                print("ℹ️  图片池会在创建或扩展排播表时自动扫描")
                print("如需扫描新图片，请在排播表管理中扩展排播表")
        elif choice == "7":
            # 查看图片使用情况
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "analyze_schedule_usage.py"),
            ]
            self.execute_command(cmd, "查看图片使用情况")
    
    def _handle_schedule_management_menu(self):
        """排播表管理菜单（工作流阶段二）- 重构版"""
        menu_items = [
            ("1", "查看排播表（完整信息）", "显示排播表状态和详情（支持筛选）"),
            ("2", "查看指定期数详情", "显示单期的详细信息"),
            ("3", "监视状态（持续模式）", "持续监视output目录，自动更新状态"),
            ("4", "分析排播表统计", "分析排播表中曲目使用情况和统计信息"),
            ("5", "创建新排播表", "创建新排播表或强制重新创建"),
            ("6", "扩展排播表（增加期数）", "在现有排播表基础上增加期数"),
            ("7", "修改排播表（日期/间隔）", "修改起始日期或排播间隔"),
            ("8", "删除指定期数", "删除排播表中的指定期数"),
            ("9", "检查排播表完整性", "检查排播表完整性和资源一致性"),
            ("10", "同步图片使用状态", "同步图片使用标记"),
            ("11", "修复数据一致性", "修复排播表中的数据问题"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("📅 排播表管理", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"], default="0")
        else:
            choice = input("\n请选择操作 [0-11]: ").strip() or "0"
        
        if choice == "0":
            return
        elif choice == "1":
            # 查看排播表（完整信息）
            if self.console:
                pending = Confirm.ask("只显示pending状态？", default=False)
                ep_id = Prompt.ask("显示指定ID详情（留空显示全部）", default="")
            else:
                pending = input("只显示pending状态？(y/N): ").strip().lower() == 'y'
                ep_id = input("显示指定ID详情（留空显示全部）: ").strip()
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "show_schedule.py"),
            ]
            if pending:
                cmd.append("--pending")
            if ep_id:
                cmd.extend(["--id", ep_id])
            
            self.execute_command(cmd, "查看排播表")
        elif choice == "2":
            # 查看指定期数详情
            if self.console:
                ep_id = Prompt.ask("请输入期数ID (YYYYMMDD格式)")
            else:
                ep_id = input("请输入期数ID (YYYYMMDD格式): ").strip()
            
            if ep_id:
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "local_picker" / "show_schedule.py"),
                    "--id", ep_id,
                ]
                self.execute_command(cmd, f"查看期数详情（ID: {ep_id}）")
        elif choice == "3":
            # 监视状态（持续模式）
            if self.console:
                watch = Confirm.ask("持续监视模式？", default=False)
                interval = Prompt.ask("扫描间隔（秒）", default="10")
            else:
                watch = input("持续监视模式？(y/N): ").strip().lower() == 'y'
                interval = input("扫描间隔（秒）[10]: ").strip() or "10"
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "watch_schedule_status.py"),
            ]
            if watch:
                cmd.append("--watch")
            cmd.extend(["--interval", interval])
            
            self.execute_command(cmd, "监视排播表状态")
        elif choice == "4":
            # 分析排播表统计
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "analyze_schedule_usage.py"),
            ]
            self.execute_command(cmd, "分析排播表统计")
        elif choice == "5":
            # 创建新排播表（复用原有逻辑）
            self._handle_create_schedule()
        elif choice == "6":
            # 扩展排播表（复用原有逻辑，从choice=="1"中提取）
            self._handle_extend_schedule()
        elif choice == "7":
            # 修改排播表
            self._handle_modify_schedule()
        elif choice == "8":
            # 删除指定期数（复用modify_schedule的逻辑）
            self._handle_delete_episode()
        elif choice == "9":
            # 检查排播表完整性
            if self.console:
                fix = Confirm.ask("自动修复可修复的问题？", default=False)
            else:
                fix = input("自动修复可修复的问题？(y/N): ").strip().lower() == 'y'
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "check_schedule_health.py"),
            ]
            if fix:
                cmd.append("--fix")
            
            self.execute_command(cmd, "检查排播表完整性")
        elif choice == "10":
            # 同步图片使用状态（基于分配，而非完成状态）
            try:
                sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
                from schedule_master import ScheduleMaster  # type: ignore[import-untyped]
                
                schedule = ScheduleMaster.load()
                if schedule:
                    # 使用 sync_images_from_assignments() 基于分配同步
                    synced = schedule.sync_images_from_assignments()
                    schedule.save()
                    
                    if self.console:
                        if synced > 0:
                            self.print(Panel(
                                f"[green]✅ 已同步图片使用状态[/green]\n"
                                f"   新增标记: {synced} 张（基于排播表中的分配）",
                                title="[bold green]同步完成[/bold green]",
                                border_style="green"
                            ))
                        elif synced < 0:
                            self.print(Panel(
                                f"[yellow]🔄 已同步图片使用状态[/yellow]\n"
                                f"   移除标记: {abs(synced)} 张（已不再分配的图片）",
                                title="[bold yellow]同步完成[/bold yellow]",
                                border_style="yellow"
                            ))
                        else:
                            self.print(Panel(
                                "[dim]图片使用状态已是最新（无需同步）[/dim]",
                                title="[bold dim]同步完成[/bold dim]",
                                border_style="dim"
                            ))
                    else:
                        if synced > 0:
                            print(f"✅ 已同步图片使用状态（新增标记: {synced} 张）")
                        elif synced < 0:
                            print(f"🔄 已同步图片使用状态（移除标记: {abs(synced)} 张）")
                        else:
                            print("✅ 图片使用状态已是最新（无需同步）")
                else:
                    if self.console:
                        self.print("[yellow]⚠️  排播表不存在[/yellow]")
                    else:
                        print("⚠️  排播表不存在")
            except Exception as e:
                if self.console:
                    self.print(f"[red]❌ 同步失败: {e}[/red]")
                else:
                    print(f"❌ 同步失败: {e}")
        elif choice == "11":
            # 修复数据一致性（调用check_schedule_health with --fix）
            if self.console:
                confirm = Confirm.ask("确认修复数据一致性问题？", default=False)
            else:
                confirm = input("确认修复数据一致性问题？(y/N): ").strip().lower() == 'y'
            
            if confirm:
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "local_picker" / "check_schedule_health.py"),
                    "--fix",
                ]
                self.execute_command(cmd, "修复数据一致性")
    
    def _handle_create_schedule(self):
        """创建新排播表"""
        # 复用原有创建排播表的逻辑（从_handle_schedule_menu的choice=="1"提取）
        schedule_path = REPO_ROOT / "config" / "schedule_master.json"
        force = False
        
        if schedule_path.exists():
            if self.console:
                force = Confirm.ask("排播表已存在，是否强制重新创建？", default=False)
            else:
                force = input("排播表已存在，是否强制重新创建？(y/N): ").strip().lower() == 'y'
            
            if not force:
                return
        
        if self.console:
            episodes = Prompt.ask("请输入期数", default="15")
            start_date = Prompt.ask("起始日期 (YYYY-MM-DD)", default="")
            interval = Prompt.ask("排播间隔（天）", default="2")
            yes = Confirm.ask("跳过确认？", default=False)
        else:
            episodes = input("请输入期数 [15]: ").strip() or "15"
            start_date = input("起始日期 (YYYY-MM-DD，留空使用默认): ").strip()
            interval = input("排播间隔（天） [2]: ").strip() or "2"
            yes = input("跳过确认？(y/N): ").strip().lower() == 'y'
        
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "create_schedule_with_confirmation.py"),
            "--episodes", episodes,
            "--interval", interval,
        ]
        if start_date:
            cmd.extend(["--start-date", start_date])
        if yes:
            cmd.append("--yes")
        if force:
            cmd.append("--force")
        
        cmd.append("--generate-content")
        
        self.execute_command(cmd, f"创建排播表并生成完整内容（{episodes}期）")
    
    def _handle_extend_schedule(self):
        """扩展排播表"""
        try:
            sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
            from schedule_master import ScheduleMaster  # type: ignore[import-untyped]
            schedule = ScheduleMaster.load()
            
            if not schedule:
                if self.console:
                    self.print("[yellow]⚠️  排播表不存在，请先创建[/yellow]")
                else:
                    print("⚠️  排播表不存在，请先创建")
                return
            
            if self.console:
                episodes = Prompt.ask("请输入要增加的期数", default="10")
            else:
                episodes = input("请输入要增加的期数 [10]: ").strip() or "10"
            
            try:
                episodes_int = int(episodes)
                if episodes_int <= 0:
                    if self.console:
                        self.print("[red]❌ 期数必须大于0[/red]")
                    else:
                        print("❌ 期数必须大于0")
                    return
            except ValueError:
                if self.console:
                    self.print("[red]❌ 请输入有效的数字[/red]")
                else:
                    print("❌ 请输入有效的数字")
                return
            
            # 扩展排播表
            schedule.extend(episodes_int)
            schedule.save()
            
            if self.console:
                self.print(f"[green]✅ 已扩展排播表，新增 {episodes_int} 期[/green]")
            else:
                print(f"✅ 已扩展排播表，新增 {episodes_int} 期")
            
            # 为新添加的期数生成内容（复用原有逻辑）
            from create_mixtape import load_tracklist  # type: ignore[import-untyped]
            from generate_full_schedule import generate_episode_content  # type: ignore[import-untyped]
            from src.creation_utils import get_dominant_color
            # sync_resources已过时，现在使用schedule.sync_images_from_assignments()
            
            tracklist_path = REPO_ROOT / "data" / "song_library.csv"
            if tracklist_path.exists():
                all_tracks = load_tracklist(tracklist_path)
                new_episodes = schedule.episodes[-episodes_int:]
                
                used_starting_tracks_in_progress = set()
                
                for i, episode in enumerate(new_episodes, 1):
                    print(f"\n[{i}/{len(new_episodes)}] {episode['episode_id']} - {episode['schedule_date']}")
                    
                    all_excluded_starting_tracks = set(schedule.get_used_starting_tracks())
                    all_excluded_starting_tracks.update(used_starting_tracks_in_progress)
                    
                    content = generate_episode_content(
                        episode,
                        schedule,
                        all_tracks,
                        additional_excluded_starting_tracks=all_excluded_starting_tracks
                    )
                    
                    if content:
                        actual_starting_track = None
                        if content.get("side_a") and len(content["side_a"]) > 0:
                            actual_starting_track = content["side_a"][0].title
                            content["starting_track"] = actual_starting_track
                        elif content.get("starting_track"):
                            actual_starting_track = content["starting_track"]
                        
                        if actual_starting_track:
                            used_starting_tracks_in_progress.add(actual_starting_track)
                            print(f"  📝 起始曲目已记录: {actual_starting_track}")
                        
                        # 提取背景色
                        image_path = Path(episode.get("image_path", ""))
                        if image_path.exists():
                            try:
                                dominant_color = get_dominant_color(image_path)
                                episode["dominant_color_rgb"] = dominant_color
                                episode["dominant_color_hex"] = f"{dominant_color[0]:02x}{dominant_color[1]:02x}{dominant_color[2]:02x}"
                                print(f"  🎨 背景色: #{episode['dominant_color_hex']}")
                            except Exception as e:
                                episode["dominant_color_rgb"] = (100, 100, 100)
                                episode["dominant_color_hex"] = "646464"
                        
                        # 更新排播表
                        schedule.update_episode(
                            episode["episode_id"],
                            title=content["title"],
                            tracks_used=[t.title for t in content["side_a"] + content["side_b"]],
                            starting_track=content["starting_track"]
                        )
                        print(f"  ✅ 已更新排播表")
                
                # 保存并自动同步资源标记
                schedule.save()
                print(f"\n🔄 自动同步资源标记...")
                images_synced = schedule.sync_images_from_assignments()
                schedule.save()
                if images_synced != 0:
                    print(f"✅ 图片使用标记已自动同步（{images_synced:+d} 张）")
                else:
                    print(f"✅ 图片使用标记已是最新状态")
        except Exception as e:
            if self.console:
                self.print(f"[red]❌ 扩展排播表失败: {e}[/red]")
            else:
                print(f"❌ 扩展排播表失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_delete_episode(self):
        """删除指定期数"""
        if self.console:
            ep_id = Prompt.ask("请输入要删除的期数ID (YYYYMMDD格式)", default="")
        else:
            ep_id = input("请输入要删除的期数ID (YYYYMMDD格式): ").strip()
        
        if not ep_id:
            return
        
        if self.console:
            confirm = Confirm.ask(f"确认删除期数 {ep_id}？", default=False)
        else:
            confirm = input(f"确认删除期数 {ep_id}？(y/N): ").strip().lower() == 'y'
        
        if confirm:
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "modify_schedule.py"),
                "--delete-episode", ep_id,
            ]
            self.execute_command(cmd, f"删除期数（ID: {ep_id}）")
    
    def _handle_content_generation_menu(self):
        """内容生成菜单（工作流阶段三至九）- 重构版"""
        menu_items = [
            ("1", "生成单期（完整流程）", "按ID生成单期完整内容"),
            ("2", "生成单期（指定阶段）", "生成单期的特定阶段"),
            ("3", "仅生成封面", "快速生成封面和歌单"),
            ("4", "仅生成音频混音", "只生成混音音频文件"),
            ("5", "仅生成视频", "只生成视频文件（需要封面和音频）"),
            ("6", "广度优先生成（推荐）", "按阶段批量生成所有期数"),
            ("7", "批量生成指定期数", "批量生成指定的多个期数"),
            ("8", "批量生成指定日期范围", "生成指定日期范围内的所有期数"),
            ("9", "继续未完成的期数", "继续生成未完成的期数"),
            ("10", "📤 上传到YouTube", "上传视频到YouTube（工作流阶段十）"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("🎵 内容生成", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], default="0")
        else:
            choice = input("\n请选择操作 [0-10]: ").strip() or "0"
        
        if choice == "0":
            return
        elif choice == "1":
            # 生成单期（完整流程）
            if self.console:
                ep_id = Prompt.ask("请输入期数ID (YYYYMMDD格式)", default="20251101")
            else:
                ep_id = input("请输入期数ID (YYYYMMDD格式) [20251101]: ").strip() or "20251101"
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
                "--font_name", "Lora-Regular",
                "--episode-id", ep_id,
            ]
            
            self.execute_command(cmd, f"生成单期（ID: {ep_id}）")
        elif choice == "2":
            # 生成单期（指定阶段）- 提示用户使用广度优先
            if self.console:
                self.print("[yellow]ℹ️  单期指定阶段生成建议使用广度优先生成[/yellow]")
                self.print("[dim]或使用命令行工具直接指定参数[/dim]")
            else:
                print("ℹ️  单期指定阶段生成建议使用广度优先生成")
                print("或使用命令行工具直接指定参数")
        elif choice == "3":
            # 仅生成封面
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
                "--font_name", "Lora-Regular",
                "--no-remix",
                "--no-video",
            ]
            self.execute_command(cmd, "仅生成封面")
        elif choice == "4":
            # 仅生成音频混音
            if self.console:
                playlist_path = Prompt.ask("请输入歌单CSV路径", default="")
            else:
                playlist_path = input("请输入歌单CSV路径: ").strip()
            
            if playlist_path:
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "local_picker" / "remix_mixtape.py"),
                    "--playlist", playlist_path,
                ]
                self.execute_command(cmd, "生成音频混音")
        elif choice == "5":
            # 仅生成视频
            if self.console:
                ep_id = Prompt.ask("请输入期数ID (YYYYMMDD格式)")
            else:
                ep_id = input("请输入期数ID (YYYYMMDD格式): ").strip()
            
            if ep_id:
                # 查找封面和音频，然后生成视频（需要调用create_mixtape但跳过前面步骤）
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
                    "--font_name", "Lora-Regular",
                    "--episode-id", ep_id,
                    "--no-remix",  # 跳过混音（假设已存在）
                ]
                # 注意：这里需要确保封面和音频已存在
                self.execute_command(cmd, f"生成视频（ID: {ep_id}）")
        elif choice == "6":
            # 广度优先生成（推荐）
            if self.console:
                force = Confirm.ask("强制重新生成所有文件？", default=False)
                skip_stages = Prompt.ask(
                    "跳过哪些阶段？（用逗号分隔，例如：4,5，留空不跳过）",
                    default=""
                ).strip()
                no_pause = Confirm.ask("自动运行（不暂停）？", default=True)
            else:
                force = input("强制重新生成所有文件？(y/N): ").strip().lower() == 'y'
                skip_stages = input("跳过哪些阶段？（用逗号分隔，例如：4,5，留空不跳过）: ").strip()
                no_pause = input("自动运行（不暂停）？(Y/n): ").strip().lower() != 'n'
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "breadth_first_generate.py"),
            ]
            if force:
                cmd.append("--force")
            if skip_stages:
                try:
                    stages = [int(s.strip()) for s in skip_stages.split(",") if s.strip()]
                    if stages:
                        cmd.extend(["--skip-stage"] + [str(s) for s in stages])
                except ValueError:
                    if self.console:
                        self.print("[yellow]⚠️  跳过阶段格式无效，将不跳过任何阶段[/yellow]")
                    else:
                        print("⚠️  跳过阶段格式无效，将不跳过任何阶段")
            if no_pause:
                cmd.append("--no-pause")
            
            self.execute_command(cmd, "广度优先生成（所有期数）")
        elif choice == "7":
            # 批量生成指定期数
            if self.console:
                ep_ids = Prompt.ask("请输入期数ID列表（用逗号分隔）", default="")
            else:
                ep_ids = input("请输入期数ID列表（用逗号分隔）: ").strip()
            
            if ep_ids:
                id_list = [id.strip() for id in ep_ids.split(",")]
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "local_picker" / "batch_generate_by_id.py"),
                ]
                cmd.extend(id_list)
                
                self.execute_command(cmd, f"批量生成指定期数（{len(id_list)}期）")
        elif choice == "8":
            # 批量生成指定日期范围
            if self.console:
                start_date = Prompt.ask("起始日期 (YYYY-MM-DD)", default="")
                end_date = Prompt.ask("结束日期 (YYYY-MM-DD)", default="")
            else:
                start_date = input("起始日期 (YYYY-MM-DD): ").strip()
                end_date = input("结束日期 (YYYY-MM-DD): ").strip()
            
            if start_date and end_date:
                # 需要根据日期范围筛选期数，然后调用批量生成
                try:
                    sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
                    from schedule_master import ScheduleMaster  # type: ignore[import-untyped]
                    from datetime import datetime
                    
                    schedule = ScheduleMaster.load()
                    if schedule:
                        start_dt = datetime.fromisoformat(start_date)
                        end_dt = datetime.fromisoformat(end_date)
                        
                        matching_episodes = []
                        for ep in schedule.episodes:
                            ep_date = datetime.fromisoformat(ep['schedule_date'])
                            if start_dt <= ep_date <= end_dt:
                                matching_episodes.append(ep['episode_id'])
                        
                        if matching_episodes:
                            cmd = [
                                sys.executable,
                                str(REPO_ROOT / "scripts" / "local_picker" / "batch_generate_by_id.py"),
                            ]
                            cmd.extend(matching_episodes)
                            
                            self.execute_command(cmd, f"批量生成日期范围（{len(matching_episodes)}期）")
                        else:
                            if self.console:
                                self.print("[yellow]⚠️  该日期范围内没有期数[/yellow]")
                            else:
                                print("⚠️  该日期范围内没有期数")
                    else:
                        if self.console:
                            self.print("[yellow]⚠️  排播表不存在[/yellow]")
                        else:
                            print("⚠️  排播表不存在")
                except Exception as e:
                    if self.console:
                        self.print(f"[red]❌ 处理失败: {e}[/red]")
                    else:
                        print(f"❌ 处理失败: {e}")
        elif choice == "9":
            # 继续未完成的期数
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "batch_generate_by_id.py"),
                "--all",
            ]
            self.execute_command(cmd, "继续未完成的期数")
        elif choice == "10":
            # 上传到YouTube
            self._handle_upload_to_youtube()
    
    def _handle_upload_to_youtube(self):
        """上传视频到YouTube"""
        try:
            # Import upload functions
            from upload_to_youtube import (  # type: ignore[import-untyped]
                load_config,
                get_authenticated_service,
                upload_video,
                read_metadata_files,
                check_already_uploaded,
                update_schedule_record,
                log_event,
                YouTubeUploadError,
            )
            
            # Get episode ID
            if self.console:
                ep_id = Prompt.ask("请输入期数ID (YYYYMMDD格式)", default="")
            else:
                ep_id = input("请输入期数ID (YYYYMMDD格式): ").strip()
            
            if not ep_id:
                if self.console:
                    self.print("[yellow]⚠️  未输入期数ID[/yellow]")
                else:
                    print("⚠️  未输入期数ID")
                return
            
            # Load configuration
            config = load_config()
            
            # Ask for optional settings
            if self.console:
                privacy_choice = Prompt.ask(
                    "隐私设置",
                    choices=["private", "unlisted", "public"],
                    default=config.get("privacy_status", "unlisted")
                )
                schedule = Confirm.ask("计划发布（设置为期数日期的9:00 AM）？", default=False)
                playlist_id = Prompt.ask("播放列表ID（留空使用配置中的）", default="")
                force = Confirm.ask("强制上传（即使已上传）？", default=False)
            else:
                privacy_input = input(f"隐私设置 [private/unlisted/public] [{config.get('privacy_status', 'unlisted')}]: ").strip()
                privacy_choice = privacy_input or config.get("privacy_status", "unlisted")
                schedule_input = input("计划发布？(y/N): ").strip().lower()
                schedule = schedule_input == 'y'
                playlist_id = input("播放列表ID（留空使用配置中的）: ").strip()
                force_input = input("强制上传？(y/N): ").strip().lower()
                force = force_input == 'y'
            
            config["privacy_status"] = privacy_choice
            config["schedule"] = schedule
            if playlist_id:
                config["playlist_id"] = playlist_id
            if force:
                config["force"] = True
            
            # Auto-detect video file
            output_dir = REPO_ROOT / "output"
            video_file = output_dir / f"{ep_id}_youtube.mp4"
            
            # If not found, try in final directories
            if not video_file.exists():
                final_dirs = list(output_dir.glob(f"{ep_id[:8]}-*"))
                for final_dir in final_dirs:
                    candidate = final_dir / f"{ep_id}_youtube.mp4"
                    if candidate.exists():
                        video_file = candidate
                        break
            
            # If still not found, search recursively
            if not video_file.exists():
                all_videos = list(output_dir.rglob(f"{ep_id}_youtube.mp4"))
                if all_videos:
                    video_file = all_videos[0]
            
            # Validate video file
            if not video_file.exists():
                if self.console:
                    self.print(Panel(
                        f"[red]❌ 视频文件未找到[/red]\n\n"
                        f"[dim]路径: {video_file}[/dim]\n\n"
                        f"[yellow]💡 请确保视频文件存在[/yellow]",
                        title="[bold red]上传失败[/bold red]",
                        border_style="red"
                    ))
                else:
                    print(f"\n❌ 视频文件未找到: {video_file}")
                    print("💡 请确保视频文件存在\n")
                return
            
            # Check if already uploaded
            existing_video_id = check_already_uploaded(ep_id)
            if existing_video_id and not force:
                if self.console:
                    self.print(Panel(
                        f"[green]✅ 期数 {ep_id} 已上传[/green]\n\n"
                        f"[cyan]📺 视频: https://www.youtube.com/watch?v={existing_video_id}[/cyan]\n\n"
                        f"[dim]💡 使用强制上传选项可重新上传[/dim]",
                        title="[bold green]已上传[/bold green]",
                        border_style="green"
                    ))
                else:
                    print(f"\n✅ 期数 {ep_id} 已上传")
                    print(f"📺 视频: https://www.youtube.com/watch?v={existing_video_id}")
                    print("💡 使用强制上传选项可重新上传\n")
                return
            
            # Read metadata
            metadata = read_metadata_files(ep_id, video_file, None, None)
            
            # Use defaults if metadata not found
            if not metadata["title"]:
                metadata["title"] = f"Kat Records Lo-Fi Mix - {ep_id}"
                if self.console:
                    self.print("[yellow]⚠️  未找到标题文件，使用默认标题[/yellow]")
                else:
                    print("⚠️  未找到标题文件，使用默认标题")
            
            if not metadata["description"]:
                metadata["description"] = "Kat Records - Lo-Fi Radio Mix"
                if self.console:
                    self.print("[yellow]⚠️  未找到描述文件，使用默认描述[/yellow]")
                else:
                    print("⚠️  未找到描述文件，使用默认描述")
            
            # Show upload info
            if self.console:
                info_table = Table(show_header=False, box=None)
                info_table.add_column(style="cyan", width=15)
                info_table.add_column(style="white", width=50)
                
                info_table.add_row("📹 视频", video_file.name)
                title_display = metadata["title"][:50] + "..." if len(metadata["title"]) > 50 else metadata["title"]
                info_table.add_row("📝 标题", title_display)
                if metadata["subtitle_path"]:
                    info_table.add_row("📄 字幕", Path(metadata["subtitle_path"]).name)
                if metadata["thumbnail_path"]:
                    info_table.add_row("🖼️  缩略图", Path(metadata["thumbnail_path"]).name)
                if config.get("playlist_id"):
                    info_table.add_row("📋 播放列表", config["playlist_id"])
                
                self.print(Panel(
                    info_table,
                    title="[bold cyan]📤 准备上传[/bold cyan]",
                    border_style="cyan"
                ))
            else:
                print(f"\n📤 准备上传期数 {ep_id} 到 YouTube")
                print(f"   📹 视频: {video_file.name}")
                print(f"   📝 标题: {metadata['title'][:60]}{'...' if len(metadata['title']) > 60 else ''}")
                if metadata["subtitle_path"]:
                    print(f"   📄 字幕: {Path(metadata['subtitle_path']).name}")
                if metadata["thumbnail_path"]:
                    print(f"   🖼️  缩略图: {Path(metadata['thumbnail_path']).name}")
                if config.get("playlist_id"):
                    print(f"   📋 播放列表: {config['playlist_id']}")
                print()
            
            # Log upload start
            log_event("upload", ep_id, "started", video_file=str(video_file))
            
            # Get authenticated service
            youtube = get_authenticated_service(config)
            
            # Upload video
            result = upload_video(
                youtube=youtube,
                video_file=video_file,
                title=metadata["title"],
                description=metadata["description"],
                config=config,
                subtitle_path=Path(metadata["subtitle_path"]) if metadata["subtitle_path"] else None,
                thumbnail_path=Path(metadata["thumbnail_path"]) if metadata["thumbnail_path"] else None,
                episode_id=ep_id,
                max_retries=5
            )
            
            # Update schedule_master.json
            update_schedule_record(ep_id, result["video_id"], result["video_url"])
            
            # Trigger event bus
            try:
                from core.event_bus import get_event_bus  # type: ignore[import-untyped]
                event_bus = get_event_bus()
                event_bus.emit_upload_started(ep_id)
                event_bus.emit_upload_completed(ep_id, result["video_id"], result["video_url"])
            except Exception:
                pass  # Event bus optional
            
            # Write upload result JSON
            output_dir = video_file.parent
            result_file = output_dir / f"{ep_id}_youtube_upload.json"
            import json
            result_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
            
            # Show success message
            if self.console:
                success_table = Table(show_header=False, box=None)
                success_table.add_column(style="green", width=15)
                success_table.add_column(style="white", width=50)
                
                success_table.add_row("📺 视频ID", result["video_id"])
                success_table.add_row("🔗 URL", result["video_url"])
                if result.get("playlist_id"):
                    success_table.add_row("📋 播放列表", result["playlist_id"])
                success_table.add_row("⏱️  耗时", f"{result.get('duration_seconds', 0):.1f} 秒")
                
                self.print(Panel(
                    success_table,
                    title="[bold green]✅ 上传成功！[/bold green]",
                    border_style="green"
                ))
            else:
                print(f"\n✅ 上传成功！")
                print(f"   📺 视频ID: {result['video_id']}")
                print(f"   🔗 URL: {result['video_url']}")
                if result.get("playlist_id"):
                    print(f"   📋 已添加到播放列表: {result['playlist_id']}")
                print(f"   ⏱️  耗时: {result.get('duration_seconds', 0):.1f} 秒")
                print()
            
            # Log success
            log_event("upload", ep_id, "completed", **result)
            
        except YouTubeUploadError as e:
            error_msg = str(e)
            log_event("upload", ep_id if 'ep_id' in locals() else None, "error", error=error_msg, exception_type=type(e).__name__)
            
            # Provide friendly error messages
            if self.console:
                if "403" in error_msg or "accessNotConfigured" in error_msg:
                    self.print(Panel(
                        "[red]❌ YouTube Data API v3 未启用[/red]\n\n"
                        "[yellow]🔧 解决步骤：[/yellow]\n"
                        "  1. 访问 Google Cloud Console\n"
                        "     https://console.cloud.google.com/\n"
                        "  2. 转到 'APIs & Services' → 'Library'\n"
                        "  3. 搜索并启用 'YouTube Data API v3'\n"
                        "  4. 等待 2-5 分钟让更改生效\n"
                        "  5. 重新运行上传命令\n\n"
                        "[dim]💡 或运行: python scripts/check_youtube_api.py[/dim]",
                        title="[bold red]上传失败[/bold red]",
                        border_style="red"
                    ))
                elif "401" in error_msg or "unauthorized" in error_msg.lower():
                    self.print(Panel(
                        "[yellow]⚠️  认证失败：需要重新授权[/yellow]\n\n"
                        "[dim]💡 下次运行上传时会自动触发授权流程[/dim]",
                        title="[bold yellow]认证失败[/bold yellow]",
                        border_style="yellow"
                    ))
                else:
                    self.print(Panel(
                        f"[red]❌ 上传失败[/red]\n\n"
                        f"[white]{error_msg}[/white]",
                        title="[bold red]错误[/bold red]",
                        border_style="red"
                    ))
            else:
                if "403" in error_msg or "accessNotConfigured" in error_msg:
                    print(f'\n❌ 上传失败：YouTube Data API v3 未启用')
                    print(f'\n🔧 解决步骤：')
                    print(f'   1. 访问 Google Cloud Console')
                    print(f'      https://console.cloud.google.com/')
                    print(f'   2. 转到 "APIs & Services" → "Library"')
                    print(f'   3. 搜索并启用 "YouTube Data API v3"')
                    print(f'   4. 等待 2-5 分钟让更改生效')
                    print(f'   5. 重新运行上传命令\n')
                elif "401" in error_msg or "unauthorized" in error_msg.lower():
                    print(f'\n⚠️  认证失败：需要重新授权')
                    print(f'💡 下次运行上传时会自动触发授权流程\n')
                else:
                    print(f'\n❌ 上传失败：{error_msg}\n')
                    
        except ImportError as e:
            if self.console:
                self.print(Panel(
                    f"[red]❌ 导入错误[/red]\n\n"
                    f"[white]{e}[/white]\n\n"
                    f"[yellow]💡 请确保所有依赖已正确安装[/yellow]",
                    title="[bold red]错误[/bold red]",
                    border_style="red"
                ))
            else:
                print(f'\n❌ 导入错误：{e}')
                print(f'💡 请确保所有依赖已正确安装\n')
        except Exception as e:
            error_msg = str(e)
            log_event("upload", ep_id if 'ep_id' in locals() else None, "error", error=error_msg, exception_type=type(e).__name__)
            if self.console:
                self.print(Panel(
                    f"[red]❌ 上传失败[/red]\n\n"
                    f"[white]{error_msg}[/white]",
                    title="[bold red]错误[/bold red]",
                    border_style="red"
                ))
            else:
                print(f'\n❌ 上传失败：{error_msg}\n')
    
    def _handle_system_config_menu(self):
        """系统配置与状态菜单（系统工具）- 重构版"""
        menu_items = [
            ("1", "环境状态检查", "检查环境初始化状态"),
            ("2", "API状态检查", "检查API配置和连接"),
            ("3", "排播表状态（详细）", "查看排播表详细状态"),
            ("4", "生产日志查看", "查看生产日志信息"),
            ("5", "初始化环境", "首次使用或环境变化时测试编码器"),
            ("6", "配置API密钥", "一次性配置OpenAI、Gemini等API"),
            ("7", "测试编码器", "基准测试（手动指定文件）"),
            ("8", "修复SSL证书", "修复macOS SSL证书验证问题"),
            ("9", "重置系统（危险操作）", "完整重置：清空文件、排播表和使用标记"),
            ("10", "清理临时文件", "清理临时和缓存文件"),
            ("11", "备份配置文件", "备份重要配置文件"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("⚙️  系统配置与状态", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"], default="0")
        else:
            choice = input("\n请选择操作 [0-11]: ").strip() or "0"
        
        if choice == "0":
            return
        elif choice == "1":
            # 环境状态检查
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "check_environment.py"),
            ]
            self.execute_command(cmd, "检查环境状态")
        elif choice == "2":
            # API状态检查
            try:
                from greet_garfield import greet_garfield  # type: ignore[import-untyped]
                success, message = greet_garfield()
                if self.console:
                    if success:
                        self.print(Panel(
                            f"[green]✅ {message}[/green]",
                            title="[bold green]API状态[/bold green]",
                            border_style="green"
                        ))
                    else:
                        self.print(Panel(
                            f"[yellow]⚠️  {message}[/yellow]",
                            title="[bold yellow]API状态[/bold yellow]",
                            border_style="yellow"
                        ))
                else:
                    print(f"\n{'✅' if success else '⚠️ '} {message}")
            except Exception as e:
                if self.console:
                    self.print(f"[red]❌ API检查失败: {e}[/red]")
                else:
                    print(f"❌ API检查失败: {e}")
        elif choice == "3":
            # 排播表状态（详细）
            self._handle_view_schedule_status()
        elif choice == "4":
            # 生产日志查看
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "show_schedule.py"),
            ]
            self.execute_command(cmd, "查看生产日志")
        elif choice == "5":
            # 初始化环境
            cmd = [
                sys.executable,
                str(REPO_ROOT / "tools" / "initialize_environment.py"),
            ]
            self.execute_command(cmd, "初始化环境")
        elif choice == "6":
            # 配置API密钥
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "configure_api.py"),
            ]
            self.execute_command(cmd, "配置API密钥")
        elif choice == "7":
            # 测试编码器
            if self.console:
                image = Prompt.ask("图片路径", default="assets/cover_sample/cover_sample.png")
                audio = Prompt.ask("音频路径", default="output/*_full_mix.mp3")
            else:
                image = input("图片路径 [assets/cover_sample/cover_sample.png]: ").strip() or "assets/cover_sample/cover_sample.png"
                audio = input("音频路径 [output/*_full_mix.mp3]: ").strip() or "output/*_full_mix.mp3"
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "tools" / "ffmpeg_bench.py"),
                "--image", image,
                "--audio", audio,
                "--fps", "1",
                "--duration-fix", "1fps-precise",
            ]
            self.execute_command(cmd, "测试编码器")
        elif choice == "8":
            # 修复SSL证书
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "fix_ssl_certificates.py"),
            ]
            self.execute_command(cmd, "修复SSL证书")
        elif choice == "9":
            # 重置系统（危险操作）
            self._handle_reset_menu()
        elif choice == "10":
            # 清理临时文件
            if self.console:
                confirm = Confirm.ask("确认清理临时文件？", default=False)
            else:
                confirm = input("确认清理临时文件？(y/N): ").strip().lower() == 'y'
            
            if confirm:
                # 清理output根目录中的临时文件（保留期数文件夹）
                import glob
                temp_patterns = [
                    "output/*.json",
                    "output/*.log",
                    "output/*.tmp",
                ]
                cleaned = 0
                for pattern in temp_patterns:
                    for file in glob.glob(pattern):
                        try:
                            Path(file).unlink()
                            cleaned += 1
                        except:
                            pass
                
                if self.console:
                    self.print(f"[green]✅ 已清理 {cleaned} 个临时文件[/green]")
                else:
                    print(f"✅ 已清理 {cleaned} 个临时文件")
        elif choice == "11":
            # 备份配置文件
            from datetime import datetime
            backup_dir = REPO_ROOT / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            config_files = [
                "config/schedule_master.json",
                "config/production_log.json",
                "data/song_library.csv",
                "data/song_usage.csv",
            ]
            
            backed_up = 0
            for config_file in config_files:
                src = REPO_ROOT / config_file
                if src.exists():
                    dst = backup_dir / f"{Path(config_file).name}.{timestamp}"
                    try:
                        import shutil
                        shutil.copy2(src, dst)
                        backed_up += 1
                    except:
                        pass
            
            if self.console:
                self.print(f"[green]✅ 已备份 {backed_up} 个配置文件到 backups/[/green]")
            else:
                print(f"✅ 已备份 {backed_up} 个配置文件到 backups/")
    
    def _handle_schedule_menu(self):
        """处理排播表菜单（保留兼容性，内部调用新菜单）"""
        # 重定向到新的排播表管理菜单
        self._handle_schedule_management_menu()
    
    def _handle_modify_schedule(self):
        """处理修改排播表"""
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
        
        try:
            from schedule_master import ScheduleMaster  # type: ignore[import-untyped]
            schedule = ScheduleMaster.load()
            
            if not schedule:
                if self.console:
                    self.print("[yellow]⚠️  排播表不存在[/yellow]")
                    self.print("[dim]请先创建排播表[/dim]")
                    if Confirm.ask("是否现在创建排播表？", default=True):
                        # 不递归调用，直接返回让用户在主菜单选择
                        return
                else:
                    print("⚠️  排播表不存在，请先创建排播表")
                    create = input("是否现在创建排播表？(Y/n): ").strip().lower() != 'n'
                    if create:
                        # 不递归调用，直接返回让用户在主菜单选择
                        return
                return
            
            # 显示当前排播表信息
            end_date = schedule.get_end_date()
            if self.console:
                self.print("[cyan]📋 当前排播表信息[/cyan]")
                self.print(f"   起始日期：{schedule.start_date}")
                self.print(f"   结束日期：{end_date}")
                self.print(f"   排播间隔：{schedule.schedule_interval_days} 天")
                self.print(f"   总期数：{schedule.total_episodes} 期")
            else:
                print("📋 当前排播表信息")
                print(f"   起始日期：{schedule.start_date}")
                print(f"   结束日期：{end_date}")
                print(f"   排播间隔：{schedule.schedule_interval_days} 天")
                print(f"   总期数：{schedule.total_episodes} 期")
            
            # 询问修改选项
            if self.console:
                self.print("\n[cyan]修改选项：[/cyan]")
                action = Prompt.ask(
                    "请选择操作",
                    choices=["修改起始日期", "修改排播间隔", "删除期数", "取消"],
                    default="取消"
                )
            else:
                print("\n修改选项：")
                print("  1. 修改起始日期")
                print("  2. 修改排播间隔")
                print("  3. 删除期数")
                print("  4. 取消")
                action_choice = input("请选择 [1-4] (4): ").strip() or "4"
                action_map = {"1": "修改起始日期", "2": "修改排播间隔", "3": "删除期数", "4": "取消"}
                action = action_map.get(action_choice, "取消")
            
            if action == "取消":
                return
            
            # 构建命令
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "modify_schedule.py"),
            ]
            
            if action == "修改起始日期":
                if self.console:
                    new_start = Prompt.ask("请输入新的起始日期 (YYYY-MM-DD)", default=schedule.start_date)
                else:
                    new_start = input(f"请输入新的起始日期 (YYYY-MM-DD) [{schedule.start_date}]: ").strip() or schedule.start_date
                cmd.extend(["--start-date", new_start])
            
            elif action == "修改排播间隔":
                if self.console:
                    new_interval = Prompt.ask("请输入新的排播间隔（天）", default=str(schedule.schedule_interval_days))
                else:
                    new_interval = input(f"请输入新的排播间隔（天） [{schedule.schedule_interval_days}]: ").strip() or str(schedule.schedule_interval_days)
                try:
                    interval_int = int(new_interval)
                    if interval_int <= 0:
                        if self.console:
                            self.print("[red]❌ 排播间隔必须大于0[/red]")
                        else:
                            print("❌ 排播间隔必须大于0")
                        return
                except ValueError:
                    if self.console:
                        self.print("[red]❌ 请输入有效的数字[/red]")
                    else:
                        print("❌ 请输入有效的数字")
                    return
                cmd.extend(["--interval", new_interval])
            
            elif action == "删除期数":
                if self.console:
                    ep_id = Prompt.ask("请输入要删除的期数ID (YYYYMMDD格式)", default="")
                else:
                    ep_id = input("请输入要删除的期数ID (YYYYMMDD格式): ").strip()
                
                if not ep_id:
                    if self.console:
                        self.print("[yellow]⚠️  已取消[/yellow]")
                    else:
                        print("⚠️  已取消")
                    return
                
                cmd.extend(["--delete-episode", ep_id])
            
            self.execute_command(cmd, f"修改排播表 - {action}")
            
        except Exception as e:
            if self.console:
                self.print(f"[red]❌ 修改排播表失败: {e}[/red]")
            else:
                print(f"❌ 修改排播表失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_generate_menu(self):
        """处理视频生成菜单"""
        choice = self.show_generate_menu()
        
        if choice == "0":
            return
        
        elif choice == "1":
            # 生成单期
            if self.console:
                ep_id = Prompt.ask("请输入期数ID (YYYYMMDD格式)", default="20251101")
            else:
                ep_id = input("请输入期数ID (YYYYMMDD格式) [20251101]: ").strip() or "20251101"
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
                "--font_name", "Lora-Regular",
                "--episode-id", ep_id,
            ]
            
            self.execute_command(cmd, f"生成单期（ID: {ep_id}）")
        
        elif choice == "2":
            # 批量生成
            if self.console:
                count = Prompt.ask("请输入生成期数", default="10")
            else:
                count = input("请输入生成期数 [10]: ").strip() or "10"
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "batch_generate_videos.py"),
                count,
            ]
            
            self.execute_command(cmd, f"批量生成{count}期")
        
        elif choice == "3":
            # 仅生成封面
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
                "--font_name", "Lora-Regular",
                "--no-remix",
                "--no-video",
            ]
            self.execute_command(cmd, "仅生成封面")
        
        elif choice == "4":
            # 广度优先生成
            if self.console:
                force = Confirm.ask("强制重新生成所有文件？", default=False)
                skip_stages = Prompt.ask(
                    "跳过哪些阶段？（用逗号分隔，例如：4,5 表示跳过视频和打包，留空不跳过）",
                    default=""
                ).strip()
            else:
                force = input("强制重新生成所有文件？(y/N): ").strip().lower() == 'y'
                skip_stages = input("跳过哪些阶段？（用逗号分隔，例如：4,5，留空不跳过）: ").strip()
            
            if self.console:
                no_pause = Confirm.ask("自动运行不暂停？", default=True)
            else:
                no_pause = input("自动运行不暂停？(Y/n): ").strip().lower() != 'n'
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "breadth_first_generate.py"),
            ]
            if force:
                cmd.append("--force")
            if no_pause:
                cmd.append("--no-pause")
            if skip_stages:
                try:
                    stages = [int(s.strip()) for s in skip_stages.split(",") if s.strip()]
                    if stages:
                        cmd.extend(["--skip-stage"] + [str(s) for s in stages])
                except:
                    pass
            
            self.execute_command(cmd, "广度优先生成所有期数")
    
    def _handle_status_config_menu(self):
        """处理状态与配置菜单（合并查看状态和环境配置）"""
        choice = self.show_status_config_menu()
        
        if choice == "0":
            return
        
        elif choice == "1":
            # 排播表状态
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "show_schedule.py"),
            ]
            self.execute_command(cmd, "查看排播表状态")
        
        elif choice == "2":
            # 环境状态
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "init_env.py"),
                "--check-only",
            ]
            self.execute_command(cmd, "检查环境状态")
        
        elif choice == "3":
            # API状态
            if self.console:
                test = Confirm.ask("执行实际API调用测试？", default=False)
            else:
                test = input("执行实际API调用测试？(y/N): ").strip().lower() == 'y'
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "check_api_status.py"),
            ]
            if test:
                cmd.append("--test")
            
            self.execute_command(cmd, "检查API状态")
        
        elif choice == "4":
            # 初始化环境
            if self.console:
                confirm = Confirm.ask("初始化环境将测试编码器，可能需要几分钟，继续？", default=True)
            else:
                confirm = input("初始化环境将测试编码器，可能需要几分钟，继续？(Y/n): ").strip().lower() != 'n'
            
            if confirm:
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "init_env.py"),
                ]
                self.execute_command(cmd, "初始化环境")
        
        elif choice == "5":
            # 配置API密钥（使用新的配置向导）
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "local_picker" / "configure_api.py"),
            ]
            self.execute_command(cmd, "配置API密钥（支持OpenAI、Gemini等）")
        
        elif choice == "6":
            # 修复SSL证书
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "fix_ssl_certificates.py"),
            ]
            self.execute_command(cmd, "修复SSL证书")
        
        elif choice == "7":
            # 测试编码器
            if self.console:
                image = Prompt.ask("图片路径", default="assets/cover_sample/cover_sample.png")
                audio = Prompt.ask("音频路径", default="output/audio/*_full_mix.mp3")
            else:
                image = input("图片路径 [assets/cover_sample/cover_sample.png]: ").strip() or "assets/cover_sample/cover_sample.png"
                audio = input("音频路径 [output/audio/*_full_mix.mp3]: ").strip() or "output/audio/*_full_mix.mp3"
            
            cmd = [
                sys.executable,
                str(REPO_ROOT / "tools" / "ffmpeg_bench.py"),
                "--image", image,
                "--audio", audio,
                "--fps", "1",
                "--duration-fix", "1fps-precise",
            ]
            self.execute_command(cmd, "基准测试")
    
    def _handle_reset_menu(self):
        """处理重置初始化菜单"""
        if self.console:
            self.print(Panel(
                "[bold red]⚠️  警告：重置操作不可逆！[/bold red]\n\n"
                "完整重置将执行以下操作：\n"
                "  1. 删除output目录下所有文件（包括期数文件夹）\n"
                "  2. 删除排播表（config/schedule_master.json）\n"
                "  3. 重置图库使用标记（清空images_used）\n"
                "  4. 重置歌库使用标记（清空tracks_used和song_usage.csv）\n"
                "  5. 验证重置结果",
                title="[bold yellow]重置初始化[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED
            ))
            confirm = Confirm.ask("\n确认执行完整重置？", default=False)
        else:
            print("\n" + "=" * 70)
            print("⚠️  警告：重置操作不可逆！")
            print("=" * 70)
            print("完整重置将执行以下操作：")
            print("  1. 删除output目录下所有文件（包括期数文件夹）")
            print("  2. 删除排播表（config/schedule_master.json）")
            print("  3. 重置图库使用标记（清空images_used）")
            print("  4. 重置歌库使用标记（清空tracks_used和song_usage.csv）")
            print("  5. 验证重置结果")
            print("=" * 70)
            confirm = input("\n确认执行完整重置？(yes/no): ").strip().lower() == 'yes'
        
        if not confirm:
            if self.console:
                self.print("[yellow]❌ 已取消重置[/yellow]")
            else:
                print("❌ 已取消重置")
            return
        
        # 执行重置
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "reset_all.py"),
            "--yes",  # 跳过二次确认（因为用户已经在菜单中确认了）
        ]
        self.execute_command(cmd, "完整重置初始化")
    
    def _handle_help_menu(self):
        """处理帮助文档菜单（保留兼容性，内部调用新菜单）"""
        # 重定向到新的帮助文档菜单
        self._handle_help_documentation_menu()
    
    def _handle_web_console(self):
        """启动 Web 控制台"""
        if self.console:
            self.print(Panel(
                "[bold cyan]🌐 Web 控制台[/bold cyan]\n\n"
                "[dim]Web 控制台将在浏览器中打开，提供可视化的管理和监控界面。[/dim]\n\n"
                "[yellow]提示:[/yellow] 按 Ctrl+C 停止服务器并返回主菜单",
                title="[bold cyan]启动选项[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED
            ))
        else:
            print("\n" + "=" * 70)
            print("🌐 Web 控制台")
            print("=" * 70)
            print("\nWeb 控制台将在浏览器中打开，提供可视化的管理和监控界面。")
            print("提示: 按 Ctrl+C 停止服务器并返回主菜单\n")
        
        try:
            # 使用 kat_cli.py 的 web 命令启动
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "kat_cli.py"),
                "web",
                "--open",  # 自动打开浏览器
            ]
            
            if self.console:
                self.print("\n[cyan]正在启动 Web 服务器...[/cyan]\n")
            else:
                print("\n正在启动 Web 服务器...\n")
            
            # 直接在前台运行（用户可以按 Ctrl+C 停止）
            # 这会阻塞，直到服务器停止
            self.execute_command(cmd, "启动 Web 控制台")
            
            if self.console:
                self.print("\n[yellow]Web 服务器已停止[/yellow]")
            else:
                print("\nWeb 服务器已停止")
            
        except KeyboardInterrupt:
            if self.console:
                self.print("\n[yellow]⚠️  已停止 Web 服务器[/yellow]")
            else:
                print("\n⚠️  已停止 Web 服务器")
        except Exception as e:
            error_msg = str(e)
            if "uvicorn" in error_msg.lower() or "fastapi" in error_msg.lower():
                # 缺少依赖的情况
                if self.console:
                    self.print(f"\n[red]❌ 启动失败: {e}[/red]")
                    self.print("[yellow]💡 检测到缺少依赖，正在尝试自动安装...[/yellow]")
                else:
                    print(f"\n❌ 启动失败: {e}")
                    print("💡 检测到缺少依赖，正在尝试自动安装...")
                
                # 尝试自动安装依赖
                try:
                    import subprocess
                    install_cmd = [
                        sys.executable, "-m", "pip", "install", 
                        "fastapi", "uvicorn[standard]"
                    ]
                    result = subprocess.run(
                        install_cmd,
                        cwd=REPO_ROOT,
                        check=False,
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        if self.console:
                            self.print("[green]✅ 依赖安装成功！[/green]")
                            self.print("[cyan]正在重新启动 Web 服务器...[/cyan]\n")
                        else:
                            print("✅ 依赖安装成功！")
                            print("正在重新启动 Web 服务器...\n")
                        
                        # 重新尝试启动
                        return self._handle_web_console()
                    else:
                        if self.console:
                            self.print("[red]❌ 自动安装失败[/red]")
                            self.print("[dim]请手动运行: pip install fastapi uvicorn[standard][/dim]")
                            self.print("[dim]或安装所有依赖: pip install -r requirements.txt[/dim]")
                        else:
                            print("❌ 自动安装失败")
                            print("请手动运行: pip install fastapi uvicorn[standard]")
                            print("或安装所有依赖: pip install -r requirements.txt")
                except Exception as install_error:
                    if self.console:
                        self.print(f"[red]❌ 自动安装出错: {install_error}[/red]")
                        self.print("[dim]请手动运行: pip install fastapi uvicorn[standard][/dim]")
                    else:
                        print(f"❌ 自动安装出错: {install_error}")
                        print("请手动运行: pip install fastapi uvicorn[standard]")
            else:
                # 其他错误
                if self.console:
                    self.print(f"\n[red]❌ 启动失败: {e}[/red]")
                    self.print("[dim]提示: 确保已安装 fastapi 和 uvicorn: pip install fastapi uvicorn[standard][/dim]")
                else:
                    print(f"\n❌ 启动失败: {e}")
                    print("提示: 确保已安装 fastapi 和 uvicorn: pip install fastapi uvicorn[standard]")
    
    def _handle_help_documentation_menu(self):
        """帮助文档菜单（重构版）"""
        menu_items = [
            ("1", "工作流程概览", "查看KAT REC完整工作流程"),
            ("2", "常用命令速查", "显示常用命令快速参考"),
            ("3", "快捷键列表", "显示快捷键说明"),
            ("4", "完整命令辞典", "查看所有可用命令"),
            ("5", "API使用指南", "OpenAI API使用说明"),
            ("6", "API安全指南", "API密钥安全配置"),
            ("7", "工作流程详解", "详细工作流程说明"),
            ("8", "文档索引", "列出所有文档"),
            ("9", "搜索文档", "在文档中搜索关键词"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("📖 帮助文档", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], default="0")
        else:
            choice = input("\n请选择操作 [0-9]: ").strip() or "0"
        
        if choice == "0":
            return
        elif choice == "1":
            # 工作流程概览
            doc_path = REPO_ROOT / "docs" / "KAT_REC工作流程.md"
            if doc_path.exists():
                if self.console:
                    self.print(f"[cyan]📖 打开文档: {doc_path}[/cyan]")
                else:
                    print(f"📖 文档位置: {doc_path}")
                # 显示前100行
                try:
                    content = doc_path.read_text(encoding="utf-8")
                    lines = content.split("\n")[:100]
                    print("\n".join(lines))
                    print("\n... (更多内容请查看完整文档)")
                except Exception:
                    pass
            else:
                if self.console:
                    self.print("[yellow]⚠️  文档不存在[/yellow]")
                else:
                    print("⚠️  文档不存在")
        elif choice == "2":
            # 常用命令速查
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "show_help.py"),
                "--quick",
            ]
            self.execute_command(cmd, "显示快速参考")
        elif choice == "3":
            # 快捷键列表
            shortcuts = {
                "Q": "快速查看状态",
                "G": "快速生成单期",
                "C": "检查文件",
                "H": "帮助",
            }
            if self.console:
                from rich.table import Table
                table = Table(title="⌨️  快捷键", box=box.ROUNDED)
                table.add_column("快捷键", style="cyan")
                table.add_column("功能", style="green")
                for key, desc in shortcuts.items():
                    table.add_row(key, desc)
                self.print(table)
            else:
                print("\n⌨️  快捷键：")
                for key, desc in shortcuts.items():
                    print(f"  {key}: {desc}")
        elif choice == "4":
            # 完整命令辞典
            help_path = REPO_ROOT / "COMMAND_REFERENCE.md"
            if help_path.exists():
                if self.console:
                    self.print(f"[cyan]📖 打开文档: {help_path}[/cyan]")
                else:
                    print(f"📖 文档位置: {help_path}")
            else:
                if self.console:
                    self.print("[yellow]⚠️  文档不存在[/yellow]")
                else:
                    print("⚠️  文档不存在")
        elif choice == "5":
            # API使用指南
            help_path = REPO_ROOT / "docs" / "API完整指南.md"
            if help_path.exists():
                if self.console:
                    self.print(f"[cyan]📖 打开文档: {help_path}[/cyan]")
                else:
                    print(f"📖 文档位置: {help_path}")
                try:
                    content = help_path.read_text(encoding="utf-8")
                    lines = content.split("\n")[:50]
                    print("\n".join(lines))
                    print("\n... (更多内容请查看完整文档)")
                except Exception:
                    pass
        elif choice == "6":
            # API安全指南（已合并到API完整指南）
            help_path = REPO_ROOT / "docs" / "API完整指南.md"
            if help_path.exists():
                if self.console:
                    self.print(f"[cyan]📖 打开文档: {help_path}[/cyan]")
                else:
                    print(f"📖 文档位置: {help_path}")
        elif choice == "7":
            # 工作流程详解
            doc_path = REPO_ROOT / "docs" / "KAT_REC工作流程.md"
            if doc_path.exists():
                if self.console:
                    self.print(f"[cyan]📖 打开文档: {doc_path}[/cyan]")
                else:
                    print(f"📖 文档位置: {doc_path}")
        elif choice == "8":
            # 文档索引
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "show_help.py"),
                "--docs",
            ]
            self.execute_command(cmd, "显示文档索引")
        elif choice == "9":
            # 搜索文档
            if self.console:
                keyword = Prompt.ask("请输入搜索关键词")
            else:
                keyword = input("请输入搜索关键词: ").strip()
            
            if keyword:
                # 简单的文档搜索
                docs_dir = REPO_ROOT / "docs"
                results = []
                if docs_dir.exists():
                    for doc_file in docs_dir.glob("*.md"):
                        try:
                            content = doc_file.read_text(encoding="utf-8")
                            if keyword.lower() in content.lower():
                                results.append(doc_file.name)
                        except:
                            pass
                
                if results:
                    if self.console:
                        from rich.table import Table
                        table = Table(title=f"搜索结果: {keyword}", box=box.ROUNDED)
                        table.add_column("文档", style="cyan")
                        for result in results:
                            table.add_row(result)
                        self.print(table)
                    else:
                        print(f"\n搜索结果（关键词: {keyword}）：")
                        for result in results:
                            print(f"  • {result}")
                else:
                    if self.console:
                        self.print(f"[yellow]未找到包含 '{keyword}' 的文档[/yellow]")
                    else:
                        print(f"未找到包含 '{keyword}' 的文档")
    
    def show_help_menu(self):
        """帮助文档菜单（保留兼容性，返回选择用于旧接口）"""
        menu_items = [
            ("1", "快速参考", "显示常用命令快速参考"),
            ("2", "完整命令辞典", "查看所有可用命令"),
            ("3", "API使用指南", "OpenAI API使用说明"),
            ("4", "API安全指南", "API密钥安全配置"),
            ("5", "文档索引", "列出所有文档"),
            ("0", "返回", "返回主菜单"),
        ]
        
        self._show_submenu("帮助文档", menu_items)
        
        if self.console:
            choice = Prompt.ask("\n请选择操作", choices=["0", "1", "2", "3", "4", "5"], default="0")
        else:
            choice = input("\n请选择操作 [0-5]: ").strip() or "0"
        
        return choice


def main():
    parser = argparse.ArgumentParser(
        description="KAT Records Studio - 交互式终端界面",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/kat_terminal.py              # 启动交互式界面
  python scripts/kat_terminal.py help         # 显示帮助（非交互模式）
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        help="直接执行的命令（如 'help'）"
    )
    
    args = parser.parse_args()
    
    terminal = KatTerminal()
    
    if args.command == "help":
        # 非交互模式：直接显示帮助
        terminal.show_header()
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "show_help.py"),
        ]
        subprocess.run(cmd, cwd=REPO_ROOT)
    else:
        # 交互模式
        terminal.run_interactive()


if __name__ == "__main__":
    main()


