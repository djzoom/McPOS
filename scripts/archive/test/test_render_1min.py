#!/usr/bin/env python3
"""
测试渲染前1分钟，找出正确的参数组合

测试不同的参数组合，找出能产生正确码率（约0.14 Mbps）的参数
"""
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_render_1min(episode_id: str, test_name: str, params: dict):
    """测试渲染前1分钟"""
    channel_id = "kat_lofi"
    output_dir = REPO_ROOT / "channels" / channel_id / "output"
    episode_dir = output_dir / episode_id
    
    cover_path = episode_dir / f"{episode_id}_cover.png"
    audio_path = episode_dir / f"{episode_id}_full_mix.mp3"
    test_video = episode_dir / f"test_{test_name}.mp4"
    
    if not cover_path.exists() or not audio_path.exists():
        print(f"❌ 文件不存在")
        return None
    
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
    ]
    
    # 添加码率控制：优先使用固定码率，否则使用CRF
    if params.get("b_v"):
        cmd.extend(["-b:v", params["b_v"]])
        # 添加maxrate和bufsize以确保码率限制生效
        if params.get("maxrate"):
            cmd.extend(["-maxrate", params["maxrate"]])
        if params.get("bufsize"):
            cmd.extend(["-bufsize", params["bufsize"]])
    elif params.get("crf"):
        cmd.extend(["-crf", str(params["crf"])])
    else:
        cmd.extend(["-crf", "23"])
    
    # 添加tune参数（如果指定）
    if params.get("tune"):
        cmd.extend(["-tune", params["tune"]])
    
    # 添加g参数（关键帧间隔，如果指定）
    if params.get("g"):
        cmd.extend(["-g", str(params["g"])])
    
    # 添加x264参数
    if params.get("x264_params"):
        if params["x264_params"]:  # 非空字符串
            cmd.extend(["-x264-params", params["x264_params"]])
    else:
        cmd.extend(["-x264-params", "keyint=1:min-keyint=1"])
    
    cmd.extend([
        "-vsync", "vfr",
        "-fps_mode", "passthrough",
        "-c:a", "aac",
        "-b:a", params.get("b_a", "192k"),  # 使用指定的音频码率
        "-shortest",
        str(test_video),
    ])
    
    print(f"\n测试: {test_name}")
    param_str = f"pix_fmt={params.get('pix_fmt')}, preset={params.get('preset')}"
    if params.get("b_v"):
        param_str += f", b:v={params.get('b_v')}"
        if params.get("maxrate"):
            param_str += f", maxrate={params.get('maxrate')}"
    elif params.get("crf"):
        param_str += f", crf={params.get('crf')}"
    if params.get("b_a"):
        param_str += f", b:a={params.get('b_a')}"
    print(f"  参数: {param_str}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
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
        
        # 计算预期码率（23期是0.14 Mbps）
        expected_bitrate = 0.14
        bitrate_ok = 0.1 < bitrate < 0.2 if bitrate else False
        
        print(f"  文件大小: {size_mb:.2f} MB (1分钟)")
        print(f"  码率: {bitrate:.2f} Mbps" if bitrate else "  码率: 未知")
        print(f"  像素格式: {pix_fmt_actual}")
        print(f"  预期码率: {expected_bitrate:.2f} Mbps")
        
        if bitrate_ok:
            print(f"  ✅ 码率正确！")
        elif bitrate:
            print(f"  ⚠️  码率差异: {bitrate/expected_bitrate:.1f}x")
        
        # 计算完整视频预期大小（62分钟）
        if bitrate:
            expected_full_size_mb = (bitrate * 60 * 62) / 8  # Mbps * 秒数 / 8 = MB
            print(f"  预期完整大小: {expected_full_size_mb:.1f} MB")
        
        return {
            "test_name": test_name,
            "size_mb": size_mb,
            "bitrate_mbps": bitrate,
            "pix_fmt": pix_fmt_actual,
            "params": params,
            "bitrate_ok": bitrate_ok
        }
        
    except subprocess.TimeoutExpired:
        print(f"  ❌ 超时")
        return None
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return None
    finally:
        # 保留测试文件以便检查（注释掉删除）
        # if test_video.exists():
        #     test_video.unlink()
        pass


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/test_render_1min.py <episode_id>")
        print("示例: python3 scripts/test_render_1min.py 20251127")
        sys.exit(1)
    
    episode_id = sys.argv[1]
    
    print("="*60)
    print(f"测试渲染前1分钟: {episode_id}")
    print("="*60)
    print("目标: 找出能产生码率约0.14 Mbps的参数组合")
    print()
    
    # 测试不同的参数组合（帧率1fps）
    test_configs = [
        {
            "name": "yuv420p_veryslow_bv100k_ba40k_tune_stillimage_g60",
            "params": {
                "pix_fmt": "yuv420p",
                "preset": "veryslow",
                "b_v": "100k",
                "maxrate": "100k",
                "bufsize": "200k",
                "b_a": "40k",
                "tune": "stillimage",
                "g": 60,
                "x264_params": "keyint=60:min-keyint=60"
            }
        },
        {
            "name": "yuv420p_veryslow_bv50k_ba40k_tune_stillimage_g60",
            "params": {
                "pix_fmt": "yuv420p",
                "preset": "veryslow",
                "b_v": "50k",
                "maxrate": "50k",
                "bufsize": "100k",
                "b_a": "40k",
                "tune": "stillimage",
                "g": 60,
                "x264_params": "keyint=60:min-keyint=60"
            }
        },
        {
            "name": "yuv420p_veryslow_crf32_tune_stillimage_g60",
            "params": {
                "pix_fmt": "yuv420p",
                "preset": "veryslow",
                "crf": 32,
                "tune": "stillimage",
                "g": 60,
                "x264_params": "keyint=60:min-keyint=60"
            }
        },
        {
            "name": "yuv420p_veryslow_crf30_tune_stillimage_g60",
            "params": {
                "pix_fmt": "yuv420p",
                "preset": "veryslow",
                "crf": 30,
                "tune": "stillimage",
                "g": 60,
                "x264_params": "keyint=60:min-keyint=60"
            }
        },
    ]
    
    results = []
    for config in test_configs:
        result = test_render_1min(episode_id, config["name"], config["params"])
        if result:
            results.append(result)
    
    # 总结
    print("\n" + "="*60)
    print("测试结果总结")
    print("="*60)
    
    if results:
        # 找出码率最接近0.14 Mbps的
        best = min(results, key=lambda x: abs(x["bitrate_mbps"] - 0.14) if x["bitrate_mbps"] else 999)
        
        print(f"\n最佳参数组合: {best['test_name']}")
        print(f"  参数: {best['params']}")
        print(f"  码率: {best['bitrate_mbps']:.2f} Mbps")
        print(f"  预期完整大小: {(best['bitrate_mbps'] * 60 * 62) / 8:.1f} MB")
        
        print(f"\n所有测试结果:")
        for r in sorted(results, key=lambda x: abs(x["bitrate_mbps"] - 0.14) if x["bitrate_mbps"] else 999):
            status = "✅" if r["bitrate_ok"] else "⚠️"
            print(f"  {status} {r['test_name']}: {r['bitrate_mbps']:.2f} Mbps, {r['size_mb']:.2f} MB")
    else:
        print("没有成功的测试结果")


if __name__ == "__main__":
    main()

