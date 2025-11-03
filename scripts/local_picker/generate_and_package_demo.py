#!/usr/bin/env python3
# coding: utf-8
"""
为DEMO期数生成title、description、SRT，并打包到每期文件夹

此脚本专门用于处理手动创建的DEMO内容，复用create_mixtape.py的打包逻辑。
只做两件事：
1. 为每期生成YouTube资源（SRT、title、description）- 如果缺失
2. 将文件打包到各自的期数文件夹

用法：
    python scripts/local_picker/generate_and_package_demo.py
"""
from __future__ import annotations

import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional
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
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def generate_and_package_demo():
    """为所有DEMO期数生成资源并打包"""
    demo_dir = REPO_ROOT / "output" / "DEMO"
    
    if not demo_dir.exists():
        print(f"❌ DEMO文件夹不存在: {demo_dir}")
        return
    
    # 加载排播表
    try:
        schedule = ScheduleMaster.load()
        if not schedule:
            print("❌ 无法加载排播表")
            return
    except Exception as e:
        print(f"❌ 加载排播表失败: {e}")
        return
    
    # 查找所有歌单文件（DEMO目录和子文件夹）
    playlist_files = []
    playlist_files.extend(demo_dir.glob("*_playlist.csv"))
    for subdir in demo_dir.iterdir():
        if subdir.is_dir() and subdir.name.startswith("2025-"):
            playlist_files.extend(subdir.glob("*_playlist.csv"))
    
    playlist_files = sorted(set(playlist_files))
    
    if not playlist_files:
        print(f"❌ 未找到歌单文件")
        return
    
    print(f"📋 找到 {len(playlist_files)} 期歌单文件")
    print("=" * 70)
    
    # 使用虚拟环境的Python
    python_exe = sys.executable
    venv_python = REPO_ROOT / ".venv" / "bin" / "python3"
    if venv_python.exists():
        python_exe = str(venv_python)
    
    youtube_script = REPO_ROOT / "scripts" / "local_picker" / "generate_youtube_assets.py"
    console = Console() if RICH_AVAILABLE else None
    
    success_count = 0
    failed_count = 0
    
    for i, playlist_path in enumerate(playlist_files, 1):
        id_str = playlist_path.stem.replace("_playlist", "")
        ep = schedule.get_episode(id_str)
        
        if not ep:
            print(f"\n[{i}/{len(playlist_files)}] ⚠️  跳过 {id_str}：排播表中未找到")
            failed_count += 1
            continue
        
        title = ep.get("title") or extract_title_from_playlist(playlist_path)
        if not title:
            print(f"\n[{i}/{len(playlist_files)}] ⚠️  跳过 {id_str}：无法获取标题")
            failed_count += 1
            continue
        
        schedule_date_str = ep.get("schedule_date", "")
        try:
            schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
        except:
            try:
                schedule_date = datetime.strptime(id_str, "%Y%m%d")
            except:
                print(f"\n[{i}/{len(playlist_files)}] ⚠️  跳过 {id_str}：无法解析日期")
                failed_count += 1
                continue
        
        print(f"\n[{i}/{len(playlist_files)}] 处理期数: {id_str} - {title}")
        print("-" * 70)
        
        final_dir = get_final_output_dir(schedule_date, title)
        playlist_path = playlist_path.resolve()
        
        # 1. 生成YouTube资源（复用create_mixtape.py的逻辑）
        srt_path = final_dir / f"{id_str}_youtube.srt"
        title_path = final_dir / f"{id_str}_youtube_title.txt"
        desc_path = final_dir / f"{id_str}_youtube_description.txt"
        
        if not (srt_path.exists() and title_path.exists() and desc_path.exists()):
            print(f"  [生成] YouTube资源...")
            if console:
                with console.status(f"[cyan]正在生成YouTube资源...", spinner="dots"):
                    try:
                        import os
                        cmd = [
                            python_exe,
                            str(youtube_script),
                            "--playlist", str(playlist_path),
                            "--title", title,
                            "--output", str(final_dir),
                        ]
                        if os.environ.get("OPENAI_API_KEY"):
                            cmd.extend(["--openai-api-key", os.environ.get("OPENAI_API_KEY")])
                        if os.environ.get("OPENAI_BASE_URL"):
                            cmd.extend(["--openai-base-url", os.environ.get("OPENAI_BASE_URL")])
                        
                        result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120)
                        if result.returncode == 0:
                            print(f"  ✓ YouTube资源已生成")
                        else:
                            error_msg = result.stderr[:200] if result.stderr else result.stdout[:200] if result.stdout else '未知错误'
                            print(f"  ⚠️  生成失败: {error_msg}")
                    except Exception as e:
                        print(f"  ⚠️  异常: {e}")
            else:
                try:
                    import os
                    cmd = [
                        python_exe,
                        str(youtube_script),
                        "--playlist", str(playlist_path),
                        "--title", title,
                        "--output", str(final_dir),
                    ]
                    if os.environ.get("OPENAI_API_KEY"):
                        cmd.extend(["--openai-api-key", os.environ.get("OPENAI_API_KEY")])
                    if os.environ.get("OPENAI_BASE_URL"):
                        cmd.extend(["--openai-base-url", os.environ.get("OPENAI_BASE_URL")])
                    
                    result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        print(f"  ✓ YouTube资源已生成")
                    else:
                        error_msg = result.stderr[:200] if result.stderr else result.stdout[:200] if result.stdout else '未知错误'
                        print(f"  ⚠️  生成失败: {error_msg}")
                except Exception as e:
                    print(f"  ⚠️  异常: {e}")
        else:
            print(f"  ✓ YouTube资源已存在")
        
        # 2. 打包文件（复用create_mixtape.py的打包逻辑，但适配DEMO目录）
        final_dir.mkdir(parents=True, exist_ok=True)
        
        # 收集需要移动的文件（从DEMO目录）
        files_to_move = []
        
        # 核心文件
        for pattern in [
            f"{id_str}_cover.png",
            f"{id_str}_playlist.csv",
            f"{id_str}_full_mix.mp3",
            f"{id_str}_playlist_full_mix.mp3",
            f"{id_str}_youtube.mp4",
        ]:
            src = demo_dir / pattern
            if src.exists():
                files_to_move.append(src)
        
        # YouTube资源文件
        for pattern in [
            f"{id_str}_youtube*.srt",
            f"{id_str}_youtube*.txt",
            f"{id_str}_youtube*.csv",
        ]:
            files_to_move.extend(list(demo_dir.glob(pattern)))
        
        # 移动文件到最终文件夹
        moved_count = 0
        for src_file in files_to_move:
            dst_file = final_dir / src_file.name
            if src_file.parent == final_dir:
                continue  # 已在目标文件夹
            if not dst_file.exists():
                shutil.move(str(src_file), str(dst_file))
                moved_count += 1
        
        if moved_count > 0:
            print(f"  ✓ 已打包 {moved_count} 个文件到: {final_dir.name}")
        else:
            print(f"  ℹ️  所有文件已在文件夹中")
        
        success_count += 1
    
    print("\n" + "=" * 70)
    print(f"✅ 处理完成：成功 {success_count} 期，失败 {failed_count} 期")
    print("=" * 70)


if __name__ == "__main__":
    generate_and_package_demo()
