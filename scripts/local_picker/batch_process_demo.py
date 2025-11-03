#!/usr/bin/env python3
# coding: utf-8
"""
批量处理DEMO文件夹中的歌单和封面，生成所有剩余素材

功能：
1. 为每期生成full mix音频
2. 生成SRT字幕和YouTube资源
3. 生成视频

用法：
    python scripts/local_picker/batch_process_demo.py
"""
from __future__ import annotations

import sys
import subprocess
import glob
import re
from pathlib import Path
from typing import List, Tuple, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from rich.console import Console  # pyright: ignore[reportMissingImports]
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn  # pyright: ignore[reportMissingImports]
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from utils import extract_title_from_playlist
except ImportError as e:
    print(f"❌ 无法导入 utils 模块: {e}")
    sys.exit(1)


def process_demo_episodes(demo_dir: Path = None):
    """批量处理DEMO文件夹中的所有期数"""
    if demo_dir is None:
        demo_dir = REPO_ROOT / "output" / "DEMO"
    
    if not demo_dir.exists():
        print(f"❌ DEMO文件夹不存在: {demo_dir}")
        return
    
    # 查找所有歌单文件
    playlist_files = sorted(demo_dir.glob("*_playlist.csv"))
    
    if not playlist_files:
        print(f"❌ 未找到歌单文件: {demo_dir}")
        return
    
    print(f"📋 找到 {len(playlist_files)} 期歌单文件")
    print("=" * 60)
    
    # 确定使用的Python解释器（优先使用虚拟环境）
    python_exe = sys.executable
    venv_python = REPO_ROOT / ".venv" / "bin" / "python3"
    if venv_python.exists():
        python_exe = str(venv_python)
        print(f"🐍 使用虚拟环境: {python_exe}")
    
    # 导入必要的脚本路径
    remix_script = REPO_ROOT / "scripts" / "local_picker" / "remix_mixtape.py"
    youtube_script = REPO_ROOT / "scripts" / "local_picker" / "generate_youtube_assets.py"
    
    if not remix_script.exists():
        print(f"❌ 未找到混音脚本: {remix_script}")
        return
    
    if not youtube_script.exists():
        print(f"❌ 未找到YouTube资源脚本: {youtube_script}")
        return
    
    # 准备进度显示
    console = Console() if RICH_AVAILABLE else None
    
    # 处理每一期
    success_count = 0
    failed_count = 0
    
    for i, playlist_path in enumerate(playlist_files, 1):
        # 从文件名提取ID
        id_str = playlist_path.stem.replace("_playlist", "")
        cover_path = demo_dir / f"{id_str}_cover.png"
        
        if not cover_path.exists():
            print(f"[{i}/{len(playlist_files)}] ⚠️  跳过 {id_str}：封面文件不存在")
            failed_count += 1
            continue
        
        print(f"\n[{i}/{len(playlist_files)}] 处理期数: {id_str}")
        print("-" * 60)
        
        # 1. 生成full mix音频
        full_mix_path = demo_dir / f"{id_str}_full_mix.mp3"
        if full_mix_path.exists():
            print(f"  ✓ full_mix已存在，跳过: {full_mix_path.name}")
        else:
            if console:
                with console.status(f"[cyan]正在生成full mix音频...", spinner="dots"):
                    try:
                        result = subprocess.run([
                            python_exe,
                            str(remix_script),
                            "--playlist", str(playlist_path),
                        ], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300)
                        if result.returncode == 0:
                            # 检查文件是否生成（可能在output根目录）
                            if not full_mix_path.exists():
                                # 查找output根目录中的文件
                                root_full_mix = REPO_ROOT / "output" / f"{id_str}_full_mix.mp3"
                                if root_full_mix.exists():
                                    # 移动到DEMO目录
                                    import shutil
                                    shutil.move(str(root_full_mix), str(full_mix_path))
                                    print(f"  ✓ full_mix已生成并移动到DEMO目录")
                                else:
                                    print(f"  ⚠️  full_mix生成可能失败，文件未找到")
                            else:
                                print(f"  ✓ full_mix已生成")
                        else:
                            print(f"  ❌ full_mix生成失败: {result.stderr}")
                            failed_count += 1
                            continue
                    except Exception as e:
                        print(f"  ❌ full_mix生成异常: {e}")
                        failed_count += 1
                        continue
            else:
                print(f"  [生成] full_mix音频...")
                try:
                    result = subprocess.run([
                        python_exe,
                        str(remix_script),
                        "--playlist", str(playlist_path),
                    ], cwd=str(REPO_ROOT), capture_output=False, timeout=300)
                    if result.returncode == 0:
                        # 检查并移动文件
                        if not full_mix_path.exists():
                            root_full_mix = REPO_ROOT / "output" / f"{id_str}_full_mix.mp3"
                            if root_full_mix.exists():
                                import shutil
                                shutil.move(str(root_full_mix), str(full_mix_path))
                        print(f"  ✓ full_mix已生成")
                    else:
                        print(f"  ❌ full_mix生成失败")
                        failed_count += 1
                        continue
                except Exception as e:
                    print(f"  ❌ full_mix生成异常: {e}")
                    failed_count += 1
                    continue
        
        # 2. 生成YouTube资源（SRT、标题、描述）
        # 先从歌单中提取标题
        title = extract_title_from_playlist(playlist_path)
        if not title:
            print(f"  ⚠️  无法从歌单提取标题，跳过YouTube资源生成")
        else:
            srt_path = demo_dir / f"{id_str}_youtube.srt"
            if srt_path.exists():
                print(f"  ✓ YouTube资源已存在，跳过")
            else:
                if console:
                    with console.status(f"[cyan]正在生成YouTube资源...", spinner="dots"):
                        try:
                            cmd = [
                                python_exe,
                                str(youtube_script),
                                "--playlist", str(playlist_path),
                                "--title", title,
                                "--output", str(demo_dir),
                            ]
                            # 添加API配置（如果环境变量中有）
                            import os
                            if os.environ.get("OPENAI_API_KEY"):
                                cmd.extend(["--openai-api-key", os.environ.get("OPENAI_API_KEY")])
                            if os.environ.get("OPENAI_BASE_URL"):
                                cmd.extend(["--openai-base-url", os.environ.get("OPENAI_BASE_URL")])
                            
                            result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120)
                            if result.returncode == 0:
                                print(f"  ✓ YouTube资源已生成")
                            else:
                                print(f"  ⚠️  YouTube资源生成失败: {result.stderr[:200]}")
                        except Exception as e:
                            print(f"  ⚠️  YouTube资源生成异常: {e}")
                else:
                    print(f"  [生成] YouTube资源...")
                    try:
                        cmd = [
                            python_exe,
                            str(youtube_script),
                            "--playlist", str(playlist_path),
                            "--title", title,
                            "--output", str(demo_dir),
                        ]
                        import os
                        if os.environ.get("OPENAI_API_KEY"):
                            cmd.extend(["--openai-api-key", os.environ.get("OPENAI_API_KEY")])
                        if os.environ.get("OPENAI_BASE_URL"):
                            cmd.extend(["--openai-base-url", os.environ.get("OPENAI_BASE_URL")])
                        
                        result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=False, timeout=120)
                        if result.returncode == 0:
                            print(f"  ✓ YouTube资源已生成")
                        else:
                            print(f"  ⚠️  YouTube资源生成失败")
                    except Exception as e:
                        print(f"  ⚠️  YouTube资源生成异常: {e}")
        
        # 3. 生成视频
        video_path = demo_dir / f"{id_str}_youtube.mp4"
        if video_path.exists():
            print(f"  ✓ 视频已存在，跳过: {video_path.name}")
        else:
            # 确保full_mix音频存在
            if not full_mix_path.exists():
                print(f"  ⚠️  full_mix音频不存在，跳过视频生成")
                failed_count += 1
                continue
            
            if console:
                with console.status(f"[cyan]正在生成视频...", spinner="dots"):
                    try:
                        # 使用ffmpeg生成视频
                        cmd = [
                            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                            "-loop", "1", "-i", str(cover_path),
                            "-i", str(full_mix_path),
                            "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,fps=1:round=down",
                            "-c:v", "h264_videotoolbox", "-b:v", "2M", "-maxrate", "4M", "-bufsize", "6M",
                            "-vsync", "vfr", "-fps_mode", "passthrough",
                            "-c:a", "aac", "-b:a", "256k",
                            "-shortest",
                            "-movflags", "+faststart",
                            str(video_path),
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                        if result.returncode == 0:
                            print(f"  ✓ 视频已生成: {video_path.name}")
                        else:
                            # 回退到libx264
                            cmd = [
                                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                                "-loop", "1", "-i", str(cover_path),
                                "-i", str(full_mix_path),
                                "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,fps=1:round=down",
                                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                                "-vsync", "vfr", "-fps_mode", "passthrough",
                                "-c:a", "aac", "-b:a", "256k",
                                "-shortest",
                                "-movflags", "+faststart",
                                str(video_path),
                            ]
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                            if result.returncode == 0:
                                print(f"  ✓ 视频已生成（使用libx264）: {video_path.name}")
                            else:
                                print(f"  ❌ 视频生成失败: {result.stderr[:200] if result.stderr else '未知错误'}")
                                failed_count += 1
                                continue
                    except Exception as e:
                        print(f"  ❌ 视频生成异常: {e}")
                        failed_count += 1
                        continue
            else:
                print(f"  [生成] 视频...")
                try:
                    cmd = [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-loop", "1", "-i", str(cover_path),
                        "-i", str(full_mix_path),
                        "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,fps=1:round=down",
                        "-c:v", "h264_videotoolbox", "-b:v", "2M", "-maxrate", "4M", "-bufsize", "6M",
                        "-vsync", "vfr", "-fps_mode", "passthrough",
                        "-c:a", "aac", "-b:a", "256k",
                        "-shortest",
                        "-movflags", "+faststart",
                        str(video_path),
                    ]
                    result = subprocess.run(cmd, capture_output=False, timeout=600)
                    if result.returncode != 0:
                        # 回退到libx264
                        cmd = [
                            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                            "-loop", "1", "-i", str(cover_path),
                            "-i", str(full_mix_path),
                            "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,fps=1:round=down",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                            "-vsync", "vfr", "-fps_mode", "passthrough",
                            "-c:a", "aac", "-b:a", "256k",
                            "-shortest",
                            "-movflags", "+faststart",
                            str(video_path),
                        ]
                        result = subprocess.run(cmd, capture_output=False, timeout=600)
                        if result.returncode == 0:
                            print(f"  ✓ 视频已生成（使用libx264）")
                        else:
                            print(f"  ❌ 视频生成失败")
                            failed_count += 1
                            continue
                    else:
                        print(f"  ✓ 视频已生成")
                except Exception as e:
                    print(f"  ❌ 视频生成异常: {e}")
                    failed_count += 1
                    continue
        
        success_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ 处理完成：成功 {success_count} 期，失败 {failed_count} 期")
    print("=" * 60)


if __name__ == "__main__":
    process_demo_episodes()

