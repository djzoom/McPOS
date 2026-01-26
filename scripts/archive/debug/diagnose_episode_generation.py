#!/usr/bin/env python3
# coding: utf-8
"""
期数生成诊断工具

检查期数生成流程，诊断为什么只生成了部分文件。
"""
from __future__ import annotations

import sys
import json
import os
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "kat_rec_web" / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

try:
    from utils_logging import setup_logging, logger
    setup_logging()
except ImportError:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

# 颜色输出
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def check_file_timeline(episode_dir: Path, episode_id: str):
    """检查文件生成时间线"""
    if not episode_dir.exists():
        return False, f"Episode directory does not exist: {episode_dir}", {}
    
    files = {}
    for file_path in episode_dir.glob("*"):
        if file_path.is_file():
            mtime = os.path.getmtime(file_path)
            size = file_path.stat().st_size
            files[file_path.name] = {
                "mtime": mtime,
                "size": size,
                "datetime": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            }
    
    # 按时间排序
    sorted_files = sorted(files.items(), key=lambda x: x[1]["mtime"])
    
    return True, "OK", sorted_files


def check_expected_files(episode_dir: Path, episode_id: str):
    """检查预期文件是否存在"""
    expected_files = {
        "playlist": episode_dir / "playlist.csv",
        "manifest": episode_dir / f"{episode_id}_manifest.json",
        "playlist_metadata": episode_dir / "playlist_metadata.json",
        "cover": episode_dir / f"{episode_id}_cover.png",
        "title": episode_dir / f"{episode_id}_youtube_title.txt",
        "description": episode_dir / f"{episode_id}_youtube_description.txt",
        "captions": episode_dir / f"{episode_id}_youtube.srt",
        "tags": episode_dir / f"{episode_id}_tags.txt",
        "audio": episode_dir / f"{episode_id}_full_mix.mp3",
        "timeline": episode_dir / f"{episode_id}_timeline.csv",
    }
    
    results = {}
    for name, path in expected_files.items():
        exists = path.exists() and path.is_file()
        size = path.stat().st_size if exists else 0
        results[name] = {
            "exists": exists,
            "path": str(path),
            "size": size,
            "status": "✅" if exists and size > 0 else "❌"
        }
    
    return results


def analyze_generation_flow(episode_id: str, channel_id: str = "kat_lofi"):
    """分析生成流程"""
    # 直接使用路径，避免导入问题
    output_dir = REPO_ROOT / "channels" / channel_id / "output"
    episode_output_dir = output_dir / episode_id
    
    logger.info(f"{BLUE}🔍 期数生成流程诊断{NC}")
    logger.info("=" * 70)
    logger.info(f"期数 ID: {episode_id}")
    logger.info(f"频道 ID: {channel_id}")
    logger.info(f"输出目录: {episode_output_dir}")
    logger.info("")
    
    # 检查目录
    if not episode_output_dir.exists():
        logger.error(f"{RED}❌ 输出目录不存在: {episode_output_dir}{NC}")
        return False
    
    # 检查文件时间线
    logger.info(f"{BLUE}📅 文件生成时间线{NC}")
    logger.info("-" * 70)
    success, msg, files = check_file_timeline(episode_output_dir, episode_id)
    if not success:
        logger.error(f"{RED}{msg}{NC}")
        return False
    
    if not files:
        logger.warning(f"{YELLOW}⚠️  目录为空，没有生成任何文件{NC}")
        return False
    
    for name, info in files:
        size_kb = info["size"] / 1024
        logger.info(f"  {info['datetime']}: {name} ({size_kb:.1f} KB)")
    
    logger.info("")
    
    # 检查预期文件
    logger.info(f"{BLUE}📋 预期文件检查{NC}")
    logger.info("-" * 70)
    file_results = check_expected_files(episode_output_dir, episode_id)
    
    # 分类文件
    phase1_files = ["playlist", "manifest", "playlist_metadata"]  # init_episode
    phase2_files = ["cover", "title", "description", "captions", "tags"]  # 并行任务
    phase3_files = ["audio", "timeline"]  # remix
    
    phase1_status = all(file_results[f]["exists"] for f in phase1_files)
    phase2_status = all(file_results[f]["exists"] for f in phase2_files)
    phase3_status = all(file_results[f]["exists"] for f in phase3_files)
    
    logger.info(f"{BLUE}阶段1: init_episode (小文件并行准备){NC}")
    for name in phase1_files:
        result = file_results[name]
        status = f"{GREEN}✅{NC}" if result["exists"] else f"{RED}❌{NC}"
        logger.info(f"  {status} {name}: {result['path']}")
        if result["exists"]:
            logger.info(f"     大小: {result['size']} bytes")
    
    logger.info("")
    logger.info(f"{BLUE}阶段2: 文本资产 + 封面 (并行生成){NC}")
    for name in phase2_files:
        result = file_results[name]
        status = f"{GREEN}✅{NC}" if result["exists"] else f"{RED}❌{NC}"
        logger.info(f"  {status} {name}: {result['path']}")
        if result["exists"]:
            logger.info(f"     大小: {result['size']} bytes")
    
    logger.info("")
    logger.info(f"{BLUE}阶段3: 音频混音 (串行处理){NC}")
    for name in phase3_files:
        result = file_results[name]
        status = f"{GREEN}✅{NC}" if result["exists"] else f"{RED}❌{NC}"
        logger.info(f"  {status} {name}: {result['path']}")
        if result["exists"]:
            logger.info(f"     大小: {result['size']} bytes")
    
    logger.info("")
    
    # 诊断问题
    logger.info(f"{BLUE}🔬 问题诊断{NC}")
    logger.info("-" * 70)
    
    if not phase1_status:
        logger.error(f"{RED}❌ 阶段1未完成: init_episode 失败{NC}")
        return False
    
    if not phase2_status:
        missing = [f for f in phase2_files if not file_results[f]["exists"]]
        logger.warning(f"{YELLOW}⚠️  阶段2未完成: 以下文件缺失: {', '.join(missing)}{NC}")
        logger.info("")
        logger.info(f"{YELLOW}可能原因:{NC}")
        logger.info("  1. 任务创建失败但未抛出异常")
        logger.info("  2. 任务执行失败但错误被吞掉")
        logger.info("  3. 任务被阻塞（信号量耗尽或死锁）")
        logger.info("  4. 文件生成到错误的位置")
        logger.info("")
        logger.info(f"{YELLOW}检查方法:{NC}")
        logger.info("  1. 查看日志: grep '\\[PARALLEL\\]' .logs/backend.log | grep " + episode_id)
        logger.info("  2. 检查任务状态: 查看 WebSocket 消息")
        logger.info("  3. 检查信号量: 查看是否有任务在等待")
    
    if not phase3_status:
        missing = [f for f in phase3_files if not file_results[f]["exists"]]
        logger.warning(f"{YELLOW}⚠️  阶段3未完成: 以下文件缺失: {', '.join(missing)}{NC}")
        logger.info("")
        logger.info(f"{YELLOW}可能原因:{NC}")
        logger.info("  1. 阶段2未完成，导致阶段3未启动")
        logger.info("  2. remix 任务执行失败")
        logger.info("  3. FFmpeg 进程卡死或崩溃")
    
    logger.info("")
    logger.info("=" * 70)
    
    if phase1_status and phase2_status and phase3_status:
        logger.info(f"{GREEN}✅ 所有文件生成完成{NC}")
        return True
    else:
        logger.warning(f"{YELLOW}⚠️  部分文件缺失，请根据上述诊断修复{NC}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="诊断期数生成流程")
    parser.add_argument("episode_id", help="期数 ID (例如: 20251111)")
    parser.add_argument("--channel", default="kat_lofi", help="频道 ID")
    
    args = parser.parse_args()
    
    success = analyze_generation_flow(args.episode_id, args.channel)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

