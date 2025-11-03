#!/usr/bin/env python3
# coding: utf-8
"""
完成DEMO期数的所有素材，打包到每期文件夹，更新排播表状态

功能：
1. 检查10期DEMO期数的完整性
2. 补齐缺少的内容（SRT、YouTube资源、MP4视频）
3. 打包到每期文件夹（output/{YYYY-MM-DD}_{标题}/）
4. 更新排播表状态为"已完成"
5. 同步图库和歌库信息

用法：
    python scripts/local_picker/finalize_demo_episodes.py
"""
from __future__ import annotations

import sys
import subprocess
import shutil
import glob
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster
    from episode_status import STATUS_已完成, normalize_status
    # sync_resources已过时，现在使用schedule.sync_images_from_assignments()
    from utils import extract_title_from_playlist, get_final_output_dir
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    sys.exit(1)

try:
    from rich.console import Console  # pyright: ignore[reportMissingImports]
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn  # pyright: ignore[reportMissingImports]
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def check_episode_files(demo_dir: Path, id_str: str, title: str) -> Tuple[bool, List[str]]:
    """检查期数文件完整性，返回(是否完整, 缺少的文件列表)"""
    missing = []
    
    # 必需文件
    required_files = {
        "cover": demo_dir / f"{id_str}_cover.png",
        "playlist": demo_dir / f"{id_str}_playlist.csv",
    }
    
    # 检查full_mix的两种可能命名
    full_mix_v1 = demo_dir / f"{id_str}_full_mix.mp3"
    full_mix_v2 = demo_dir / f"{id_str}_playlist_full_mix.mp3"
    full_mix_path = full_mix_v1 if full_mix_v1.exists() else full_mix_v2
    if full_mix_v2.exists() and not full_mix_v1.exists():
        # 重命名为标准格式
        shutil.move(str(full_mix_v2), str(full_mix_v1))
        full_mix_path = full_mix_v1
    required_files["full_mix"] = full_mix_path
    
    for key, file_path in required_files.items():
        if not file_path.exists():
            missing.append(f"{key}: {file_path.name}")
    
    # 可选但推荐的文件
    optional_files = {
        "srt": demo_dir / f"{id_str}_youtube.srt",
        "youtube_title": demo_dir / f"{id_str}_youtube_title.txt",
        "youtube_desc": demo_dir / f"{id_str}_youtube_description.txt",
        "video": demo_dir / f"{id_str}_youtube.mp4",
    }
    
    for key, file_path in optional_files.items():
        if not file_path.exists():
            missing.append(f"{key}: {file_path.name}")
    
    return len(missing) == 0, missing


def finalize_demo_episodes():
    """完成所有DEMO期数的处理"""
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
    
    # 查找所有歌单文件
    playlist_files = sorted(demo_dir.glob("*_playlist.csv"))
    
    if not playlist_files:
        print(f"❌ 未找到歌单文件: {demo_dir}")
        return
    
    print(f"📋 找到 {len(playlist_files)} 期歌单文件")
    print("=" * 70)
    
    # 确定使用的Python解释器
    python_exe = sys.executable
    venv_python = REPO_ROOT / ".venv" / "bin" / "python3"
    if venv_python.exists():
        python_exe = str(venv_python)
        print(f"🐍 使用虚拟环境: {python_exe}")
    
    # 脚本路径
    remix_script = REPO_ROOT / "scripts" / "local_picker" / "remix_mixtape.py"
    youtube_script = REPO_ROOT / "scripts" / "local_picker" / "generate_youtube_assets.py"
    create_video_script = REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"
    
    console = Console() if RICH_AVAILABLE else None
    
    # 处理每一期
    success_count = 0
    failed_count = 0
    updated_schedule_count = 0
    
    for i, playlist_path in enumerate(playlist_files, 1):
        # 从文件名提取ID
        id_str = playlist_path.stem.replace("_playlist", "")
        
        # 从排播表获取期数信息
        ep = schedule.get_episode(id_str)
        if not ep:
            print(f"\n[{i}/{len(playlist_files)}] ⚠️  跳过 {id_str}：排播表中未找到")
            failed_count += 1
            continue
        
        # 获取标题和日期
        title = ep.get("title") or extract_title_from_playlist(playlist_path)
        if not title:
            print(f"\n[{i}/{len(playlist_files)}] ⚠️  跳过 {id_str}：无法获取标题")
            failed_count += 1
            continue
        
        # 获取日期
        schedule_date_str = ep.get("schedule_date", "")
        try:
            schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
        except:
            # 尝试从ID解析
            try:
                schedule_date = datetime.strptime(id_str, "%Y%m%d")
            except:
                print(f"\n[{i}/{len(playlist_files)}] ⚠️  跳过 {id_str}：无法解析日期")
                failed_count += 1
                continue
        
        print(f"\n[{i}/{len(playlist_files)}] 处理期数: {id_str} - {title}")
        print("-" * 70)
        
        # 检查文件完整性
        is_complete, missing = check_episode_files(demo_dir, id_str, title)
        if is_complete:
            print(f"  ✓ 所有文件已完整")
        else:
            print(f"  ⚠️  缺少文件: {', '.join(missing)}")
        
        cover_path = demo_dir / f"{id_str}_cover.png"
        full_mix_v1 = demo_dir / f"{id_str}_full_mix.mp3"
        full_mix_v2 = demo_dir / f"{id_str}_playlist_full_mix.mp3"
        # 检查两种可能的文件名
        if full_mix_v1.exists():
            full_mix_path = full_mix_v1
        elif full_mix_v2.exists():
            full_mix_path = full_mix_v2
            # 标准化文件名：重命名为标准格式
            shutil.move(str(full_mix_v2), str(full_mix_v1))
            full_mix_path = full_mix_v1
        else:
            full_mix_path = full_mix_v1  # 使用标准格式作为目标路径
        
        video_path = demo_dir / f"{id_str}_youtube.mp4"
        
        # 1. 生成full mix（如果缺失）
        if not full_mix_path.exists():
            print(f"  [生成] full_mix音频...")
            if console:
                with console.status(f"[cyan]正在生成full mix...", spinner="dots"):
                    try:
                        result = subprocess.run([
                            python_exe,
                            str(remix_script),
                            "--playlist", str(playlist_path),
                        ], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300)
                        if result.returncode == 0:
                            # 检查并移动文件（可能在output根目录或DEMO目录）
                            root_full_mix = REPO_ROOT / "output" / f"{id_str}_full_mix.mp3"
                            root_playlist_full_mix = REPO_ROOT / "output" / f"{id_str}_playlist_full_mix.mp3"
                            if root_full_mix.exists():
                                shutil.move(str(root_full_mix), str(full_mix_path))
                            elif root_playlist_full_mix.exists():
                                shutil.move(str(root_playlist_full_mix), str(full_mix_path))
                            elif full_mix_path.exists():
                                pass  # 文件已经在正确位置
                            print(f"  ✓ full_mix已生成")
                        else:
                            print(f"  ❌ full_mix生成失败: {result.stderr[:200] if result.stderr else '未知错误'}")
                            failed_count += 1
                            continue
                    except Exception as e:
                        print(f"  ❌ full_mix生成异常: {e}")
                        failed_count += 1
                        continue
            else:
                try:
                    result = subprocess.run([
                        python_exe,
                        str(remix_script),
                        "--playlist", str(playlist_path),
                    ], cwd=str(REPO_ROOT), timeout=300)
                    if result.returncode == 0:
                        root_full_mix = REPO_ROOT / "output" / f"{id_str}_full_mix.mp3"
                        root_playlist_full_mix = REPO_ROOT / "output" / f"{id_str}_playlist_full_mix.mp3"
                        if root_full_mix.exists():
                            shutil.move(str(root_full_mix), str(full_mix_path))
                        elif root_playlist_full_mix.exists():
                            shutil.move(str(root_playlist_full_mix), str(full_mix_path))
                        elif full_mix_path.exists():
                            pass  # 文件已经在正确位置
                        print(f"  ✓ full_mix已生成")
                    else:
                        print(f"  ❌ full_mix生成失败")
                        failed_count += 1
                        continue
                except Exception as e:
                    print(f"  ❌ full_mix生成异常: {e}")
                    failed_count += 1
                    continue
        
        # 2. 生成YouTube资源（如果缺失）
        srt_path = demo_dir / f"{id_str}_youtube.srt"
        if not srt_path.exists():
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
                            "--output", str(demo_dir),
                        ]
                        if os.environ.get("OPENAI_API_KEY"):
                            cmd.extend(["--openai-api-key", os.environ.get("OPENAI_API_KEY")])
                        if os.environ.get("OPENAI_BASE_URL"):
                            cmd.extend(["--openai-base-url", os.environ.get("OPENAI_BASE_URL")])
                        
                        result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120)
                        if result.returncode == 0:
                            print(f"  ✓ YouTube资源已生成")
                        else:
                            print(f"  ⚠️  YouTube资源生成失败: {result.stderr[:200] if result.stderr else '未知错误'}")
                    except Exception as e:
                        print(f"  ⚠️  YouTube资源生成异常: {e}")
            else:
                try:
                    import os
                    cmd = [
                        python_exe,
                        str(youtube_script),
                        "--playlist", str(playlist_path),
                        "--title", title,
                        "--output", str(demo_dir),
                    ]
                    if os.environ.get("OPENAI_API_KEY"):
                        cmd.extend(["--openai-api-key", os.environ.get("OPENAI_API_KEY")])
                    if os.environ.get("OPENAI_BASE_URL"):
                        cmd.extend(["--openai-base-url", os.environ.get("OPENAI_BASE_URL")])
                    
                    result = subprocess.run(cmd, cwd=str(REPO_ROOT), timeout=120)
                    if result.returncode == 0:
                        print(f"  ✓ YouTube资源已生成")
                    else:
                        print(f"  ⚠️  YouTube资源生成失败")
                except Exception as e:
                    print(f"  ⚠️  YouTube资源生成异常: {e}")
        
        # 3. 生成视频（如果缺失）
        if not video_path.exists():
            if not full_mix_path.exists() or not cover_path.exists():
                print(f"  ⚠️  缺少cover或full_mix，跳过视频生成")
                failed_count += 1
                continue
            
            print(f"  [生成] 视频...")
            if console:
                with console.status(f"[cyan]正在生成视频...", spinner="dots"):
                    try:
                        # 尝试h264_videotoolbox
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
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                        if result.returncode == 0:
                            print(f"  ✓ 视频已生成: {video_path.name}")
                        else:
                            print(f"  ❌ 视频生成失败: {result.stderr[:200] if result.stderr else '未知错误'}")
                            failed_count += 1
                            continue
                    except Exception as e:
                        print(f"  ❌ 视频生成异常: {e}")
                        failed_count += 1
                        continue
            else:
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
                        print(f"  ✓ 视频已生成")
                    else:
                        print(f"  ❌ 视频生成失败")
                        failed_count += 1
                        continue
                except Exception as e:
                    print(f"  ❌ 视频生成异常: {e}")
                    failed_count += 1
                    continue
        
        # 4. 打包到每期文件夹
        final_dir = get_final_output_dir(schedule_date, title)
        final_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"  [打包] 到文件夹: {final_dir.name}")
        
        # 收集所有相关文件
        files_to_move = []
        
        # 核心文件
        core_files = [
            demo_dir / f"{id_str}_cover.png",
            demo_dir / f"{id_str}_playlist.csv",
        ]
        # full_mix可能有两种命名
        full_mix_v1 = demo_dir / f"{id_str}_full_mix.mp3"
        full_mix_v2 = demo_dir / f"{id_str}_playlist_full_mix.mp3"
        if full_mix_v1.exists():
            core_files.append(full_mix_v1)
        elif full_mix_v2.exists():
            core_files.append(full_mix_v2)
        # 视频
        video_file = demo_dir / f"{id_str}_youtube.mp4"
        if video_file.exists():
            core_files.append(video_file)
        
        files_to_move.extend([f for f in core_files if f.exists()])
        
        # YouTube资源文件
        for pattern in [
            f"{id_str}_youtube*.srt",
            f"{id_str}_youtube*.txt",
            f"{id_str}_youtube*.csv",
        ]:
            found = list(demo_dir.glob(pattern))
            files_to_move.extend(found)
        
        # 移动文件
        moved_count = 0
        for src_file in files_to_move:
            dst_file = final_dir / src_file.name
            if not dst_file.exists():
                shutil.move(str(src_file), str(dst_file))
                moved_count += 1
        
        if moved_count > 0:
            print(f"  ✓ 已打包 {moved_count} 个文件到: {final_dir.name}")
        else:
            print(f"  ℹ️  所有文件已在文件夹中")
        
        # 5. 更新排播表状态（如果视频已生成）
        if video_path.exists() or (final_dir / f"{id_str}_youtube.mp4").exists():
            current_status = normalize_status(ep.get("status", ""))
            if current_status != STATUS_已完成:
                success_update = schedule.update_episode(
                    episode_id=id_str,
                    status=STATUS_已完成
                )
                if success_update:
                    schedule.save()
                    print(f"  ✓ 排播表状态已更新为: {STATUS_已完成}")
                    updated_schedule_count += 1
                else:
                    print(f"  ⚠️  更新排播表状态失败")
        
        success_count += 1
    
    # 6. 同步资源标记
    if updated_schedule_count > 0:
        print("\n" + "=" * 70)
        print("🔄 同步资源标记...")
        print("=" * 70)
        try:
            images_synced = schedule.sync_images_from_assignments()
            schedule.save()
            print(f"✅ 图片使用标记已同步（{images_synced:+d} 张）")
        except Exception as e:
            print(f"⚠️  同步资源标记失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"✅ 处理完成")
    print(f"   成功: {success_count}/{len(playlist_files)} 期")
    print(f"   失败: {failed_count}/{len(playlist_files)} 期")
    print(f"   更新排播表: {updated_schedule_count} 期")
    print("=" * 70)


if __name__ == "__main__":
    finalize_demo_episodes()

