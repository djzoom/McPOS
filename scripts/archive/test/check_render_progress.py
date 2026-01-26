#!/usr/bin/env python3
# coding: utf-8
"""
检查视频渲染进度

用法:
    python3 scripts/check_render_progress.py kat kat_20260201
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcpos.models import EpisodeSpec
from mcpos.adapters.filesystem import build_asset_paths
from mcpos.config import get_config


def check_render_progress(channel_id: str, episode_id: str):
    """检查渲染进度"""
    date = episode_id.split("_")[-1] if "_" in episode_id else episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=episode_id,
    )
    
    config = get_config()
    paths = build_asset_paths(spec, config)
    
    print(f"📹 渲染进度检查: {episode_id}")
    print("=" * 60)
    
    # 检查音频文件长度
    if paths.final_mix_mp3.exists():
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(paths.final_mix_mp3)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                audio_duration = float(result.stdout.strip())
                print(f"🎵 音频文件长度: {audio_duration:.1f}秒 ({audio_duration/60:.1f}分钟)")
            else:
                print("⚠️  无法获取音频长度")
        except Exception as e:
            print(f"⚠️  获取音频长度失败: {e}")
    else:
        print("❌ 音频文件不存在")
        return
    
    # 检查视频文件
    if paths.youtube_mp4.exists():
        video_size = paths.youtube_mp4.stat().st_size
        print(f"📹 视频文件大小: {video_size / 1024 / 1024:.1f} MB")
        
        # 检查视频长度
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(paths.youtube_mp4)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                video_duration = float(result.stdout.strip())
                print(f"📹 当前视频长度: {video_duration:.1f}秒 ({video_duration/60:.1f}分钟)")
                
                if audio_duration:
                    progress = (video_duration / audio_duration) * 100
                    print(f"📊 渲染进度: {progress:.1f}%")
                    
                    if video_duration >= audio_duration * 0.99:  # 99%以上认为完成
                        print("✅ 视频渲染已完成！")
                    else:
                        remaining = audio_duration - video_duration
                        print(f"⏳ 剩余时间: {remaining:.1f}秒 ({remaining/60:.1f}分钟)")
            else:
                print("⚠️  视频文件可能还在写入中，无法读取元数据")
        except Exception as e:
            print(f"⚠️  获取视频长度失败: {e}")
            print("   视频文件可能还在写入中...")
    else:
        print("⏳ 视频文件尚未创建")
    
    # 检查渲染进程
    print()
    print("🔍 检查渲染进程:")
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True,
    )
    ffmpeg_processes = [line for line in result.stdout.split('\n') 
                       if 'ffmpeg' in line and episode_id in line and 'grep' not in line]
    
    if ffmpeg_processes:
        print(f"✅ 发现 {len(ffmpeg_processes)} 个渲染进程正在运行")
        for proc in ffmpeg_processes[:2]:  # 只显示前2个
            parts = proc.split()
            if len(parts) >= 3:
                cpu = parts[2]
                print(f"   CPU使用率: {cpu}%")
    else:
        print("ℹ️  未发现正在运行的渲染进程")
        if paths.render_complete_flag.exists():
            print("✅ 渲染已完成（flag文件存在）")
        else:
            print("⚠️  渲染可能已停止或完成")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="检查视频渲染进度")
    parser.add_argument("channel_id", help="频道ID，如 kat")
    parser.add_argument("episode_id", help="节目ID，如 kat_20260201")
    
    args = parser.parse_args()
    check_render_progress(args.channel_id, args.episode_id)
