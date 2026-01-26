#!/usr/bin/env python3
"""
对比测试：-g 3600 vs -g 36 (CRF 35, Veryfast, 1分钟)

测试不同关键帧间隔对渲染时间和文件大小的影响
"""
import sys
import subprocess
from pathlib import Path
import time

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_video_info(video_path: Path):
    """获取视频文件信息（大小、码率、像素格式）"""
    if not video_path.exists():
        return None
    
    info = {
        "file_size": video_path.stat().st_size / (1024 * 1024),  # MB
        "total_bit_rate": "N/A",
        "pixel_format": "N/A",
    }
    
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=pix_fmt",
            "-show_entries", "format=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            info["pixel_format"] = lines[0] if len(lines) > 0 else "N/A"
            if len(lines) > 1 and lines[1].isdigit():
                info["total_bit_rate"] = float(lines[1]) / 1_000_000  # Mbps
    except Exception:
        pass
    
    return info


def test_render(episode_id: str, test_name: str, params: dict) -> dict:
    """执行单次1分钟渲染测试"""
    channel_id = "kat_lofi"
    output_dir = REPO_ROOT / "channels" / channel_id / "output"
    episode_dir = output_dir / episode_id
    
    cover_path = episode_dir / f"{episode_id}_cover.png"
    audio_path = episode_dir / f"{episode_id}_full_mix.mp3"
    test_video = output_dir / f"test_{test_name}.mp4"
    
    if not cover_path.exists() or not audio_path.exists():
        print(f"❌ 文件不存在")
        return None
    
    # 删除旧测试文件
    if test_video.exists():
        test_video.unlink()
    
    # 构建FFmpeg命令
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-t", "60", "-i", str(cover_path),  # 只渲染60秒
        "-t", "60", "-i", str(audio_path),
        "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,"
               "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,"
               "fps=1:round=down",  # 帧率1fps
        "-pix_fmt", params.get("pix_fmt", "yuv420p"),
        "-c:v", "libx264",
        "-preset", params.get("preset", "veryfast"),
        "-crf", str(params.get("crf", 35)),
        "-tune", "stillimage",
        "-g", str(params.get("g", 60)),  # 关键帧间隔
    ]
    
    # 添加x264参数
    if params.get("x264_params"):
        cmd.extend(["-x264-params", params["x264_params"]])
    else:
        # 使用与-g相同的值
        g_value = params.get("g", 60)
        cmd.extend(["-x264-params", f"keyint={g_value}:min-keyint={g_value}"])
    
    cmd.extend([
        "-vsync", "vfr",
        "-fps_mode", "passthrough",
        "-c:a", "aac",
        "-b:a", params.get("b_a", "256k"),
        "-shortest",
        str(test_video),
    ])
    
    print(f"\n测试: {test_name}")
    print(f"  参数: g={params.get('g')}, crf={params.get('crf')}, preset={params.get('preset')}")
    print(f"  开始渲染...")
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        render_time = time.time() - start_time
        
        if result.returncode != 0:
            print(f"  ❌ 渲染失败:")
            print(result.stderr)
            return None
        
        if not test_video.exists():
            print(f"  ❌ 视频文件未生成")
            return None
        
        info = get_video_info(test_video)
        if not info:
            print(f"  ❌ 无法获取视频信息")
            return None
        
        file_size = info["file_size"]
        total_bit_rate = info["total_bit_rate"]
        pixel_format = info["pixel_format"]
        
        # 预期完整视频大小（假设62.5分钟）
        # 使用比例计算：1分钟文件大小 * 62.5
        full_duration_min = 62.5
        expected_full_size_mb = file_size * full_duration_min
        
        print(f"  ✅ 渲染完成")
        print(f"    渲染时间: {render_time:.2f} 秒")
        print(f"    文件大小: {file_size:.2f} MB (1分钟)")
        print(f"    码率: {total_bit_rate:.2f} Mbps")
        print(f"    像素格式: {pixel_format}")
        print(f"    预期完整大小: {expected_full_size_mb:.1f} MB")
        
        return {
            "name": test_name,
            "params": params,
            "render_time": render_time,
            "file_size": file_size,
            "bit_rate": total_bit_rate,
            "pixel_format": pixel_format,
            "expected_full_size": expected_full_size_mb
        }
        
    except subprocess.TimeoutExpired:
        print(f"  ❌ 超时（超过5分钟）")
        return None
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/test_render_g_comparison.py <episode_id>")
        print("示例: python3 scripts/test_render_g_comparison.py 20251127")
        sys.exit(1)
    
    episode_id = sys.argv[1]
    
    print("="*60)
    print(f"对比测试：-g 3600 vs -g 36 (CRF 35, Veryfast, 1分钟)")
    print("="*60)
    print(f"期数: {episode_id}")
    print()
    
    # 测试配置
    test_configs = [
        {
            "name": "g3600_crf35_veryfast",
            "params": {
                "pix_fmt": "yuv420p",
                "preset": "veryfast",
                "crf": 35,
                "g": 3600,  # 每3600秒一个I帧（1小时）
                "x264_params": "keyint=3600:min-keyint=3600",
                "b_a": "256k"
            }
        },
        {
            "name": "g36_crf35_veryfast",
            "params": {
                "pix_fmt": "yuv420p",
                "preset": "veryfast",
                "crf": 35,
                "g": 36,  # 每36秒一个I帧
                "x264_params": "keyint=36:min-keyint=36",
                "b_a": "256k"
            }
        },
    ]
    
    results = []
    for config in test_configs:
        result = test_render(episode_id, config["name"], config["params"])
        if result:
            results.append(result)
    
    print("\n" + "="*60)
    print("对比测试结果总结")
    print("="*60)
    
    if len(results) != 2:
        print("❌ 测试未完成，缺少结果")
        return
    
    # 对比结果
    g3600_result = next((r for r in results if r["params"]["g"] == 3600), None)
    g36_result = next((r for r in results if r["params"]["g"] == 36), None)
    
    if not g3600_result or not g36_result:
        print("❌ 无法找到对比结果")
        return
    
    print(f"\n{'参数':<20} {'渲染时间(秒)':<15} {'文件大小(MB)':<15} {'码率(Mbps)':<15} {'预期完整(MB)':<15}")
    print("-" * 80)
    print(f"{'g=3600':<20} {g3600_result['render_time']:<15.2f} {g3600_result['file_size']:<15.2f} {g3600_result['bit_rate']:<15.2f} {g3600_result['expected_full_size']:<15.1f}")
    print(f"{'g=36':<20} {g36_result['render_time']:<15.2f} {g36_result['file_size']:<15.2f} {g36_result['bit_rate']:<15.2f} {g36_result['expected_full_size']:<15.1f}")
    
    # 计算差异
    time_diff = g3600_result['render_time'] - g36_result['render_time']
    time_diff_pct = (time_diff / g36_result['render_time']) * 100 if g36_result['render_time'] > 0 else 0
    
    size_diff = g3600_result['file_size'] - g36_result['file_size']
    size_diff_pct = (size_diff / g36_result['file_size']) * 100 if g36_result['file_size'] > 0 else 0
    
    bitrate_diff = g3600_result['bit_rate'] - g36_result['bit_rate']
    bitrate_diff_pct = (bitrate_diff / g36_result['bit_rate']) * 100 if g36_result['bit_rate'] > 0 else 0
    
    print("\n" + "="*60)
    print("差异分析")
    print("="*60)
    print(f"渲染时间差异: {time_diff:+.2f} 秒 ({time_diff_pct:+.1f}%)")
    print(f"   {'g=3600更快' if time_diff < 0 else 'g=36更快'}")
    print()
    print(f"文件大小差异: {size_diff:+.2f} MB ({size_diff_pct:+.1f}%)")
    print(f"   {'g=3600更小' if size_diff < 0 else 'g=36更小'}")
    print()
    print(f"码率差异: {bitrate_diff:+.3f} Mbps ({bitrate_diff_pct:+.1f}%)")
    print(f"   {'g=3600更低' if bitrate_diff < 0 else 'g=36更低'}")
    print()
    print(f"预期完整大小差异: {g3600_result['expected_full_size'] - g36_result['expected_full_size']:+.1f} MB")
    
    print("\n" + "="*60)
    print("结论")
    print("="*60)
    if abs(time_diff) < 1:
        print("✅ 渲染时间差异很小（<1秒），可忽略")
    else:
        faster = "g=3600" if time_diff < 0 else "g=36"
        print(f"⚠️  {faster} 渲染更快，差异 {abs(time_diff):.2f} 秒")
    
    if abs(size_diff_pct) < 5:
        print("✅ 文件大小差异很小（<5%），可忽略")
    else:
        smaller = "g=3600" if size_diff < 0 else "g=36"
        print(f"⚠️  {smaller} 文件更小，差异 {abs(size_diff_pct):.1f}%")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()

