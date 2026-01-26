#!/usr/bin/env python3
"""
测试不同渲染参数，只渲染前60秒

快速测试不同参数组合，找出能产生正确码率（约0.14 Mbps）的参数
"""
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_render_params(episode_id: str, channel_id: str = "kat_lofi", duration_sec: int = 60):
    """测试不同参数组合，只渲染指定时长"""
    
    output_dir = REPO_ROOT / "channels" / channel_id / "output"
    episode_dir = output_dir / episode_id
    
    cover_path = episode_dir / f"{episode_id}_cover.png"
    audio_path = episode_dir / f"{episode_id}_full_mix.mp3"
    
    if not cover_path.exists() or not audio_path.exists():
        print(f"❌ 文件不存在")
        return
    
    print("="*60)
    print(f"测试渲染参数（只渲染前{duration_sec}秒）")
    print(f"期数: {episode_id}")
    print("="*60)
    
    # 测试不同的参数组合
    test_configs = [
        {
            "name": "配置1: yuv420p, crf=23, preset=veryfast (当前)",
            "pix_fmt": "yuv420p",
            "crf": "23",
            "preset": "veryfast",
            "extra": []
        },
        {
            "name": "配置2: yuv444p, crf=23, preset=veryfast (与23期像素格式一致)",
            "pix_fmt": "yuv444p",
            "crf": "23",
            "preset": "veryfast",
            "extra": []
        },
        {
            "name": "配置3: yuv420p, crf=23, preset=slow",
            "pix_fmt": "yuv420p",
            "crf": "23",
            "preset": "slow",
            "extra": []
        },
        {
            "name": "配置4: yuv444p, crf=23, preset=slow (与23期完全一致)",
            "pix_fmt": "yuv444p",
            "crf": "23",
            "preset": "slow",
            "extra": []
        },
        {
            "name": "配置5: yuv420p, crf=23, preset=veryfast, 显式码率控制",
            "pix_fmt": "yuv420p",
            "crf": "23",
            "preset": "veryfast",
            "extra": ["-maxrate", "0", "-bufsize", "0"]
        },
        {
            "name": "配置6: yuv420p, crf=28 (更高CRF，更小文件)",
            "pix_fmt": "yuv420p",
            "crf": "28",
            "preset": "veryfast",
            "extra": []
        },
    ]
    
    results = []
    
    for i, config in enumerate(test_configs, 1):
        test_output = episode_dir / f"test_{i}_{config['pix_fmt']}_crf{config['crf']}_{config['preset']}.mp4"
        
        print(f"\n{config['name']}")
        print(f"输出: {test_output.name}")
        
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-t", str(duration_sec), "-i", str(cover_path),
            "-t", str(duration_sec), "-i", str(audio_path),
            "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,"
                   "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,"
                   "fps=1:round=down",
            "-pix_fmt", config["pix_fmt"],
            "-c:v", "libx264",
            "-preset", config["preset"],
            "-crf", config["crf"],
        ] + config["extra"] + [
            "-x264-params", "keyint=1:min-keyint=1",
            "-vsync", "vfr",
            "-fps_mode", "passthrough",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(test_output),
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                print(f"  ❌ 渲染失败: {result.stderr[:200]}")
                continue
            
            if test_output.exists():
                size_mb = test_output.stat().st_size / (1024 * 1024)
                
                # 检查码率
                cmd_check = [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=bit_rate,pix_fmt",
                    "-of", "json",
                    str(test_output)
                ]
                result_check = subprocess.run(cmd_check, capture_output=True, text=True, timeout=5)
                
                bitrate = 0
                pix_fmt_actual = "unknown"
                if result_check.returncode == 0:
                    import json
                    info = json.loads(result_check.stdout)
                    if "streams" in info and len(info["streams"]) > 0:
                        stream = info["streams"][0]
                        bitrate = int(stream.get('bit_rate', 0)) / 1_000_000 if stream.get('bit_rate') else 0
                        pix_fmt_actual = stream.get('pix_fmt', 'unknown')
                
                # 计算预期大小（基于23期的码率0.14 Mbps）
                expected_size_mb = (0.14 * duration_sec) / 8
                if config["pix_fmt"] == "yuv420p":
                    expected_size_mb = expected_size_mb / 3  # yuv420p约是yuv444p的1/3
                
                results.append({
                    "config": config["name"],
                    "size_mb": size_mb,
                    "bitrate_mbps": bitrate,
                    "pix_fmt": pix_fmt_actual,
                    "expected_size_mb": expected_size_mb,
                    "file": test_output
                })
                
                status = "✅" if 0.1 < bitrate < 0.3 else "❌"
                print(f"  {status} 文件大小: {size_mb:.2f} MB, 码率: {bitrate:.2f} Mbps")
                print(f"     预期: {expected_size_mb:.2f} MB, 码率: 0.14 Mbps")
            else:
                print(f"  ❌ 文件未生成")
        except Exception as e:
            print(f"  ❌ 异常: {e}")
    
    # 总结
    print("\n" + "="*60)
    print("测试结果总结")
    print("="*60)
    print(f"{'配置':<50} {'大小(MB)':<10} {'码率(Mbps)':<12} {'状态':<10}")
    print("-" * 90)
    
    best_config = None
    best_score = float('inf')
    
    for r in results:
        # 计算分数：码率差异 + 文件大小差异
        bitrate_diff = abs(r["bitrate_mbps"] - 0.14) / 0.14
        size_diff = abs(r["size_mb"] - r["expected_size_mb"]) / r["expected_size_mb"] if r["expected_size_mb"] > 0 else 999
        score = bitrate_diff + size_diff
        
        status = "✅ 正常" if 0.1 < r["bitrate_mbps"] < 0.3 else "❌ 异常"
        print(f"{r['config']:<50} {r['size_mb']:<10.2f} {r['bitrate_mbps']:<12.2f} {status:<10}")
        
        if score < best_score:
            best_score = score
            best_config = r
    
    if best_config:
        print(f"\n✅ 最佳配置: {best_config['config']}")
        print(f"   文件大小: {best_config['size_mb']:.2f} MB")
        print(f"   码率: {best_config['bitrate_mbps']:.2f} Mbps")
        print(f"   像素格式: {best_config['pix_fmt']}")
    
    # 清理测试文件（可选）
    print(f"\n测试文件保存在: {episode_dir}")
    print("可以手动删除测试文件，或按Enter自动清理...")
    try:
        input()
        for r in results:
            if r["file"].exists():
                r["file"].unlink()
                print(f"已删除: {r['file'].name}")
    except:
        pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 scripts/test_render_params.py <episode_id> [duration_sec]")
        print("示例: python3 scripts/test_render_params.py 20251127 60")
        sys.exit(1)
    
    episode_id = sys.argv[1]
    duration_sec = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    
    test_render_params(episode_id, duration_sec=duration_sec)

