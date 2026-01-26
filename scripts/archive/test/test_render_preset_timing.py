#!/usr/bin/env python3
"""
测试所有preset档位的渲染时间（CRF=55，5分钟）

参数：
- CRF: 55
- 其他参数：yuv420p, tune=stillimage, g=60, fps=1
- 测试时长：5分钟（300秒）
- Preset档位：veryfast, faster, fast, medium, slow, slower, veryslow
- 计时精确到秒
"""
import sys
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_preset_timing(episode_id: str, preset: str):
    """测试指定preset的渲染时间（5分钟）"""
    channel_id = "kat_lofi"
    output_dir = REPO_ROOT / "channels" / channel_id / "output"
    episode_dir = output_dir / episode_id
    
    cover_path = episode_dir / f"{episode_id}_cover.png"
    audio_path = episode_dir / f"{episode_id}_full_mix.mp3"
    test_video = episode_dir / f"test_preset_{preset}_5min.mp4"
    
    if not cover_path.exists() or not audio_path.exists():
        print(f"❌ 文件不存在")
        return None
    
    # 构建FFmpeg命令（5分钟 = 300秒）
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-t", "300", "-i", str(cover_path),  # 只渲染300秒（5分钟）
        "-t", "300", "-i", str(audio_path),
        "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,"
               "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,"
               "fps=1:round=down",  # 帧率1fps
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", "55",
        "-tune", "stillimage",
        "-g", "60",
        "-x264-params", "keyint=60:min-keyint=60",
        "-vsync", "vfr",
        "-fps_mode", "passthrough",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(test_video),
    ]
    
    print(f"\n测试 Preset={preset} (5分钟, CRF=55)")
    
    try:
        # 记录开始时间
        start_time = time.time()
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 1小时超时
        
        # 记录结束时间
        end_time = time.time()
        elapsed_seconds = int(end_time - start_time)
        elapsed_minutes = elapsed_seconds // 60
        elapsed_secs = elapsed_seconds % 60
        
        if result.returncode != 0:
            print(f"  ❌ 渲染失败: {result.stderr[:200]}")
            return None
        
        if not test_video.exists():
            print(f"  ❌ 文件未生成")
            return None
        
        size_mb = test_video.stat().st_size / (1024 * 1024)
        
        # 检查码率
        cmd_check = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=bit_rate",
            "-of", "json",
            str(test_video)
        ]
        result_check = subprocess.run(cmd_check, capture_output=True, text=True, timeout=5)
        
        bitrate = None
        if result_check.returncode == 0:
            import json
            info = json.loads(result_check.stdout)
            if "streams" in info and len(info["streams"]) > 0:
                stream = info["streams"][0]
                bitrate = int(stream.get('bit_rate', 0)) / 1_000_000 if stream.get('bit_rate') else 0
        
        # 计算预期完整大小（假设62分钟）
        expected_full_size_mb = None
        if bitrate:
            total_bitrate = bitrate + 0.192  # 视频码率 + 音频码率
            expected_full_size_mb = (total_bitrate * 60 * 62) / 8
        
        # 计算渲染速度（分钟/分钟）
        render_speed = 5.0 / (elapsed_seconds / 60.0) if elapsed_seconds > 0 else 0
        
        print(f"  渲染时间: {elapsed_minutes}分{elapsed_secs}秒 ({elapsed_seconds}秒)")
        print(f"  渲染速度: {render_speed:.2f}x (实时速度的倍数)")
        print(f"  文件大小: {size_mb:.2f} MB (5分钟)")
        print(f"  码率: {bitrate:.2f} Mbps" if bitrate else "  码率: 未知")
        if expected_full_size_mb:
            print(f"  预期完整大小: {expected_full_size_mb:.1f} MB")
            # 估算完整渲染时间
            estimated_full_time_sec = int((elapsed_seconds / 5.0) * 62)
            estimated_full_time_min = estimated_full_time_sec // 60
            estimated_full_time_sec_remain = estimated_full_time_sec % 60
            print(f"  预期完整渲染时间: 约{estimated_full_time_min}分{estimated_full_time_sec_remain}秒")
        
        return {
            "preset": preset,
            "elapsed_seconds": elapsed_seconds,
            "elapsed_time_str": f"{elapsed_minutes}分{elapsed_secs}秒",
            "render_speed": render_speed,
            "size_mb": size_mb,
            "bitrate_mbps": bitrate,
            "expected_full_size_mb": expected_full_size_mb,
            "estimated_full_time_sec": estimated_full_time_sec if expected_full_size_mb else None
        }
        
    except subprocess.TimeoutExpired:
        print(f"  ❌ 超时（超过1小时）")
        return None
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/test_render_preset_timing.py <episode_id>")
        print("示例: python3 scripts/test_render_preset_timing.py 20251127")
        sys.exit(1)
    
    episode_id = sys.argv[1]
    
    print("="*60)
    print(f"Preset档位渲染时间测试: {episode_id}")
    print("="*60)
    print("参数: yuv420p, CRF=55, tune=stillimage, g=60, fps=1")
    print("测试时长: 5分钟（300秒）")
    print("Preset档位: veryfast, faster, fast, medium, slow, slower, veryslow")
    print()
    
    # 所有preset档位（从快到慢）
    presets = ["veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
    
    results = []
    for preset in presets:
        result = test_preset_timing(episode_id, preset)
        if result:
            results.append(result)
    
    # 总结
    print("\n" + "="*60)
    print("Preset档位渲染时间测试结果总结")
    print("="*60)
    
    if results:
        print(f"\n{'Preset':<12} {'渲染时间':<15} {'渲染速度':<12} {'大小(MB)':<12} {'码率(Mbps)':<12} {'预期完整(MB)':<15}")
        print("-" * 85)
        for r in results:
            time_str = r['elapsed_time_str']
            speed_str = f"{r['render_speed']:.2f}x"
            size_str = f"{r['size_mb']:.2f}"
            bitrate_str = f"{r['bitrate_mbps']:.2f}" if r['bitrate_mbps'] else "N/A"
            expected_str = f"{r['expected_full_size_mb']:.1f}" if r['expected_full_size_mb'] else "N/A"
            print(f"{r['preset']:<12} {time_str:<15} {speed_str:<12} {size_str:<12} {bitrate_str:<12} {expected_str:<15}")
        
        # 找出最快和最慢的
        fastest = min(results, key=lambda x: x['elapsed_seconds'])
        slowest = max(results, key=lambda x: x['elapsed_seconds'])
        
        print(f"\n最快: {fastest['preset']} - {fastest['elapsed_time_str']} ({fastest['render_speed']:.2f}x)")
        print(f"最慢: {slowest['preset']} - {slowest['elapsed_time_str']} ({slowest['render_speed']:.2f}x)")
        print(f"速度差异: {slowest['elapsed_seconds'] / fastest['elapsed_seconds']:.1f}x")
        
        # 推荐
        print(f"\n推荐:")
        print(f"  如果追求速度: 使用 {fastest['preset']} (约{fastest['elapsed_time_str']})")
        print(f"  如果追求质量/文件大小: 使用 {slowest['preset']} (约{slowest['elapsed_time_str']})")
        print(f"  平衡选择: medium 或 slow")
        
        # 估算完整渲染时间
        print(f"\n完整视频（62分钟）预期渲染时间:")
        for r in results:
            if r['estimated_full_time_sec']:
                full_min = r['estimated_full_time_sec'] // 60
                full_sec = r['estimated_full_time_sec'] % 60
                print(f"  {r['preset']:<12}: 约{full_min}分{full_sec}秒")
    else:
        print("没有成功的测试结果")


if __name__ == "__main__":
    main()

