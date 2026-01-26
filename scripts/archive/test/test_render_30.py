#!/usr/bin/env python3
"""
使用 render_video_direct_from_playlist 测试渲染30期视频

直接调用 kat_rec_web/backend/t2r/utils/direct_video_render.py 中的
render_video_direct_from_playlist 函数来渲染视频。
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "kat_rec_web" / "backend"))

from kat_rec_web.backend.t2r.services.schedule_service import get_output_dir
from kat_rec_web.backend.t2r.utils.direct_video_render import render_video_direct_from_playlist


async def test_render_30():
    """测试渲染30期视频"""
    episode_id = "20251130"
    channel_id = "kat_lofi"
    
    print("="*60)
    print(f"使用 render_video_direct_from_playlist 渲染30期")
    print("="*60)
    print(f"期数: {episode_id}")
    print(f"频道: {channel_id}")
    print()
    
    try:
        # 获取输出目录
        output_dir = get_output_dir(channel_id)
        episode_output_dir = output_dir / episode_id
        
        # 检查必需文件
        playlist_path = episode_output_dir / "playlist.csv"
        cover_path = episode_output_dir / f"{episode_id}_cover.png"
        video_path = episode_output_dir / f"{episode_id}_youtube.mp4"
        
        if not playlist_path.exists():
            print(f"❌ 错误: playlist.csv 不存在: {playlist_path}")
            return False
        
        if not cover_path.exists():
            print(f"❌ 错误: cover.png 不存在: {cover_path}")
            return False
        
        print(f"✅ 找到必需文件:")
        print(f"   playlist.csv: {playlist_path}")
        print(f"   cover.png: {cover_path}")
        
        # 检查视频是否已存在
        if video_path.exists():
            old_size = video_path.stat().st_size / (1024 * 1024)
            print(f"\n⚠️  视频文件已存在: {video_path}")
            print(f"   当前大小: {old_size:.1f} MB")
            response = input("是否删除旧视频并重新渲染? (y/N): ").strip().lower()
            if response == 'y':
                video_path.unlink()
                print("✅ 已删除旧视频")
            else:
                print("跳过渲染")
                return True
        
        # 加载配置
        try:
            from src.configuration import AppConfig
            app_config = AppConfig.load()
            library_root = app_config.library.song_library_root.expanduser()
            sfx_dir = app_config.paths.sfx_dir.expanduser()
            extensions = list(app_config.library.audio_extensions) or [".mp3", ".wav", ".flac", ".m4a", ".aac"]
            print(f"\n✅ 配置加载成功:")
            print(f"   library_root: {library_root}")
            print(f"   sfx_dir: {sfx_dir}")
            print(f"   extensions: {extensions}")
        except Exception as e:
            print(f"⚠️  配置加载失败，使用默认值: {e}")
            library_root = REPO_ROOT / "library" / "songs"
            sfx_dir = REPO_ROOT / "assets" / "sfx"
            extensions = [".mp3", ".wav", ".flac", ".m4a", ".aac"]
        
        print(f"\n开始渲染视频...")
        print(f"   输出路径: {video_path}")
        print(f"   使用函数: render_video_direct_from_playlist")
        print(f"   参数: crf=23, fps=1, libx264, veryfast, yuv420p")
        print()
        
        # 调用渲染函数
        result_path = await render_video_direct_from_playlist(
            playlist_path=playlist_path,
            cover_path=cover_path,
            output_video_path=video_path,
            library_root=library_root,
            sfx_dir=sfx_dir,
            extensions=extensions,
            audio_bitrate="192k",
            lufs=-14.0,
            tp=-1.0,
            vinyl_noise_db=-18.0,
            needle_gain_db=-18.0,
            episode_id=episode_id,  # 传递episode_id以检测final_mix.mp3
        )
        
        # 检查视频是否生成成功
        if result_path.exists():
            file_size = result_path.stat().st_size / (1024 * 1024)  # MB
            print(f"\n✅ 视频渲染成功!")
            print(f"   文件路径: {result_path}")
            print(f"   文件大小: {file_size:.2f} MB")
            
            # 验证像素格式
            import subprocess
            try:
                cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=pix_fmt", "-of", "default=noprint_wrappers=1:nokey=1", str(result_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    pix_fmt = result.stdout.strip()
                    if pix_fmt == "yuv420p":
                        print(f"   ✅ 像素格式: {pix_fmt} (正确)")
                    else:
                        print(f"   ⚠️  像素格式: {pix_fmt} (应该是yuv420p)")
            except:
                pass
            
            return True
        else:
            print(f"❌ 视频文件未生成: {result_path}")
            return False
            
    except Exception as e:
        print(f"❌ 渲染失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_render_30())
    sys.exit(0 if success else 1)

