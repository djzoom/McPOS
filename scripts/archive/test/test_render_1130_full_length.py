#!/usr/bin/env python3
"""
测试 g=3600 时 1130 期实际全长素材渲染

使用最新优化参数：CRF 35, Veryfast, g=3600, tune=stillimage
"""
import sys
import subprocess
from pathlib import Path
import time
import os
import signal

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_video_info(video_path: Path):
    """获取视频文件信息（大小、码率、像素格式、时长）"""
    if not video_path.exists():
        return None
    
    info = {
        "file_size": video_path.stat().st_size / (1024 * 1024),  # MB
        "total_bit_rate": "N/A",
        "video_bit_rate": "N/A",
        "audio_bit_rate": "N/A",
        "pixel_format": "N/A",
        "duration_sec": 0,
    }
    
    try:
        # 获取格式信息（总码率、时长）
        cmd_format = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=bit_rate,duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result_format = subprocess.run(cmd_format, capture_output=True, text=True, timeout=10)
        
        # 获取视频流信息
        cmd_video = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=pix_fmt,bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result_video = subprocess.run(cmd_video, capture_output=True, text=True, timeout=10)
        
        # 获取音频流信息
        cmd_audio = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result_audio = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=10)
        
        if result_format.returncode == 0:
            lines = result_format.stdout.strip().split('\n')
            if len(lines) >= 2:
                if lines[0].isdigit():
                    info["total_bit_rate"] = float(lines[0]) / 1_000_000  # Mbps
                if '.' in lines[1]:
                    info["duration_sec"] = float(lines[1])
        
        if result_video.returncode == 0:
            lines = result_video.stdout.strip().split('\n')
            if len(lines) >= 1:
                info["pixel_format"] = lines[0]
            if len(lines) >= 2 and lines[1].isdigit():
                info["video_bit_rate"] = float(lines[1]) / 1_000_000  # Mbps
        
        if result_audio.returncode == 0:
            lines = result_audio.stdout.strip().split('\n')
            if len(lines) >= 1 and lines[0].isdigit():
                info["audio_bit_rate"] = float(lines[0]) / 1000  # kbps
                
    except Exception as e:
        print(f"获取视频信息时出错: {e}")
    
    return info


def render_full_length(episode_id: str) -> dict:
    """执行全长渲染测试"""
    channel_id = "kat_lofi"
    output_dir = REPO_ROOT / "channels" / channel_id / "output"
    episode_dir = output_dir / episode_id
    
    cover_path = episode_dir / f"{episode_id}_cover.png"
    # 优先使用 final_mix.mp3，否则使用 full_mix.mp3
    final_mix_path = episode_dir / f"{episode_id}_final_mix.mp3"
    full_mix_path = episode_dir / f"{episode_id}_full_mix.mp3"
    test_video = episode_dir / f"{episode_id}_youtube_test_g3600.mp4"
    
    if not cover_path.exists():
        print(f"❌ 封面文件不存在: {cover_path}")
        return None
    
    # 选择音频文件
    if final_mix_path.exists():
        audio_path = final_mix_path
        print(f"✅ 使用 final_mix.mp3: {audio_path}")
    elif full_mix_path.exists():
        audio_path = full_mix_path
        print(f"✅ 使用 full_mix.mp3: {audio_path}")
    else:
        print(f"❌ 音频文件不存在: 检查了 {final_mix_path} 和 {full_mix_path}")
        return None
    
    # 检查音频文件大小
    audio_size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"   音频文件大小: {audio_size_mb:.2f} MB")
    
    # 删除旧测试文件
    if test_video.exists():
        old_size = test_video.stat().st_size / (1024 * 1024)
        print(f"\n⚠️  测试视频已存在: {test_video}")
        print(f"   当前大小: {old_size:.1f} MB")
        response = input("是否删除旧视频并重新渲染? (y/N): ").strip().lower()
        if response == 'y':
            test_video.unlink()
            print("✅ 已删除旧视频")
        else:
            print("跳过渲染")
            return None
    
    # 使用最新优化参数
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(cover_path),
        "-i", str(audio_path),
        "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,"
               "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,"
               "fps=1:round=down",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "35",
        "-tune", "stillimage",
        "-g", "3600",  # 每3600秒（1小时）一个I帧
        "-x264-params", "keyint=3600:min-keyint=3600",
        "-vsync", "vfr",
        "-fps_mode", "passthrough",
        "-c:a", "aac",
        "-b:a", "256k",
        "-shortest",
        "-movflags", "+faststart",
        str(test_video),
    ]
    
    print(f"\n{'='*60}")
    print(f"开始全长渲染测试: {episode_id}")
    print(f"{'='*60}")
    print(f"输出: {test_video}")
    print(f"参数:")
    print(f"  - 编码器: libx264")
    print(f"  - 像素格式: yuv420p")
    print(f"  - CRF: 35")
    print(f"  - Preset: veryfast")
    print(f"  - Tune: stillimage")
    print(f"  - 关键帧间隔: 3600 (g=3600)")
    print(f"  - 帧率: 1fps")
    print(f"  - 分辨率: 3840x2160 (4K)")
    print(f"  - 音频: AAC 256k")
    print()
    
    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )
        pid = process.pid
        print(f"✅ FFmpeg 进程已启动，PID: {pid}")
        print()
        
        start_time = time.time()
        last_size = 0
        last_check_time = start_time
        check_interval = 30  # 每30秒检查一次
        
        while process.poll() is None:  # 进程仍在运行
            time.sleep(check_interval)
            if not test_video.exists():
                continue
            
            current_size = test_video.stat().st_size / (1024 * 1024)  # MB
            elapsed_time = time.time() - start_time
            elapsed_min = elapsed_time / 60
            
            # 计算渲染速度
            if elapsed_time > 0 and current_size > 0:
                size_diff = current_size - last_size
                time_diff = time.time() - last_check_time
                if time_diff > 0:
                    render_speed = size_diff / time_diff  # MB/s
                    print(f"  [{elapsed_min:.1f}分钟] 文件大小: {current_size:.1f} MB (速度: {render_speed:.2f} MB/s)")
                else:
                    print(f"  [{elapsed_min:.1f}分钟] 文件大小: {current_size:.1f} MB")
            else:
                print(f"  [{elapsed_min:.1f}分钟] 文件大小: {current_size:.1f} MB")
            
            last_size = current_size
            last_check_time = time.time()
        
        # 进程结束
        stdout, stderr = process.communicate()
        total_time = time.time() - start_time
        
        if process.returncode != 0:
            print(f"\n❌ 渲染失败 (返回码: {process.returncode})")
            if stderr:
                print(f"错误信息:\n{stderr}")
            return None
        
        if not test_video.exists():
            print(f"\n❌ 视频文件未生成")
            return None
        
        # 获取视频信息
        info = get_video_info(test_video)
        if not info:
            print(f"\n⚠️  无法获取视频信息")
            info = {
                "file_size": test_video.stat().st_size / (1024 * 1024),
                "total_bit_rate": "N/A",
                "video_bit_rate": "N/A",
                "audio_bit_rate": "N/A",
                "pixel_format": "N/A",
                "duration_sec": 0,
            }
        
        print(f"\n{'='*60}")
        print(f"✅ 渲染完成!")
        print(f"{'='*60}")
        print(f"渲染时间: {total_time:.1f} 秒 ({total_time/60:.1f} 分钟)")
        print(f"文件大小: {info['file_size']:.1f} MB ({info['file_size']/1024:.2f} GB)")
        print(f"总码率: {info['total_bit_rate']:.3f} Mbps" if info['total_bit_rate'] != "N/A" else "总码率: N/A")
        if info['video_bit_rate'] != "N/A":
            print(f"视频码率: {info['video_bit_rate']:.3f} Mbps")
        if info['audio_bit_rate'] != "N/A":
            print(f"音频码率: {info['audio_bit_rate']:.1f} kbps")
        print(f"像素格式: {info['pixel_format']}")
        if info['duration_sec'] > 0:
            duration_min = info['duration_sec'] / 60
            print(f"时长: {duration_min:.1f} 分钟 ({info['duration_sec']:.0f} 秒)")
        
        # 计算平均渲染速度
        if info['duration_sec'] > 0:
            render_speed = info['duration_sec'] / total_time
            print(f"渲染速度: {render_speed:.2f}x 实时速度")
        
        print(f"\n文件路径: {test_video}")
        print(f"{'='*60}\n")
        
        return {
            "episode_id": episode_id,
            "render_time": total_time,
            "file_size": info['file_size'],
            "total_bit_rate": info['total_bit_rate'],
            "video_bit_rate": info['video_bit_rate'],
            "audio_bit_rate": info['audio_bit_rate'],
            "pixel_format": info['pixel_format'],
            "duration_sec": info['duration_sec'],
            "video_path": str(test_video),
        }
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  用户中断渲染")
        if process:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            time.sleep(2)
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        return None
    except Exception as e:
        print(f"\n❌ 渲染异常: {e}")
        import traceback
        traceback.print_exc()
        if process:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            time.sleep(2)
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        return None
    finally:
        if process and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            time.sleep(2)
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)


def main():
    episode_id = "20251130"
    
    print("="*60)
    print(f"测试 g=3600 时 {episode_id} 期实际全长素材渲染")
    print("="*60)
    print(f"期数: {episode_id}")
    print(f"参数: CRF 35, Veryfast, g=3600, tune=stillimage")
    print()
    
    result = render_full_length(episode_id)
    
    if result:
        print("\n" + "="*60)
        print("测试完成总结")
        print("="*60)
        print(f"✅ 渲染成功")
        print(f"   文件大小: {result['file_size']:.1f} MB")
        print(f"   渲染时间: {result['render_time']/60:.1f} 分钟")
        if result['total_bit_rate'] != "N/A":
            print(f"   总码率: {result['total_bit_rate']:.3f} Mbps")
        print(f"   文件路径: {result['video_path']}")
        print("="*60)
    else:
        print("\n❌ 测试失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

