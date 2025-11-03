#!/usr/bin/env python3
# coding: utf-8
"""
环境初始化脚本

功能：
1. 检测硬件和软件环境
2. 生成环境指纹
3. 自动运行基准测试选择最快渲染方法
4. 保存配置供后续使用
5. 仅在环境变化时重新测试
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CONFIG_DIR = REPO_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "best_encoder.json"
ENV_FINGERPRINT_FILE = CONFIG_DIR / "env_fingerprint.json"


def get_environment_fingerprint() -> Dict:
    """生成环境指纹，用于检测环境变化"""
    fingerprint = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "timestamp": datetime.now().isoformat(),
    }
    
    # macOS 特定信息
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                fingerprint["cpu_brand"] = result.stdout.strip()
        except Exception:
            pass
        
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.physicalcpu"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                fingerprint["physical_cpu"] = result.stdout.strip()
        except Exception:
            pass
    
    # FFmpeg 版本
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            fingerprint["ffmpeg_version"] = version_line
    except Exception:
        fingerprint["ffmpeg_version"] = "unknown"
    
    # 检查可用的编码器
    available_encoders = []
    encoder_tests = [
        ("h264_videotoolbox", ["ffmpeg", "-h", "encoder=h264_videotoolbox"]),
        ("h264_nvenc", ["ffmpeg", "-h", "encoder=h264_nvenc"]),
        ("mjpeg", ["ffmpeg", "-h", "encoder=mjpeg"]),
        ("libx264", ["ffmpeg", "-h", "encoder=libx264"]),
    ]
    
    for encoder_name, cmd in encoder_tests:
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=5
            )
            if result.returncode == 0:
                available_encoders.append(encoder_name)
        except Exception:
            pass
    
    fingerprint["available_encoders"] = available_encoders
    
    # 生成哈希用于快速比较
    fingerprint_str = json.dumps(fingerprint, sort_keys=True)
    fingerprint["hash"] = hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]
    
    return fingerprint


def load_env_fingerprint() -> Optional[Dict]:
    """加载保存的环境指纹"""
    if ENV_FINGERPRINT_FILE.exists():
        try:
            with ENV_FINGERPRINT_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_env_fingerprint(fingerprint: Dict) -> None:
    """保存环境指纹"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with ENV_FINGERPRINT_FILE.open("w", encoding="utf-8") as f:
        json.dump(fingerprint, f, ensure_ascii=False, indent=2)


def has_environment_changed(current: Dict, saved: Optional[Dict]) -> bool:
    """检查环境是否发生变化"""
    if not saved:
        return True
    
    # 比较关键字段
    key_fields = [
        "platform",
        "processor",
        "machine",
        "cpu_brand",
        "available_encoders",
        "ffmpeg_version"
    ]
    
    for field in key_fields:
        if current.get(field) != saved.get(field):
            print(f"环境变化检测: {field}")
            print(f"  旧值: {saved.get(field)}")
            print(f"  新值: {current.get(field)}")
            return True
    
    return False


def run_initialization_benchmark(image_path: Path, audio_path: Path, outdir: Path) -> Optional[Dict]:
    """运行初始化基准测试"""
    print("\n" + "=" * 70)
    print("🚀 开始环境初始化测试...")
    print("=" * 70)
    print(f"测试图片: {image_path}")
    print(f"测试音频: {audio_path}")
    print(f"输出目录: {outdir}")
    print()
    
    # 调用基准测试工具
    bench_cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "ffmpeg_bench.py"),
        "--image", str(image_path),
        "--audio", str(audio_path),
        "--outdir", str(outdir),
        "--fps", "1",
        "--runs", "1",
        "--container", "mp4"
    ]
    
    try:
        print("运行基准测试（这可能需要几分钟）...")
        result = subprocess.run(
            bench_cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        
        if result.returncode != 0:
            print(f"\n❌ 基准测试执行失败:")
            print(result.stderr)
            return None
        
        # 显示输出
        if result.stdout:
            print(result.stdout)
            
    except Exception as e:
        print(f"\n❌ 运行基准测试时出错: {e}")
        return None
    
    # 读取测试结果
    summary_file = outdir / "summary.json"
    if not summary_file.exists():
        print(f"\n❌ 未找到测试结果文件: {summary_file}")
        return None
    
    try:
        with summary_file.open("r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception as e:
        print(f"\n❌ 读取测试结果失败: {e}")
        return None
    
    # 找到最快的方法
    best_result = None
    best_time = float('inf')
    
    for r in results:
        if r.get("status") == "success" and r.get("elapsed_sec"):
            elapsed = r["elapsed_sec"]
            if elapsed < best_time:
                best_time = elapsed
                best_result = r
    
    if not best_result:
        print("\n❌ 没有找到成功的测试结果")
        return None
    
    # 提取最佳编码器信息
    best_method = best_result.get("method", "x264")
    best_encoder = best_result.get("encoder", "libx264")
    
    config = {
        "init_date": datetime.now().isoformat(),
        "test_date": datetime.now().isoformat(),
        "best_method": best_method,
        "best_encoder": best_encoder,
        "elapsed_sec": best_result.get("elapsed_sec"),
        "filesize_mb": best_result.get("filesize_mb"),
        "summary_path": str(summary_file),
        "all_results": results
    }
    
    # 保存配置
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print("✅ 环境初始化完成！")
    print("=" * 70)
    print(f"最快编码器: {best_method} ({best_encoder})")
    print(f"渲染耗时: {best_time:.2f} 秒")
    print(f"文件大小: {best_result.get('filesize_mb', 0):.2f} MB")
    print(f"\n配置已保存到: {CONFIG_FILE}")
    print(f"环境指纹已保存到: {ENV_FINGERPRINT_FILE}")
    print("\n💡 提示: 除非环境（硬件/软件）发生变化，否则将一直使用此配置。")
    print("   如需强制重新测试，请运行: python scripts/init_env.py --force")
    print("=" * 70)
    
    return config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="环境初始化：自动测试并选择最快渲染方法",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 自动初始化（使用默认测试文件）
  python scripts/init_env.py

  # 指定测试文件
  python scripts/init_env.py --image assets/cover_sample/cover_sample.png --audio output/audio/*full_mix.mp3

  # 强制重新测试
  python scripts/init_env.py --force
        """
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="测试用的封面图路径（可选，会自动查找默认文件）"
    )
    parser.add_argument(
        "--audio",
        type=Path,
        help="测试用的音频路径（可选，会自动查找默认文件）"
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=REPO_ROOT / "output" / "bench",
        help="基准测试输出目录"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新测试，即使环境未变化"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="仅检查环境状态，不运行测试"
    )
    
    args = parser.parse_args()
    
    # 生成当前环境指纹
    current_fingerprint = get_environment_fingerprint()
    saved_fingerprint = load_env_fingerprint()
    
    # 仅检查模式
    if args.check_only:
        print("\n" + "=" * 70)
        print("🔍 环境状态检查")
        print("=" * 70)
        
        if not saved_fingerprint:
            print("状态: ❌ 未初始化")
            print("建议: 运行 'python scripts/init_env.py' 进行初始化")
        else:
            print("状态: ✅ 已初始化")
            print(f"初始化时间: {saved_fingerprint.get('timestamp', '未知')}")
            print(f"环境哈希: {saved_fingerprint.get('hash', '未知')}")
            print(f"CPU: {saved_fingerprint.get('cpu_brand', saved_fingerprint.get('processor', '未知'))}")
            print(f"可用编码器: {', '.join(saved_fingerprint.get('available_encoders', []))}")
            
            if has_environment_changed(current_fingerprint, saved_fingerprint):
                print("\n⚠️  检测到环境变化，建议重新初始化")
            else:
                print("\n✅ 环境未变化，可以继续使用当前配置")
        
        print("=" * 70)
        return
    
    # 检查是否需要初始化或重新测试
    needs_init = False
    
    if not saved_fingerprint:
        print("\n📋 首次运行：需要进行环境初始化")
        needs_init = True
    elif args.force:
        print("\n🔄 强制重新测试")
        needs_init = True
    elif has_environment_changed(current_fingerprint, saved_fingerprint):
        print("\n⚠️  检测到环境变化，需要重新初始化")
        needs_init = True
    else:
        print("\n✅ 环境未变化，当前配置仍然有效")
        
        # 加载现有配置
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    config = json.load(f)
                print(f"当前使用编码器: {config.get('best_encoder', '未知')}")
                print(f"上次测试时间: {config.get('test_date', '未知')}")
                print(f"\n如需重新测试，请运行: python scripts/init_env.py --force")
            except Exception:
                pass
        return
    
    # 需要运行测试
    if not args.image or not args.audio:
        # 尝试查找默认测试文件
        default_image = REPO_ROOT / "assets" / "cover_sample" / "cover_sample.png"
        if not default_image.exists():
            default_image = REPO_ROOT / "assets" / "design" / "images"
            images = list(default_image.glob("*.png")) + list(default_image.glob("*.jpg"))
            if images:
                default_image = images[0]
            else:
                default_image = None
        
        default_audio = None
        audio_dirs = [
            REPO_ROOT / "output" / "audio",
            REPO_ROOT / "assets" / "song_sample",
        ]
        for audio_dir in audio_dirs:
            audios = list(audio_dir.glob("*full_mix.mp3"))
            if audios:
                default_audio = audios[0]
                break
            # 如果没有 full_mix，找任意 mp3
            audios = list(audio_dir.glob("*.mp3"))
            if audios:
                default_audio = audios[0]
                break
        
        if not default_image or not default_audio:
            print("\n❌ 错误: 需要指定测试文件")
            print("\n请使用以下参数指定测试文件：")
            print("  --image <封面图路径>")
            print("  --audio <音频路径>")
            print("\n或确保以下目录存在测试文件：")
            if not default_image:
                print(f"  图片: {REPO_ROOT / 'assets' / 'cover_sample'}/*.png")
            if not default_audio:
                print(f"  音频: {REPO_ROOT / 'output' / 'audio'}/*.mp3")
            sys.exit(1)
        
        args.image = default_image
        args.audio = default_audio
        print(f"\n使用默认测试文件:")
        print(f"  图片: {args.image}")
        print(f"  音频: {args.audio}")
    
    if not args.image.exists() or not args.audio.exists():
        print(f"\n❌ 错误: 测试文件不存在")
        print(f"  图片: {args.image} ({'✓' if args.image.exists() else '✗'})")
        print(f"  音频: {args.audio} ({'✓' if args.audio.exists() else '✗'})")
        sys.exit(1)
    
    # 运行基准测试
    config = run_initialization_benchmark(args.image, args.audio, args.outdir)
    
    if config:
        # 保存环境指纹
        save_env_fingerprint(current_fingerprint)
        print(f"\n✅ 环境指纹已更新")
    else:
        print("\n❌ 初始化失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()

