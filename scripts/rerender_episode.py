#!/usr/bin/env python3
# coding: utf-8
"""
重新渲染指定episode的视频

用法:
    python3 scripts/rerender_episode.py kat kat_20260201
"""
from __future__ import annotations

import sys
import asyncio
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcpos.models import EpisodeSpec, AssetPaths
from mcpos.adapters.filesystem import build_asset_paths
from mcpos.config import get_config
from mcpos.assets.render import run_render_for_episode


async def rerender_episode(channel_id: str, episode_id: str):
    """重新渲染episode的视频"""
    # 从 episode_id 解析 date
    date = episode_id.split("_")[-1] if "_" in episode_id else episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=episode_id,
    )
    
    config = get_config()
    paths = build_asset_paths(spec, config)
    
    print(f"📹 开始重新渲染: {episode_id}")
    print(f"   频道: {channel_id}")
    print(f"   输出目录: {paths.episode_output_dir}")
    print()
    
    # 检查必需文件
    if not paths.cover_png.exists():
        print(f"❌ 错误: 封面文件不存在: {paths.cover_png}")
        print("   请先运行 COVER 阶段")
        return False
    
    if not paths.final_mix_mp3.exists():
        print(f"❌ 错误: 音频文件不存在: {paths.final_mix_mp3}")
        print("   请先运行 MIX 阶段")
        return False
    
    print(f"✅ 输入文件检查通过:")
    print(f"   封面: {paths.cover_png.name} ({paths.cover_png.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"   音频: {paths.final_mix_mp3.name} ({paths.final_mix_mp3.stat().st_size / 1024 / 1024:.1f} MB)")
    print()
    
    # 删除旧的视频文件和flag（如果存在）
    if paths.youtube_mp4.exists():
        print(f"🗑️  删除旧的视频文件: {paths.youtube_mp4.name}")
        paths.youtube_mp4.unlink()
    
    if paths.render_complete_flag.exists():
        print(f"🗑️  删除旧的flag文件: {paths.render_complete_flag.name}")
        paths.render_complete_flag.unlink()
    
    print()
    print("🎬 开始渲染...")
    print()
    
    try:
        result = await run_render_for_episode(spec, paths)
        
        if result.success:
            print()
            print("=" * 60)
            print(f"✅ 渲染成功完成!")
            print("=" * 60)
            print(f"   视频文件: {paths.youtube_mp4}")
            print(f"   文件大小: {paths.youtube_mp4.stat().st_size / 1024 / 1024:.1f} MB")
            print(f"   耗时: {result.duration_seconds:.1f} 秒")
            return True
        else:
            print()
            print("=" * 60)
            print(f"❌ 渲染失败")
            print("=" * 60)
            if result.error_message:
                print(f"   错误: {result.error_message}")
            return False
            
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ 渲染过程中发生异常")
        print("=" * 60)
        print(f"   错误: {e}")
        import traceback
        print()
        print("详细错误信息:")
        print(traceback.format_exc())
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="重新渲染episode的视频")
    parser.add_argument("channel_id", help="频道ID，如 kat")
    parser.add_argument("episode_id", help="节目ID，如 kat_20260201")
    
    args = parser.parse_args()
    
    success = asyncio.run(rerender_episode(args.channel_id, args.episode_id))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
