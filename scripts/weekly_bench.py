#!/usr/bin/env python3
# coding: utf-8
"""
每周环境测试和渲染性能基准测试

功能：
1. 检测可用的编码器
2. 运行4种方法的并行基准测试
3. 选择最快的方法并保存配置
4. 每周提示查看测试结果
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CONFIG_FILE = REPO_ROOT / "config" / "best_encoder.json"


def load_best_encoder_config() -> Optional[Dict]:
    """加载保存的最佳编码器配置"""
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_best_encoder_config(config: Dict) -> None:
    """保存最佳编码器配置"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def should_rerun_test(config: Optional[Dict], force: bool = False) -> bool:
    """判断是否需要重新运行测试（超过7天、环境变化或强制）"""
    if force:
        return True
    if not config:
        return True
    
    # 检查环境是否变化
    try:
        from scripts.init_env import (
            get_environment_fingerprint,
            load_env_fingerprint,
            has_environment_changed
        )
        current_fp = get_environment_fingerprint()
        saved_fp = load_env_fingerprint()
        if has_environment_changed(current_fp, saved_fp):
            return True
    except Exception:
        pass  # 如果检查失败，继续检查时间
    
    # 检查时间（超过7天）
    test_date_str = config.get("test_date")
    if not test_date_str:
        return True
    try:
        test_date = datetime.fromisoformat(test_date_str)
        days_since_test = (datetime.now() - test_date).days
        return days_since_test >= 7
    except Exception:
        return True


def run_benchmark(image_path: Path, audio_path: Path, outdir: Path) -> Optional[Dict]:
    """运行基准测试并返回最快的方法"""
    print("=" * 60)
    print("开始每周环境测试和渲染性能基准测试...")
    print("=" * 60)
    
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
        result = subprocess.run(bench_cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        if result.returncode != 0:
            print(f"基准测试执行失败: {result.stderr}")
            return None
    except Exception as e:
        print(f"运行基准测试时出错: {e}")
        return None
    
    # 读取测试结果
    summary_file = outdir / "summary.json"
    if not summary_file.exists():
        print(f"未找到测试结果文件: {summary_file}")
        return None
    
    try:
        with summary_file.open("r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception as e:
        print(f"读取测试结果失败: {e}")
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
        print("没有找到成功的测试结果")
        return None
    
    # 提取最佳编码器信息
    best_method = best_result.get("method", "x264")
    best_encoder = best_result.get("encoder", "libx264")
    
    config = {
        "test_date": datetime.now().isoformat(),
        "best_method": best_method,
        "best_encoder": best_encoder,
        "elapsed_sec": best_result.get("elapsed_sec"),
        "filesize_mb": best_result.get("filesize_mb"),
        "summary_path": str(summary_file),
        "results": results
    }
    
    print("\n" + "=" * 60)
    print(f"✅ 测试完成！最快方法: {best_method} ({best_encoder})")
    print(f"   耗时: {best_time:.2f} 秒")
    print(f"   文件大小: {best_result.get('filesize_mb', 0):.2f} MB")
    print(f"   详细结果已保存到: {summary_file}")
    print("=" * 60)
    
    return config


def check_and_prompt(config: Optional[Dict]) -> None:
    """检查是否需要提示用户查看测试结果"""
    if not config:
        print("\n⚠️  未找到编码器测试配置，建议运行每周测试：")
        print("   python scripts/weekly_bench.py")
        return
    
    test_date_str = config.get("test_date")
    if not test_date_str:
        return
    
    try:
        test_date = datetime.fromisoformat(test_date_str)
        days_since_test = (datetime.now() - test_date).days
        
        if days_since_test >= 7:
            print("\n" + "=" * 60)
            print("📊 每周测试提醒")
            print("=" * 60)
            print(f"上次测试时间: {test_date.strftime('%Y-%m-%d %H:%M')}")
            print(f"已过去 {days_since_test} 天")
            print(f"当前使用编码器: {config.get('best_encoder', '未知')}")
            print("\n建议重新运行测试以确保使用最快方法：")
            print("  python scripts/weekly_bench.py --image <cover.png> --audio <audio.mp3>")
            print(f"\n或查看上次测试结果: {config.get('summary_path', 'N/A')}")
            print("=" * 60)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="每周环境测试和渲染性能基准测试")
    parser.add_argument("--image", type=Path, help="测试用的封面图路径")
    parser.add_argument("--audio", type=Path, help="测试用的音频路径")
    parser.add_argument("--outdir", type=Path, default=REPO_ROOT / "output" / "bench", help="输出目录")
    parser.add_argument("--force", action="store_true", help="强制重新测试，即使未超过7天")
    parser.add_argument("--check-only", action="store_true", help="仅检查是否需要测试，不运行")
    
    args = parser.parse_args()
    
    # 加载现有配置
    config = load_best_encoder_config()
    
    # 仅检查模式
    if args.check_only:
        check_and_prompt(config)
        return
    
    # 检查是否需要测试
    if not should_rerun_test(config, args.force):
        print(f"✅ 上次测试在 {(datetime.now() - datetime.fromisoformat(config['test_date'])).days} 天前")
        print(f"当前使用编码器: {config.get('best_encoder', '未知')}")
        print("如需重新测试，请使用 --force 参数")
        check_and_prompt(config)
        return
    
    # 需要运行测试
    if not args.image or not args.audio:
        # 尝试使用默认路径
        default_image = REPO_ROOT / "assets" / "design" / "images"
        default_audio = REPO_ROOT / "output" / "audio"
        
        images = list(default_image.glob("*.png")) + list(default_image.glob("*.jpg"))
        audios = list(default_audio.glob("*full_mix.mp3"))
        
        if not images or not audios:
            print("错误: 需要指定 --image 和 --audio 参数")
            print("或确保以下目录存在测试文件：")
            print(f"  图片: {default_image}/*.png")
            print(f"  音频: {default_audio}/*full_mix.mp3")
            sys.exit(1)
        
        args.image = images[0]
        args.audio = audios[0]
        print(f"使用默认测试文件:")
        print(f"  图片: {args.image}")
        print(f"  音频: {args.audio}")
    
    if not args.image.exists() or not args.audio.exists():
        print(f"错误: 测试文件不存在")
        print(f"  图片: {args.image} ({'存在' if args.image.exists() else '不存在'})")
        print(f"  音频: {args.audio} ({'存在' if args.audio.exists() else '不存在'})")
        sys.exit(1)
    
    # 运行基准测试
    result_config = run_benchmark(args.image, args.audio, args.outdir)
    
    if result_config:
        # 保存配置
        save_best_encoder_config(result_config)
        print(f"\n✅ 配置已保存到: {CONFIG_FILE}")
        print(f"   接下来一周将使用: {result_config['best_encoder']}")
    else:
        print("\n❌ 测试失败，无法确定最佳编码器")
        sys.exit(1)


if __name__ == "__main__":
    main()

