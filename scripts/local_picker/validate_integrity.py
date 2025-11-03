#!/usr/bin/env python3
# coding: utf-8
"""
完整性验证工具

功能：
1. 检查schedule_master.json中每个期数的字段一致性
2. 验证已完成期数是否有对应的输出目录和视频文件
3. 确保没有重复的episode_id
4. 生成JSON格式的验证报告

用法：
    python scripts/local_picker/validate_integrity.py          # 快速检查
    python scripts/local_picker/validate_integrity.py --deep  # 深度检查（包括文件系统验证）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster
    SCHEDULE_AVAILABLE = True
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    SCHEDULE_AVAILABLE = False
    sys.exit(1)

# 尝试导入rich用于彩色输出
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class IntegrityValidator:
    """完整性验证器"""
    
    def __init__(self, schedule: ScheduleMaster, output_dir: Path, deep: bool = False):
        self.schedule = schedule
        self.output_dir = output_dir
        self.deep = deep
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
        self.total_episodes = len(schedule.episodes)
    
    def validate(self) -> Dict:
        """
        执行完整性验证
        
        Returns:
            验证结果字典
        """
        # 1. 检查重复episode_id
        self._check_duplicate_ids()
        
        # 2. 检查字段一致性
        self._check_field_consistency()
        
        # 3. 检查状态一致性
        self._check_status_consistency()
        
        # 4. 深度检查（如果启用）
        if self.deep:
            self._check_file_system_integrity()
        
        return {
            "total": self.total_episodes,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "is_valid": len(self.errors) == 0
        }
    
    def _check_duplicate_ids(self) -> None:
        """检查重复的episode_id"""
        seen_ids: Set[str] = set()
        for ep in self.schedule.episodes:
            ep_id = ep.get("episode_id")
            if not ep_id:
                self.errors.append({
                    "type": "missing_id",
                    "episode_number": ep.get("episode_number"),
                    "message": "期数缺少episode_id"
                })
                continue
            
            if ep_id in seen_ids:
                self.errors.append({
                    "type": "duplicate_id",
                    "episode_id": ep_id,
                    "message": f"重复的episode_id: {ep_id}"
                })
            else:
                seen_ids.add(ep_id)
    
    def _check_field_consistency(self) -> None:
        """检查字段一致性"""
        required_fields = ["episode_id", "schedule_date", "episode_number", "status"]
        
        for ep in self.schedule.episodes:
            ep_id = ep.get("episode_id", "未知")
            
            # 检查必需字段
            for field in required_fields:
                if field not in ep:
                    self.errors.append({
                        "type": "missing_field",
                        "episode_id": ep_id,
                        "field": field,
                        "message": f"期数 {ep_id} 缺少必需字段: {field}"
                    })
            
            # 检查状态值有效性
            status = ep.get("status", "")
            valid_statuses = {"pending", "remixing", "rendering", "uploading", "completed", "error"}
            if status and status not in valid_statuses:
                self.warnings.append({
                    "type": "invalid_status",
                    "episode_id": ep_id,
                    "status": status,
                    "message": f"期数 {ep_id} 状态值无效: {status}"
                })
            
            # 检查日期格式
            schedule_date = ep.get("schedule_date", "")
            if schedule_date:
                try:
                    from datetime import datetime
                    datetime.strptime(schedule_date, "%Y-%m-%d")
                except ValueError:
                    self.errors.append({
                        "type": "invalid_date_format",
                        "episode_id": ep_id,
                        "date": schedule_date,
                        "message": f"期数 {ep_id} 日期格式无效: {schedule_date}（应为YYYY-MM-DD）"
                    })
            
            # 检查tracks_used是否为列表
            tracks_used = ep.get("tracks_used")
            if tracks_used is not None and not isinstance(tracks_used, list):
                self.errors.append({
                    "type": "invalid_tracks_used",
                    "episode_id": ep_id,
                    "message": f"期数 {ep_id} 的tracks_used应为列表类型"
                })
    
    def _check_status_consistency(self) -> None:
        """检查状态一致性"""
        # 状态为completed但缺少标题或曲目
        for ep in self.schedule.episodes:
            ep_id = ep.get("episode_id", "未知")
            status = ep.get("status", "")
            
            if status == "completed":
                if not ep.get("title"):
                    self.warnings.append({
                        "type": "completed_without_title",
                        "episode_id": ep_id,
                        "message": f"期数 {ep_id} 状态为completed但缺少title"
                    })
                
                if not ep.get("tracks_used"):
                    self.warnings.append({
                        "type": "completed_without_tracks",
                        "episode_id": ep_id,
                        "message": f"期数 {ep_id} 状态为completed但缺少tracks_used"
                    })
    
    def _check_file_system_integrity(self) -> None:
        """深度检查：验证文件系统完整性"""
        for ep in self.schedule.episodes:
            ep_id = ep.get("episode_id", "未知")
            status = ep.get("status", "")
            schedule_date = ep.get("schedule_date", "")
            title = ep.get("title", "")
            
            if status == "completed":
                # 查找期数文件夹
                episode_folders = []
                
                if schedule_date and title:
                    try:
                        from datetime import datetime as dt
                        date_obj = dt.strptime(schedule_date, "%Y-%m-%d")
                        title_safe = title.replace(" ", "_").replace("/", "_")
                        folder_name = f"{date_obj.strftime('%Y-%m-%d')}_{title_safe}"
                        folder_path = self.output_dir / folder_name
                        if folder_path.exists():
                            episode_folders.append(folder_path)
                    except Exception:
                        pass
                
                # 如果未找到，尝试在output根目录查找
                if not episode_folders:
                    for folder in self.output_dir.iterdir():
                        if folder.is_dir() and ep_id in folder.name:
                            episode_folders.append(folder)
                            break
                
                # 检查必需文件
                if not episode_folders:
                    self.errors.append({
                        "type": "missing_output_folder",
                        "episode_id": ep_id,
                        "message": f"期数 {ep_id} 状态为completed但未找到输出文件夹"
                    })
                else:
                    folder = episode_folders[0]
                    required_files = {
                        "cover": f"{ep_id}_cover.png",
                        "playlist": f"{ep_id}_playlist.csv",
                        "audio": [f"{ep_id}_full_mix.mp3", f"{ep_id}_playlist_full_mix.mp3"],
                        "video": [f"{ep_id}_youtube.mp4", f"{ep_id}_youtube.mov"],
                    }
                    
                    missing = []
                    for key, patterns in required_files.items():
                        if isinstance(patterns, str):
                            patterns = [patterns]
                        
                        found = False
                        for pattern in patterns:
                            if (folder / pattern).exists():
                                found = True
                                break
                        
                        if not found:
                            missing.append(key)
                    
                    if missing:
                        self.errors.append({
                            "type": "missing_files",
                            "episode_id": ep_id,
                            "folder": folder.name,
                            "missing": missing,
                            "message": f"期数 {ep_id} 缺少必需文件: {', '.join(missing)}"
                        })


def print_summary(result: Dict, use_rich: bool = False) -> None:
    """打印验证结果摘要"""
    if use_rich and RICH_AVAILABLE:
        console = Console()
        
        # 创建结果面板
        status = "✅ 通过" if result["is_valid"] else "❌ 失败"
        color = "green" if result["is_valid"] else "red"
        
        summary = f"""
总期数: {result['total']}
错误数: {result['error_count']}
警告数: {result['warning_count']}
状态: {status}
        """.strip()
        
        console.print(Panel(summary, title="验证结果", border_style=color))
        
        # 错误表格
        if result["errors"]:
            table = Table(title="错误列表", show_header=True, header_style="red")
            table.add_column("类型", style="cyan")
            table.add_column("期数ID", style="yellow")
            table.add_column("消息", style="white")
            
            for error in result["errors"][:20]:  # 最多显示20个
                table.add_row(
                    error.get("type", "未知"),
                    error.get("episode_id", error.get("episode_number", "未知")),
                    error.get("message", "")
                )
            
            console.print(table)
            
            if len(result["errors"]) > 20:
                console.print(f"[yellow]... 还有 {len(result['errors']) - 20} 个错误未显示[/yellow]")
        
        # 警告表格
        if result["warnings"]:
            table = Table(title="警告列表", show_header=True, header_style="yellow")
            table.add_column("类型", style="cyan")
            table.add_column("期数ID", style="yellow")
            table.add_column("消息", style="white")
            
            for warning in result["warnings"][:20]:  # 最多显示20个
                table.add_row(
                    warning.get("type", "未知"),
                    warning.get("episode_id", "未知"),
                    warning.get("message", "")
                )
            
            console.print(table)
            
            if len(result["warnings"]) > 20:
                console.print(f"[yellow]... 还有 {len(result['warnings']) - 20} 个警告未显示[/yellow]")
    else:
        # 简单文本输出
        print("=" * 70)
        print("完整性验证结果")
        print("=" * 70)
        print(f"总期数: {result['total']}")
        print(f"错误数: {result['error_count']}")
        print(f"警告数: {result['warning_count']}")
        print(f"状态: {'✅ 通过' if result['is_valid'] else '❌ 失败'}")
        print("=" * 70)
        
        if result["errors"]:
            print(f"\n❌ 错误 ({len(result['errors'])} 个):")
            for error in result["errors"][:10]:
                print(f"  - [{error.get('type', '未知')}] {error.get('message', '')}")
            if len(result["errors"]) > 10:
                print(f"  ... 还有 {len(result['errors']) - 10} 个错误")
        
        if result["warnings"]:
            print(f"\n⚠️  警告 ({len(result['warnings'])} 个):")
            for warning in result["warnings"][:10]:
                print(f"  - [{warning.get('type', '未知')}] {warning.get('message', '')}")
            if len(result["warnings"]) > 10:
                print(f"  ... 还有 {len(result['warnings']) - 10} 个警告")


def main():
    parser = argparse.ArgumentParser(
        description="完整性验证工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 快速检查
  python scripts/local_picker/validate_integrity.py
  
  # 深度检查（包括文件系统验证）
  python scripts/local_picker/validate_integrity.py --deep
  
  # 输出JSON格式
  python scripts/local_picker/validate_integrity.py --json
        """
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="深度检查（包括文件系统完整性验证）"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出JSON格式结果"
    )
    
    args = parser.parse_args()
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在，请先创建排播表")
        sys.exit(1)
    
    # 执行验证
    output_dir = REPO_ROOT / "output"
    validator = IntegrityValidator(schedule, output_dir, deep=args.deep)
    result = validator.validate()
    
    # 输出结果
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_summary(result, use_rich=RICH_AVAILABLE)
        
        # 返回适当的退出码
        sys.exit(0 if result["is_valid"] else 1)


if __name__ == "__main__":
    main()

