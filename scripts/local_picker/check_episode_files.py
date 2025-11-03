#!/usr/bin/env python3
# coding: utf-8
"""
检查期数文件夹的文件完整性

功能：
1. 扫描 output 目录下的所有期数文件夹
2. 检查每个文件夹是否包含必需的文件
3. 列出缺失的文件并提示如何补充生成

用法：
    python scripts/local_picker/check_episode_files.py
    python scripts/local_picker/check_episode_files.py --output output/DEMO  # 检查DEMO文件夹
"""
from __future__ import annotations

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster
    from utils import extract_title_from_playlist, get_final_output_dir
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    sys.exit(1)

try:
    from rich.console import Console  # pyright: ignore[reportMissingImports]
    from rich.table import Table  # pyright: ignore[reportMissingImports]
    from rich.panel import Panel  # pyright: ignore[reportMissingImports]
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def extract_episode_id_from_folder(folder_path: Path) -> Optional[str]:
    """从文件夹名提取期数ID（YYYYMMDD格式）"""
    # 格式1: YYYY-MM-DD_Title
    match = re.match(r"^(\d{4}-\d{2}-\d{2})_", folder_path.name)
    if match:
        date_str = match.group(1)
        # 转换为 YYYYMMDD
        return date_str.replace("-", "")
    
    # 格式2: 直接包含 YYYYMMDD 的文件夹名
    match = re.search(r"(\d{8})", folder_path.name)
    if match:
        return match.group(1)
    
    return None


def check_episode_folder(episode_dir: Path, id_str: str) -> Tuple[bool, Dict[str, List[str]]]:
    """
    检查期数文件夹的文件完整性
    
    Returns:
        (是否完整, {缺失类型: [文件列表]})
    """
    missing = {
        "必需": [],
        "推荐": [],
    }
    
    # 必需文件
    required_files = {
        "cover": episode_dir / f"{id_str}_cover.png",
        "playlist": episode_dir / f"{id_str}_playlist.csv",
        "full_mix": episode_dir / f"{id_str}_full_mix.mp3",
    }
    
    # 检查 full_mix 的两种可能命名
    full_mix_v1 = episode_dir / f"{id_str}_full_mix.mp3"
    full_mix_v2 = episode_dir / f"{id_str}_playlist_full_mix.mp3"
    if full_mix_v2.exists() and not full_mix_v1.exists():
        required_files["full_mix"] = full_mix_v2
    
    for key, file_path in required_files.items():
        if not file_path.exists():
            missing["必需"].append(f"{key}: {file_path.name}")
    
    # 推荐文件（YouTube资源）
    recommended_files = {
        "srt": episode_dir / f"{id_str}_youtube.srt",
        "youtube_title": episode_dir / f"{id_str}_youtube_title.txt",
        "youtube_desc": episode_dir / f"{id_str}_youtube_description.txt",
        "video": episode_dir / f"{id_str}_youtube.mp4",
    }
    
    for key, file_path in recommended_files.items():
        if not file_path.exists():
            missing["推荐"].append(f"{key}: {file_path.name}")
    
    is_complete = len(missing["必需"]) == 0 and len(missing["推荐"]) == 0
    
    return is_complete, missing


def generate_fix_suggestions(id_str: str, missing: Dict[str, List[str]], episode_dir: Path) -> List[str]:
    """生成修复建议"""
    suggestions = []
    
    # 检查缺失的类型
    missing_types = set()
    for item in missing["必需"] + missing["推荐"]:
        if "cover" in item.lower():
            missing_types.add("cover")
        elif "playlist" in item.lower():
            missing_types.add("playlist")
        elif "full_mix" in item.lower() or "audio" in item.lower():
            missing_types.add("audio")
        elif "srt" in item.lower() or "youtube_title" in item.lower() or "youtube_desc" in item.lower():
            missing_types.add("youtube")
        elif "video" in item.lower() or "mp4" in item.lower():
            missing_types.add("video")
    
    # 获取期数文件夹的相对路径（用于命令）
    folder_path = episode_dir.relative_to(REPO_ROOT) if episode_dir.is_relative_to(REPO_ROOT) else episode_dir
    
    if "cover" in missing_types or "playlist" in missing_types:
        suggestions.append(f"生成封面和歌单：python scripts/local_picker/create_mixtape.py --episode-id {id_str} --no-remix --no-video")
    
    playlist_path = episode_dir / f"{id_str}_playlist.csv"
    if playlist_path.exists():
        playlist_rel = playlist_path.relative_to(REPO_ROOT) if playlist_path.is_relative_to(REPO_ROOT) else playlist_path
        
        if "audio" in missing_types:
            suggestions.append(f"生成混音音频：python scripts/local_picker/remix_mixtape.py --playlist {playlist_rel}")
        
        if "youtube" in missing_types:
            # 尝试从排播表获取标题
            try:
                from schedule_master import ScheduleMaster
                from utils import extract_title_from_playlist
                schedule = ScheduleMaster.load()
                ep = schedule.get_episode(id_str) if schedule else None
                title = ep.get("title") if ep else extract_title_from_playlist(playlist_path) or "[标题]"
            except:
                title = "[标题]"
            suggestions.append(f"生成YouTube资源：python scripts/local_picker/generate_youtube_assets.py --playlist {playlist_rel} --title \"{title}\" --output {folder_path}")
        
        if "video" in missing_types:
            suggestions.append(f"生成视频：python scripts/local_picker/create_mixtape.py --episode-id {id_str} --no-youtube")
    else:
        # 如果没有playlist，先需要生成playlist
        suggestions.append(f"⚠️  请先生成歌单文件（包含在封面生成命令中）")
    
    if not suggestions:
        suggestions.append("所有必需文件已存在")
    
    return suggestions


def check_all_episodes(output_dir: Path = None, demo_only: bool = False):
    """检查所有期数文件夹"""
    if output_dir is None:
        output_dir = REPO_ROOT / "output"
    
    if demo_only:
        output_dir = output_dir / "DEMO"
    
    if not output_dir.exists():
        print(f"❌ 输出目录不存在: {output_dir}")
        return
    
    # 加载排播表
    try:
        schedule = ScheduleMaster.load()
        if not schedule:
            print("⚠️  排播表不存在，将仅检查文件完整性")
            schedule = None
    except Exception as e:
        print(f"⚠️  加载排播表失败: {e}，将仅检查文件完整性")
        schedule = None
    
    console = Console() if RICH_AVAILABLE else None
    
    # 查找所有期数文件夹
    episode_dirs = []
    for subdir in output_dir.iterdir():
        if subdir.is_dir():
            # 跳过非期数文件夹
            ep_id = extract_episode_id_from_folder(subdir)
            if ep_id:
                episode_dirs.append((subdir, ep_id))
            elif demo_only and subdir.name.startswith("2025-"):
                # DEMO模式下，尝试从文件夹名提取
                ep_id = extract_episode_id_from_folder(subdir)
                if ep_id:
                    episode_dirs.append((subdir, ep_id))
    
    if not episode_dirs:
        print(f"📁 未找到期数文件夹: {output_dir}")
        return
    
    episode_dirs.sort(key=lambda x: x[1])  # 按ID排序
    
    print(f"🔍 扫描 {len(episode_dirs)} 个期数文件夹...")
    print("=" * 70)
    
    complete_count = 0
    incomplete_count = 0
    results = []
    
    for episode_dir, id_str in episode_dirs:
        is_complete, missing = check_episode_folder(episode_dir, id_str)
        
        # 获取期数信息
        ep = schedule.get_episode(id_str) if schedule else None
        title = ep.get("title") if ep else episode_dir.name
        
        if is_complete:
            complete_count += 1
            status_icon = "✅"
        else:
            incomplete_count += 1
            status_icon = "⚠️ "
        
        results.append({
            "id": id_str,
            "title": title,
            "folder": episode_dir.name,
            "folder_path": episode_dir,
            "complete": is_complete,
            "missing": missing,
            "suggestions": generate_fix_suggestions(id_str, missing, episode_dir) if not is_complete else [],
        })
    
    # 显示结果
    if console:
        # 使用 Rich 显示
        table = Table(title="期数文件完整性检查", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan")
        table.add_column("标题", style="magenta")
        table.add_column("状态", justify="center")
        table.add_column("缺失文件", style="yellow")
        
        for result in results:
            status = "✅ 完整" if result["complete"] else "⚠️  不完整"
            missing_text = ""
            if not result["complete"]:
                missing_list = []
                if result["missing"]["必需"]:
                    missing_list.extend(result["missing"]["必需"])
                if result["missing"]["推荐"]:
                    missing_list.extend(result["missing"]["推荐"])
                missing_text = ", ".join(missing_list[:3])
                if len(missing_list) > 3:
                    missing_text += f" (+{len(missing_list)-3}个)"
            
            table.add_row(
                result["id"],
                result["title"][:40] + ("..." if len(result["title"]) > 40 else ""),
                status,
                missing_text
            )
        
        console.print(table)
    else:
        # 简单文本显示
        print(f"\n{'ID':<12} {'标题':<35} {'状态':<10} {'缺失文件'}")
        print("-" * 70)
        for result in results:
            status = "✅" if result["complete"] else "⚠️ "
            missing_text = ""
            if not result["complete"]:
                missing_list = []
                if result["missing"]["必需"]:
                    missing_list.extend(result["missing"]["必需"])
                if result["missing"]["推荐"]:
                    missing_list.extend(result["missing"]["推荐"])
                missing_text = ", ".join(missing_list[:2])
            
            print(f"{result['id']:<12} {result['title'][:33]:<35} {status:<10} {missing_text}")
    
    # 显示统计
    print("\n" + "=" * 70)
    print(f"📊 统计:")
    print(f"   完整: {complete_count} 个")
    print(f"   不完整: {incomplete_count} 个")
    print(f"   总计: {len(results)} 个")
    
    # 显示不完整的期数详情和建议
    incomplete_results = [r for r in results if not r["complete"]]
    if incomplete_results:
        print("\n" + "=" * 70)
        print(f"⚠️  不完整的期数 ({len(incomplete_results)} 个):\n")
        
        for result in incomplete_results:
            print(f"\n📁 {result['id']} - {result['title']}")
            print(f"   文件夹: {result['folder']}")
            
            if result["missing"]["必需"]:
                print(f"   ❌ 缺失必需文件:")
                for item in result["missing"]["必需"]:
                    print(f"      - {item}")
            
            if result["missing"]["推荐"]:
                print(f"   ⚠️  缺失推荐文件:")
                for item in result["missing"]["推荐"]:
                    print(f"      - {item}")
            
            if result["suggestions"]:
                print(f"   💡 修复建议:")
                for suggestion in result["suggestions"]:
                    print(f"      {suggestion}")


def check_single_episode(episode_id: str, output_dir: Path = None):
    """检查单个期数文件夹"""
    if output_dir is None:
        output_dir = REPO_ROOT / "output"
    
    if not output_dir.exists():
        print(f"❌ 输出目录不存在: {output_dir}")
        return
    
    # 尝试从排播表获取期数信息
    schedule = None
    try:
        schedule = ScheduleMaster.load()
    except:
        pass
    
    # 查找期数文件夹
    episode_dir = None
    # 方法1: 从排播表获取日期和标题
    if schedule:
        ep = schedule.get_episode(episode_id)
        if ep:
            schedule_date = ep.get("schedule_date")
            title = ep.get("title", "")
            if schedule_date:
                # 格式化日期为 YYYY-MM-DD
                from datetime import datetime
                try:
                    if isinstance(schedule_date, str):
                        date_obj = datetime.fromisoformat(schedule_date)
                    else:
                        date_obj = schedule_date
                    date_str = date_obj.strftime("%Y-%m-%d")
                    # 尝试构建文件夹名
                    folder_name = f"{date_str}_{title.replace('/', '-').replace(' ', '_')[:30]}"
                    potential_dir = output_dir / folder_name
                    if potential_dir.exists():
                        episode_dir = potential_dir
                except:
                    pass
    
    # 方法2: 扫描所有文件夹查找匹配的ID
    if not episode_dir:
        for subdir in output_dir.iterdir():
            if subdir.is_dir():
                ep_id = extract_episode_id_from_folder(subdir)
                if ep_id == episode_id:
                    episode_dir = subdir
                    break
    
    if not episode_dir:
        print(f"❌ 未找到期数文件夹 (ID: {episode_id})")
        print(f"   查找目录: {output_dir}")
        if schedule:
            ep = schedule.get_episode(episode_id)
            if ep:
                print(f"   排播日期: {ep.get('schedule_date', '未知')}")
                print(f"   标题: {ep.get('title', '未知')}")
        return
    
    # 检查文件夹
    is_complete, missing = check_episode_folder(episode_dir, episode_id)
    
    # 获取标题
    title = "未知标题"
    if schedule:
        ep = schedule.get_episode(episode_id)
        if ep:
            title = ep.get("title", "未知标题")
    
    # 生成修复建议
    suggestions = generate_fix_suggestions(episode_id, missing, episode_dir)
    
    # 显示结果
    console = Console() if RICH_AVAILABLE else None
    
    if console:
        from rich.panel import Panel
        status = "✅ 完整" if is_complete else "⚠️  不完整"
        missing_text = ""
        if not is_complete:
            missing_list = []
            if missing["必需"]:
                missing_list.extend([item.split(":")[-1].strip() for item in missing["必需"]])
            if missing["推荐"]:
                missing_list.extend([item.split(":")[-1].strip() for item in missing["推荐"]])
            missing_text = ", ".join(missing_list[:5])
            if len(missing_list) > 5:
                missing_text += f" (+{len(missing_list)-5}个)"
        
        panel_content = f"[bold]期数:[/bold] {episode_id}\n"
        panel_content += f"[bold]标题:[/bold] {title}\n"
        panel_content += f"[bold]状态:[/bold] {status}\n"
        if missing_text:
            panel_content += f"[bold]缺失文件:[/bold] {missing_text}"
        
        console.print(Panel(
            panel_content,
            title=f"📋 文件检查结果",
            border_style="green" if is_complete else "yellow"
        ))
        
        if suggestions:
            console.print("\n[bold]💡 修复建议:[/bold]")
            for suggestion in suggestions:
                console.print(f"  • {suggestion}")
    else:
        print(f"\n{'='*70}")
        print(f"期数: {episode_id}")
        print(f"标题: {title}")
        print(f"文件夹: {episode_dir}")
        print(f"状态: {'✅ 完整' if is_complete else '⚠️  不完整'}")
        if not is_complete:
            print("\n缺失文件:")
            if missing["必需"]:
                print("  必需:")
                for item in missing["必需"]:
                    print(f"    - {item}")
            if missing["推荐"]:
                print("  推荐:")
                for item in missing["推荐"]:
                    print(f"    - {item}")
        if suggestions:
            print("\n修复建议:")
            for suggestion in suggestions:
                print(f"  • {suggestion}")
        print(f"{'='*70}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="检查期数文件夹的文件完整性")
    parser.add_argument(
        "--output",
        type=Path,
        help="输出目录（默认: output）"
    )
    parser.add_argument(
        "--episode-id",
        type=str,
        help="检查指定期数ID (YYYYMMDD格式)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="仅检查DEMO文件夹（已弃用）"
    )
    
    args = parser.parse_args()
    
    output_dir = args.output or (REPO_ROOT / "output")
    
    if args.episode_id:
        # 检查单个期数
        check_single_episode(args.episode_id, output_dir)
    else:
        # 检查所有期数
        check_all_episodes(output_dir, demo_only=args.demo)


if __name__ == "__main__":
    main()

