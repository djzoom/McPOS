#!/usr/bin/env python3
"""
三个配置的全长测试：精确计时

测试配置：
1. CRF 60, veryslow preset
2. CRF 40, veryfast preset
3. CRF 40, veryslow preset

其他参数保持不变：
- yuv420p
- tune=stillimage
- g=60
- fps=1
"""
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_full_length_config(episode_id: str, crf: int, preset: str):
    """测试完整长度渲染，精确计时"""
    channel_id = "kat_lofi"
    output_dir = REPO_ROOT / "channels" / channel_id / "output"
    episode_dir = output_dir / episode_id
    
    cover_path = episode_dir / f"{episode_id}_cover.png"
    audio_path = episode_dir / f"{episode_id}_full_mix.mp3"
    test_video = episode_dir / f"test_crf{crf}_{preset}_full.mp4"
    
    if not cover_path.exists():
        print(f"❌ 封面文件不存在: {cover_path}")
        return None
    
    if not audio_path.exists():
        print(f"❌ 音频文件不存在: {audio_path}")
        return None
    
    # 获取音频时长
    cmd_duration = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    result_duration = subprocess.run(cmd_duration, capture_output=True, text=True, timeout=5)
    if result_duration.returncode != 0:
        print(f"❌ 无法获取音频时长")
        return None
    
    audio_duration_sec = float(result_duration.stdout.strip())
    audio_duration_min = audio_duration_sec / 60
    
    print("="*60)
    print(f"全长渲染测试: {episode_id}")
    print(f"配置: CRF={crf}, Preset={preset}")
    print("="*60)
    print(f"参数:")
    print(f"  - CRF: {crf}")
    print(f"  - Preset: {preset}")
    print(f"  - 像素格式: yuv420p")
    print(f"  - Tune: stillimage")
    print(f"  - g: 60")
    print(f"  - fps: 1")
    print(f"音频时长: {audio_duration_min:.2f} 分钟 ({audio_duration_sec:.0f} 秒)")
    print()
    
    if test_video.exists():
        response = input(f"测试文件已存在，是否删除并重新测试? (y/N): ").strip().lower()
        if response == 'y':
            test_video.unlink()
        else:
            print("跳过测试")
            return None
    
    # 构建FFmpeg命令（完整长度）
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(cover_path),
        "-i", str(audio_path),
        "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,"
               "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,"
               "fps=1:round=down",  # 帧率1fps
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-tune", "stillimage",
        "-g", "60",
        "-x264-params", "keyint=60:min-keyint=60",
        "-vsync", "vfr",
        "-fps_mode", "passthrough",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(test_video),
    ]
    
    print(f"开始渲染...")
    print(f"输出: {test_video}")
    print()
    
    # 记录开始时间
    start_time = time.time()
    start_datetime = datetime.now()
    print(f"开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=14400)  # 4小时超时
        
        # 记录结束时间
        end_time = time.time()
        end_datetime = datetime.now()
        elapsed_seconds = int(end_time - start_time)
        elapsed_timedelta = timedelta(seconds=elapsed_seconds)
        
        print(f"\n结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"实际渲染时间: {elapsed_seconds} 秒 ({elapsed_timedelta})")
        
        if result.returncode != 0:
            print(f"❌ 渲染失败:")
            print(result.stderr)
            return None
        
        if not test_video.exists():
            print(f"❌ 视频文件未生成")
            return None
        
        # 获取文件信息
        size_mb = test_video.stat().st_size / (1024 * 1024)
        
        # 检查码率和时长
        cmd_check = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=bit_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            str(test_video)
        ]
        result_check = subprocess.run(cmd_check, capture_output=True, text=True, timeout=10)
        
        bitrate = None
        video_duration = None
        if result_check.returncode == 0:
            import json
            info = json.loads(result_check.stdout)
            if "streams" in info and len(info["streams"]) > 0:
                stream = info["streams"][0]
                bitrate = int(stream.get('bit_rate', 0)) / 1_000_000 if stream.get('bit_rate') else 0
                video_duration = float(stream.get('duration', 0)) if stream.get('duration') else 0
            elif "format" in info:
                video_duration = float(info["format"].get('duration', 0)) if info["format"].get('duration') else 0
        
        print(f"\n结果:")
        print(f"  文件大小: {size_mb:.1f} MB")
        if bitrate:
            print(f"  视频码率: {bitrate:.2f} Mbps")
        if video_duration:
            video_duration_min = video_duration / 60
            print(f"  视频时长: {video_duration_min:.2f} 分钟 ({video_duration:.0f} 秒)")
        
        # 计算渲染速度
        if video_duration:
            speed_ratio = video_duration / elapsed_seconds
            print(f"  渲染速度: {speed_ratio:.2f}x (实时速度的{speed_ratio:.2f}倍)")
            print(f"  即: 1秒音频需要 {1/speed_ratio:.2f} 秒渲染时间")
        
        print(f"\n✅ 测试完成!")
        return {
            "crf": crf,
            "preset": preset,
            "elapsed_seconds": elapsed_seconds,
            "size_mb": size_mb,
            "bitrate_mbps": bitrate,
            "video_duration_sec": video_duration,
            "speed_ratio": video_duration / elapsed_seconds if video_duration else None
        }
        
    except subprocess.TimeoutExpired:
        elapsed_seconds = int(time.time() - start_time)
        print(f"\n❌ 渲染超时（超过4小时）")
        print(f"已用时间: {elapsed_seconds} 秒")
        return None
    except Exception as e:
        elapsed_seconds = int(time.time() - start_time)
        print(f"\n❌ 渲染异常: {e}")
        print(f"已用时间: {elapsed_seconds} 秒")
        import traceback
        traceback.print_exc()
        return None


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/test_render_full_length_3configs.py <episode_id>")
        print("示例: python3 scripts/test_render_full_length_3configs.py 20251127")
        sys.exit(1)
    
    episode_id = sys.argv[1]
    
    print("="*60)
    print(f"三个配置的全长测试: {episode_id}")
    print("="*60)
    print("将依次测试:")
    print("  1. CRF 60, veryslow preset")
    print("  2. CRF 40, veryfast preset")
    print("  3. CRF 40, veryslow preset")
    print()
    
    configs = [
        (60, "veryslow"),
        (40, "veryfast"),
        (40, "veryslow"),
    ]
    
    results = []
    for i, (crf, preset) in enumerate(configs, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}/3: CRF={crf}, Preset={preset}")
        print(f"{'='*60}")
        
        result = test_full_length_config(episode_id, crf, preset)
        if result:
            results.append(result)
        
        # 测试之间稍作停顿
        if i < len(configs):
            print(f"\n等待5秒后开始下一个测试...")
            time.sleep(5)
    
    # 总结
    print("\n" + "="*60)
    print("所有测试结果总结")
    print("="*60)
    
    if results:
        print(f"\n{'配置':<25} {'渲染时间(秒)':<15} {'文件大小(MB)':<15} {'码率(Mbps)':<12} {'速度比':<10}")
        print("-" * 80)
        for r in results:
            config_str = f"CRF={r['crf']}, {r['preset']}"
            time_str = f"{r['elapsed_seconds']}"
            size_str = f"{r['size_mb']:.1f}"
            bitrate_str = f"{r['bitrate_mbps']:.2f}" if r['bitrate_mbps'] else "N/A"
            speed_str = f"{r['speed_ratio']:.2f}x" if r['speed_ratio'] else "N/A"
            print(f"{config_str:<25} {time_str:<15} {size_str:<15} {bitrate_str:<12} {speed_str:<10}")
        
        # 找出最快的配置
        fastest = min(results, key=lambda x: x['elapsed_seconds'])
        print(f"\n最快配置: CRF={fastest['crf']}, Preset={fastest['preset']}")
        print(f"  渲染时间: {fastest['elapsed_seconds']} 秒 ({timedelta(seconds=fastest['elapsed_seconds'])})")
        print(f"  文件大小: {fastest['size_mb']:.1f} MB")
        print(f"  速度比: {fastest['speed_ratio']:.2f}x" if fastest['speed_ratio'] else "  速度比: N/A")
    else:
        print("没有成功的测试结果")


if __name__ == "__main__":
    main()

