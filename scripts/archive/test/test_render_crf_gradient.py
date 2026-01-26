#!/usr/bin/env python3
"""
CRF梯度测试：从35到60，步长+5，每个测试10分钟

使用已验证的最佳参数组合：
- yuv420p
- veryslow
- tune=stillimage
- g=60
- fps=1
"""
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_crf_10min(episode_id: str, crf: int):
    """测试指定CRF值，渲染10分钟"""
    channel_id = "kat_lofi"
    output_dir = REPO_ROOT / "channels" / channel_id / "output"
    episode_dir = output_dir / episode_id
    
    cover_path = episode_dir / f"{episode_id}_cover.png"
    audio_path = episode_dir / f"{episode_id}_full_mix.mp3"
    test_video = episode_dir / f"test_crf{crf}_10min.mp4"
    
    if not cover_path.exists() or not audio_path.exists():
        print(f"❌ 文件不存在")
        return None
    
    # 构建FFmpeg命令（10分钟 = 600秒）
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-t", "600", "-i", str(cover_path),  # 只渲染600秒（10分钟）
        "-t", "600", "-i", str(audio_path),
        "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,"
               "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,"
               "fps=1:round=down",  # 帧率1fps
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "veryslow",
        "-crf", str(crf),
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
    
    print(f"\n测试 CRF={crf} (10分钟)")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30分钟超时
        
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
            "-show_entries", "stream=bit_rate,pix_fmt",
            "-of", "json",
            str(test_video)
        ]
        result_check = subprocess.run(cmd_check, capture_output=True, text=True, timeout=5)
        
        bitrate = None
        pix_fmt_actual = None
        if result_check.returncode == 0:
            import json
            info = json.loads(result_check.stdout)
            if "streams" in info and len(info["streams"]) > 0:
                stream = info["streams"][0]
                bitrate = int(stream.get('bit_rate', 0)) / 1_000_000 if stream.get('bit_rate') else 0
                pix_fmt_actual = stream.get('pix_fmt', 'unknown')
        
        # 计算预期完整大小（假设62分钟）
        expected_full_size_mb = None
        if bitrate:
            # 总码率 = 视频码率 + 音频码率(192k = 0.192 Mbps)
            total_bitrate = bitrate + 0.192
            expected_full_size_mb = (total_bitrate * 60 * 62) / 8  # Mbps * 秒数 / 8 = MB
        
        print(f"  文件大小: {size_mb:.2f} MB (10分钟)")
        print(f"  码率: {bitrate:.2f} Mbps" if bitrate else "  码率: 未知")
        print(f"  像素格式: {pix_fmt_actual}")
        if expected_full_size_mb:
            print(f"  预期完整大小: {expected_full_size_mb:.1f} MB")
        
        return {
            "crf": crf,
            "size_mb": size_mb,
            "bitrate_mbps": bitrate,
            "pix_fmt": pix_fmt_actual,
            "expected_full_size_mb": expected_full_size_mb
        }
        
    except subprocess.TimeoutExpired:
        print(f"  ❌ 超时")
        return None
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/test_render_crf_gradient.py <episode_id>")
        print("示例: python3 scripts/test_render_crf_gradient.py 20251127")
        sys.exit(1)
    
    episode_id = sys.argv[1]
    
    print("="*60)
    print(f"CRF梯度测试: {episode_id}")
    print("="*60)
    print("参数: yuv420p, veryslow, tune=stillimage, g=60, fps=1")
    print("测试范围: CRF 35-60, 步长+5")
    print("每个测试: 10分钟")
    print()
    
    # CRF梯度：35, 40, 45, 50, 55, 60
    crf_values = list(range(35, 65, 5))
    
    results = []
    for crf in crf_values:
        result = test_crf_10min(episode_id, crf)
        if result:
            results.append(result)
    
    # 总结
    print("\n" + "="*60)
    print("CRF梯度测试结果总结")
    print("="*60)
    
    if results:
        print(f"\n{'CRF':<6} {'大小(MB)':<12} {'码率(Mbps)':<12} {'预期完整(MB)':<15}")
        print("-" * 50)
        for r in sorted(results, key=lambda x: x["crf"]):
            size_str = f"{r['size_mb']:.2f}" if r['size_mb'] else "N/A"
            bitrate_str = f"{r['bitrate_mbps']:.2f}" if r['bitrate_mbps'] else "N/A"
            expected_str = f"{r['expected_full_size_mb']:.1f}" if r['expected_full_size_mb'] else "N/A"
            print(f"{r['crf']:<6} {size_str:<12} {bitrate_str:<12} {expected_str:<15}")
        
        # 找出最佳平衡点（文件大小适中，质量好）
        print(f"\n推荐:")
        print(f"  根据测试结果，选择文件大小和质量的最佳平衡点")
        print(f"  建议选择预期完整大小在150-200MB范围内的CRF值")
        
        # 找出最接近150-200MB的
        target_range = (150, 200)
        best = None
        for r in results:
            if r['expected_full_size_mb']:
                if target_range[0] <= r['expected_full_size_mb'] <= target_range[1]:
                    if best is None or abs(r['expected_full_size_mb'] - 175) < abs(best['expected_full_size_mb'] - 175):
                        best = r
        
        if best:
            print(f"\n  最佳CRF值: {best['crf']}")
            print(f"    预期完整大小: {best['expected_full_size_mb']:.1f} MB")
            print(f"    码率: {best['bitrate_mbps']:.2f} Mbps")
        else:
            # 如果没有在目标范围内的，找最接近的
            closest = min(results, key=lambda x: abs(x['expected_full_size_mb'] - 175) if x['expected_full_size_mb'] else 999)
            print(f"\n  最接近目标(175MB)的CRF值: {closest['crf']}")
            print(f"    预期完整大小: {closest['expected_full_size_mb']:.1f} MB")
            print(f"    码率: {closest['bitrate_mbps']:.2f} Mbps")
    else:
        print("没有成功的测试结果")


if __name__ == "__main__":
    main()

