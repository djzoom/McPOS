#!/usr/bin/env python3
# coding: utf-8
"""
广度优先生成工具

按照工作流阶段批量生成所有期数：
1. 阶段1：选歌+歌单（所有期数）
2. 阶段2：封面+选色+标题（所有期数）
3. 阶段3：YouTube资源（标题、描述、SRT，所有期数）
4. 阶段4：音频混音（所有期数）
5. 阶段5：视频合成（所有期数）
6. 阶段6：检查并打包（集齐资料的期数）

每个阶段：
- 监控output目录，如果全清空提示重置排播表
- 跳过已生成的文件（除非使用--force）
- 文件体积从小到大排列

用法：
    python scripts/local_picker/breadth_first_generate.py          # 生成所有pending期数
    python scripts/local_picker/breadth_first_generate.py --force # 强制重新生成所有文件
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT / "src"))

# 尝试从配置常量导入超时值
try:
    from src.core.config_constants import (
        STAGE1_PLAYLIST_TIMEOUT,
        STAGE2_YOUTUBE_ASSETS_TIMEOUT,
        STAGE3_AUDIO_TIMEOUT,
        STAGE4_VIDEO_TIMEOUT,
    )
except ImportError:
    # 回退到硬编码值（过渡期）
    STAGE1_PLAYLIST_TIMEOUT = 300
    STAGE2_YOUTUBE_ASSETS_TIMEOUT = 120
    STAGE3_AUDIO_TIMEOUT = 600
    STAGE4_VIDEO_TIMEOUT = 3600

try:
    from schedule_master import ScheduleMaster
    from episode_status import is_pending_status
    from utils import get_final_output_dir
    SCHEDULE_AVAILABLE = True
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    SCHEDULE_AVAILABLE = False
    sys.exit(1)

def check_output_cleared(output_dir: Path) -> bool:
    """检查output目录是否被清空"""
    if not output_dir.exists():
        return True
    
    # 检查是否有任何期数相关文件
    episode_pattern = re.compile(r'^\d{8}_')
    for item in output_dir.iterdir():
        if item.is_dir():
            if item.name != "logs" and re.match(r'^\d{4}-\d{2}-\d{2}_', item.name):
                return False  # 有期数文件夹
        elif item.is_file():
            if item.name not in [".gitkeep", "run.json"] and episode_pattern.match(item.name):
                return False  # 有期数文件
    
    # 检查logs目录是否有内容
    logs_dir = output_dir / "logs"
    if logs_dir.exists():
        for item in logs_dir.iterdir():
            if item.is_file():
                return False  # logs目录有文件
    
    return True  # output目录基本清空


def check_episode_files_complete(id_str: str, output_dir: Path, schedule_date: datetime, title: str) -> Tuple[bool, List[str]]:
    """检查期数文件是否完整"""
    final_dir = get_final_output_dir(schedule_date, title)
    
    # 检查必需文件
    required_files = [
        f"{id_str}_playlist.csv",
        f"{id_str}_cover.png",
        f"{id_str}_youtube.srt",
        f"{id_str}_youtube_title.txt",
        f"{id_str}_youtube_description.txt",
    ]
    
    # 音频文件（至少一个）
    audio_files = [
        f"{id_str}_full_mix.mp3",
        f"{id_str}_playlist_full_mix.mp3",
    ]
    
    # 视频文件（可选但推荐）
    video_files = [
        f"{id_str}_youtube.mp4",
        f"{id_str}_youtube.mov",
    ]
    
    missing = []
    
    # 检查必需文件（在final_dir或output根目录）
    for req_file in required_files:
        final_path = final_dir / req_file
        output_path = output_dir / req_file
        if not final_path.exists() and not output_path.exists():
            missing.append(req_file)
    
    # 检查音频（至少需要一个）
    has_audio = False
    for audio_file in audio_files:
        if (final_dir / audio_file).exists() or (output_dir / audio_file).exists():
            has_audio = True
            break
    if not has_audio:
        missing.append("音频文件（full_mix.mp3）")
    
    return len(missing) == 0, missing


def get_pending_episodes(schedule: ScheduleMaster) -> List[Dict]:
    """获取所有pending期数"""
    pending = []
    for ep in schedule.episodes:
        status = ep.get("status", "待制作")
        if is_pending_status(status):
            pending.append(ep)
    return sorted(pending, key=lambda x: x.get("episode_id", ""))


def stage1_generate_playlists(episodes: List[Dict], output_dir: Path, force: bool = False) -> Dict[str, bool]:
    """阶段1：生成所有期数的歌单和封面"""
    results = {}
    
    print("\n" + "=" * 70)
    print("📋 阶段1：生成歌单和封面（所有期数）")
    print("=" * 70)
    
    for i, ep in enumerate(episodes, 1):
        episode_id = ep.get("episode_id", "")
        if not episode_id:
            continue
        
        print(f"\n[{i}/{len(episodes)}] 处理期数: {episode_id}")
        
        # 检查output是否被清空（仅在第一次检查时提示）
        if i == 1 and check_output_cleared(output_dir):
            print("\n⚠️  提示：output目录为空（这是正常的，如果是刚创建排播表或刚重置）")
            print("   即将开始生成内容...")
            # 如果是第一次检查且目录为空，自动继续（不中断）
        
        # 检查文件是否已存在（在output根目录或最终文件夹）
        playlist_path = output_dir / f"{episode_id}_playlist.csv"
        cover_path = output_dir / f"{episode_id}_cover.png"
        
        # 也检查最终文件夹（如果已打包）
        schedule_date_str = ep.get("schedule_date", "")
        title = ep.get("title", "")
        if schedule_date_str and title:
            try:
                schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                final_dir = get_final_output_dir(schedule_date, title)
                final_playlist = final_dir / f"{episode_id}_playlist.csv"
                final_cover = final_dir / f"{episode_id}_cover.png"
                
                # 如果最终文件夹中有文件，使用最终文件夹的路径
                if final_playlist.exists():
                    playlist_path = final_playlist
                if final_cover.exists():
                    cover_path = final_cover
            except (ValueError, OSError, AttributeError) as e:
                # 日期解析失败或路径构造失败，继续使用output根目录的路径
                # 这是正常的（如果期数还未生成最终文件夹），静默处理
                pass
        
        if not force and playlist_path.exists() and cover_path.exists():
            print(f"  ✅ 歌单和封面已存在，跳过")
            results[episode_id] = True
            continue
        
        # 生成歌单和封面（广度优先：只生成这一阶段的内容）
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
            "--font_name", "Lora-Regular",
            "--episode-id", episode_id,
            "--no-remix",      # 跳过音频（阶段3）
            "--no-video",      # 跳过视频（阶段4）
            "--no-youtube",    # 跳过YouTube资源（阶段2）
        ]
        if force:
            cmd.append("--force")
        
        try:
            # 实时显示输出，以便用户看到进度（但过滤掉过多细节）
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=STAGE1_PLAYLIST_TIMEOUT,
                cwd=REPO_ROOT  # 确保在项目根目录运行
            )
            if result.returncode == 0:
                # 检查文件是否真的生成了（在output根目录或最终文件夹）
                playlist_found = playlist_path.exists()
                cover_found = cover_path.exists()
                
                # 如果output根目录没找到，检查最终文件夹
                if not playlist_found or not cover_found:
                    schedule_date_str = ep.get("schedule_date", "")
                    title = ep.get("title", "")
                    if schedule_date_str and title:
                        try:
                            schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                            final_dir = get_final_output_dir(schedule_date, title)
                            if not playlist_found:
                                final_playlist = final_dir / f"{episode_id}_playlist.csv"
                                if final_playlist.exists():
                                    playlist_found = True
                                    playlist_path = final_playlist
                            if not cover_found:
                                final_cover = final_dir / f"{episode_id}_cover.png"
                                if final_cover.exists():
                                    cover_found = True
                                    cover_path = final_cover
                        except (ValueError, OSError, AttributeError):
                            # 路径解析失败，继续查找
                            pass
                
                if playlist_found and cover_found:
                    print(f"  ✅ 歌单和封面生成成功")
                    # 尝试记录成功日志
                    try:
                        from src.core.logger import get_logger
                        logger = get_logger()
                        logger.info(
                            "breadth_first.stage1.episode.success",
                            f"期数 {episode_id} 歌单和封面生成成功",
                            episode_id=episode_id
                        )
                    except ImportError:
                        pass
                    results[episode_id] = True
                else:
                    print(f"  ⚠️  命令成功但文件未找到")
                    print(f"     歌单: {'✅' if playlist_found else '❌'} {playlist_path}")
                    print(f"     封面: {'✅' if cover_found else '❌'} {cover_path}")
                    # 输出详细信息以便调试
                    if result.stdout:
                        # 只显示关键输出行
                        key_lines = [line for line in result.stdout.split('\n') 
                                    if any(kw in line for kw in ['歌单已写入', '封面已生成', '错误', '失败', 'Error'])]
                        if key_lines:
                            print(f"  📋 关键输出: {key_lines[-3:]}")
                    results[episode_id] = False
            else:
                # 显示更详细的错误信息
                error_msg = result.stderr if result.stderr else result.stdout
                if error_msg:
                    # 提取关键错误信息（跳过usage信息）
                    error_lines = error_msg.split('\n')
                    for line in error_lines:
                        if line.strip() and not line.startswith('usage:') and '--' not in line[:20]:
                            error_msg = line[:200]
                            break
                    if not error_msg or error_msg.startswith('usage:'):
                        error_msg = "参数错误或脚本执行失败"
                else:
                    error_msg = "未知错误"
                print(f"  ❌ 生成失败: {error_msg}")
                # 调试信息：显示完整命令
                print(f"  🔍 执行命令: {' '.join(cmd)}")
                # 尝试记录错误日志
                try:
                    from src.core.logger import get_logger
                    logger = get_logger()
                    logger.error(
                        "breadth_first.stage1.episode.failed",
                        f"期数 {episode_id} 生成失败: {error_msg}",
                        episode_id=episode_id,
                        metadata={"error": error_msg[:200]}
                    )
                except ImportError:
                    pass
                results[episode_id] = False
        except subprocess.TimeoutExpired:
            print(f"  ⏱️  生成超时（>300秒）")
            results[episode_id] = False
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            print(f"  ❌ 异常: {type(e).__name__}: {e}")
            results[episode_id] = False
        except Exception as e:
            print(f"  ❌ 未知异常: {type(e).__name__}: {e}")
            results[episode_id] = False
    
    return results


def stage2_generate_youtube_assets(episodes: List[Dict], output_dir: Path, force: bool = False) -> Dict[str, bool]:
    """阶段2：生成YouTube资源（标题、描述、SRT）"""
    results = {}
    
    print("\n" + "=" * 70)
    print("📹 阶段2：生成YouTube资源（所有期数）")
    print("=" * 70)
    
    for i, ep in enumerate(episodes, 1):
        episode_id = ep.get("episode_id", "")
        title = ep.get("title", "")
        if not episode_id:
            continue
        
        print(f"\n[{i}/{len(episodes)}] 处理期数: {episode_id}")
        
        # 检查必需文件（歌单）- 先在output根目录，再在最终文件夹
        playlist_path = output_dir / f"{episode_id}_playlist.csv"
        
        # 如果根目录没有，检查最终文件夹
        if not playlist_path.exists():
            schedule_date_str = ep.get("schedule_date", "")
            title = ep.get("title", "")
            if schedule_date_str and title:
                try:
                    schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                    final_dir = get_final_output_dir(schedule_date, title)
                    final_playlist = final_dir / f"{episode_id}_playlist.csv"
                    if final_playlist.exists():
                        playlist_path = final_playlist
                except (ValueError, OSError, AttributeError):
                    # 路径解析失败，继续使用根目录路径
                    pass
        
        if not playlist_path.exists():
            print(f"  ⚠️  歌单文件不存在，跳过")
            results[episode_id] = False
            continue
        
        # 检查YouTube资源是否已存在（output根目录或最终文件夹）
        srt_path = output_dir / f"{episode_id}_youtube.srt"
        title_path = output_dir / f"{episode_id}_youtube_title.txt"
        desc_path = output_dir / f"{episode_id}_youtube_description.txt"
        
        # 检查最终文件夹
        schedule_date_str = ep.get("schedule_date", "")
        title = ep.get("title", "")
        if schedule_date_str and title:
            try:
                schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                final_dir = get_final_output_dir(schedule_date, title)
                if not srt_path.exists():
                    final_srt = final_dir / f"{episode_id}_youtube.srt"
                    if final_srt.exists():
                        srt_path = final_srt
                if not title_path.exists():
                    final_title = final_dir / f"{episode_id}_youtube_title.txt"
                    if final_title.exists():
                        title_path = final_title
                if not desc_path.exists():
                    final_desc = final_dir / f"{episode_id}_youtube_description.txt"
                    if final_desc.exists():
                        desc_path = final_desc
            except (ValueError, OSError, AttributeError):
                # 路径解析或文件检查失败，继续使用默认路径
                pass
        
        if not force and srt_path.exists() and title_path.exists() and desc_path.exists():
            print(f"  ✅ YouTube资源已存在，跳过")
            results[episode_id] = True
            continue
        
        # 获取标题（从排播表或从歌单提取）
        if not title:
            try:
                from utils import extract_title_from_playlist
                title = extract_title_from_playlist(playlist_path) or f"Episode {episode_id}"
            except:
                title = f"Episode {episode_id}"
        
        # 生成YouTube资源（输出到playlist所在目录，如果是最终文件夹则输出到那里）
        output_for_assets = playlist_path.parent if playlist_path.parent != output_dir else output_dir
        
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "generate_youtube_assets.py"),
            "--playlist", str(playlist_path),
            "--title", title,
            "--output", str(output_for_assets),
        ]
        
        # 传递API密钥
        openai_key = os.environ.get("OPENAI_API_KEY")
        openai_base = os.environ.get("OPENAI_BASE_URL")
        if openai_key:
            cmd.extend(["--openai-api-key", openai_key])
        if openai_base:
            cmd.extend(["--openai-base-url", openai_base])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=STAGE2_YOUTUBE_ASSETS_TIMEOUT)
            if result.returncode == 0:
                # 验证文件是否真的生成了（在output_for_assets目录）
                srt_check = output_for_assets / f"{episode_id}_youtube.srt"
                title_check = output_for_assets / f"{episode_id}_youtube_title.txt"
                desc_check = output_for_assets / f"{episode_id}_youtube_description.txt"
                
                if srt_check.exists() and title_check.exists() and desc_check.exists():
                    print(f"  ✅ YouTube资源生成成功")
                    results[episode_id] = True
                else:
                    print(f"  ⚠️  命令成功但文件未找到在 {output_for_assets}")
                    print(f"     期望位置: {output_for_assets}")
                    print(f"     SRT: {'✅' if srt_check.exists() else '❌'} {srt_check}")
                    print(f"     Title: {'✅' if title_check.exists() else '❌'} {title_check}")
                    print(f"     Desc: {'✅' if desc_check.exists() else '❌'} {desc_check}")
                    results[episode_id] = False
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                if error_msg:
                    error_lines = error_msg.split('\n')
                    for line in error_lines:
                        if line.strip() and not line.startswith('usage:'):
                            error_msg = line[:200]
                            break
                print(f"  ❌ 生成失败: {error_msg[:200] if error_msg else 'Unknown error'}")
                # 尝试记录错误日志
                try:
                    from src.core.logger import get_logger
                    logger = get_logger()
                    logger.error(
                        "breadth_first.stage2.episode.failed",
                        f"期数 {episode_id} YouTube资源生成失败: {error_msg[:200] if error_msg else 'Unknown error'}",
                        episode_id=episode_id,
                        metadata={"error": error_msg[:200] if error_msg else 'Unknown error'}
                    )
                except ImportError:
                    pass
                results[episode_id] = False
        except subprocess.TimeoutExpired:
            print(f"  ⏱️  生成超时（>120秒）")
            try:
                from src.core.logger import get_logger
                logger = get_logger()
                logger.warning(
                    "breadth_first.stage2.episode.timeout",
                    f"期数 {episode_id} YouTube资源生成超时",
                    episode_id=episode_id
                )
            except ImportError:
                pass
            results[episode_id] = False
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            print(f"  ❌ 异常: {type(e).__name__}: {e}")
            results[episode_id] = False
        except Exception as e:
            print(f"  ❌ 未知异常: {type(e).__name__}: {e}")
            results[episode_id] = False
    
    # 记录阶段完成统计
    success_count = sum(1 for v in results.values() if v)
    if HAS_LOGGER and logger:
        logger.info(
            "breadth_first.stage2.completed",
            f"阶段2完成：成功 {success_count}/{len(results)}",
            metadata={"success_count": success_count, "total_count": len(results)}
        )
    
    return results


def stage3_generate_audio(episodes: List[Dict], output_dir: Path, force: bool = False) -> Dict[str, bool]:
    """阶段3：生成所有期数的音频混音"""
    # 尝试获取结构化日志（可选）
    try:
        from src.core.logger import get_logger
        logger = get_logger()
        HAS_LOGGER = True
    except ImportError:
        logger = None
        HAS_LOGGER = False
    
    results = {}
    
    if HAS_LOGGER and logger:
        logger.info(
            "breadth_first.stage3.started",
            f"开始阶段3：生成音频混音（{len(episodes)}期数）",
            metadata={"episode_count": len(episodes), "force": force}
        )
    
    print("\n" + "=" * 70)
    print("🎵 阶段3：生成音频混音（所有期数）")
    print("=" * 70)
    
    for i, ep in enumerate(episodes, 1):
        episode_id = ep.get("episode_id", "")
        if not episode_id:
            continue
        
        print(f"\n[{i}/{len(episodes)}] 处理期数: {episode_id}")
        
        # 检查必需文件（歌单）- 先在output根目录，再在最终文件夹
        playlist_path = output_dir / f"{episode_id}_playlist.csv"
        
        # 如果根目录没有，检查最终文件夹
        if not playlist_path.exists():
            schedule_date_str = ep.get("schedule_date", "")
            title = ep.get("title", "")
            if schedule_date_str and title:
                try:
                    schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                    final_dir = get_final_output_dir(schedule_date, title)
                    final_playlist = final_dir / f"{episode_id}_playlist.csv"
                    if final_playlist.exists():
                        playlist_path = final_playlist
                except (ValueError, OSError, AttributeError):
                    # 路径解析失败，继续使用根目录路径
                    pass
        
        if not playlist_path.exists():
            print(f"  ⚠️  歌单文件不存在，跳过")
            results[episode_id] = False
            continue
        
        # 检查音频是否已存在（output根目录或最终文件夹）
        audio_patterns = [
            output_dir / f"{episode_id}_full_mix.mp3",
            output_dir / f"{episode_id}_playlist_full_mix.mp3",
        ]
        has_audio = any(p.exists() for p in audio_patterns)
        
        # 如果根目录没有，检查最终文件夹
        if not has_audio:
            schedule_date_str = ep.get("schedule_date", "")
            title = ep.get("title", "")
            if schedule_date_str and title:
                try:
                    schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                    final_dir = get_final_output_dir(schedule_date, title)
                    final_audio_patterns = [
                        final_dir / f"{episode_id}_full_mix.mp3",
                        final_dir / f"{episode_id}_playlist_full_mix.mp3",
                    ]
                    has_audio = any(p.exists() for p in final_audio_patterns)
                except (ValueError, OSError, AttributeError):
                    # 路径解析失败，继续使用根目录路径
                    pass
        
        if not force and has_audio:
            print(f"  ✅ 音频文件已存在，跳过")
            results[episode_id] = True
            continue
        
        # 生成音频
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "remix_mixtape.py"),
            "--playlist", str(playlist_path),
        ]
        
        try:
            # 实时显示输出（音频生成可能需要较长时间）
            print(f"  ⏳ 正在生成音频（这可能需要几分钟）...")
            result = subprocess.run(cmd, timeout=STAGE3_AUDIO_TIMEOUT)
            if result.returncode == 0:
                # 验证音频文件是否生成
                audio_found = False
                audio_patterns = [
                    output_dir / f"{episode_id}_full_mix.mp3",
                    output_dir / f"{episode_id}_playlist_full_mix.mp3",
                ]
                if not any(p.exists() for p in audio_patterns):
                    # 检查最终文件夹
                    schedule_date_str = ep.get("schedule_date", "")
                    title = ep.get("title", "")
                    if schedule_date_str and title:
                        try:
                            schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                            final_dir = get_final_output_dir(schedule_date, title)
                            final_audio_patterns = [
                                final_dir / f"{episode_id}_full_mix.mp3",
                                final_dir / f"{episode_id}_playlist_full_mix.mp3",
                            ]
                            audio_found = any(p.exists() for p in final_audio_patterns)
                        except (ValueError, OSError, AttributeError):
                            # 路径解析失败，继续查找
                            pass
                
                if audio_found or any(p.exists() for p in audio_patterns):
                    print(f"  ✅ 音频生成成功")
                    # 尝试记录成功日志
                    try:
                        from src.core.logger import get_logger
                        logger = get_logger()
                        logger.info(
                            "breadth_first.stage3.episode.success",
                            f"期数 {episode_id} 音频生成成功",
                            episode_id=episode_id
                        )
                    except ImportError:
                        pass
                    results[episode_id] = True
                else:
                    print(f"  ⚠️  命令成功但音频文件未找到")
                    results[episode_id] = False
            else:
                error_msg = f"退出码: {result.returncode}"
                print(f"  ❌ 生成失败（退出码: {result.returncode}）")
                # 尝试记录错误日志
                try:
                    from src.core.logger import get_logger
                    logger = get_logger()
                    logger.error(
                        "breadth_first.stage3.episode.failed",
                        f"期数 {episode_id} 音频生成失败: {error_msg}",
                        episode_id=episode_id,
                        metadata={"returncode": result.returncode}
                    )
                except ImportError:
                    pass
                results[episode_id] = False
        except subprocess.TimeoutExpired:
            print(f"  ⏱️  生成超时（>600秒）")
            # 尝试记录超时日志
            try:
                from src.core.logger import get_logger
                logger = get_logger()
                logger.warning(
                    "breadth_first.stage3.episode.timeout",
                    f"期数 {episode_id} 音频生成超时",
                    episode_id=episode_id
                )
            except ImportError:
                pass
            results[episode_id] = False
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            print(f"  ❌ 异常: {type(e).__name__}: {e}")
            results[episode_id] = False
        except Exception as e:
            print(f"  ❌ 未知异常: {type(e).__name__}: {e}")
            results[episode_id] = False
    
    # 记录阶段完成统计
    success_count = sum(1 for v in results.values() if v)
    if HAS_LOGGER and logger:
        logger.info(
            "breadth_first.stage3.completed",
            f"阶段3完成：成功 {success_count}/{len(results)}",
            metadata={"success_count": success_count, "total_count": len(results)}
        )
    
    return results


def stage4_generate_videos(episodes: List[Dict], output_dir: Path, force: bool = False) -> Dict[str, bool]:
    """阶段4：生成所有期数的视频"""
    # 尝试获取结构化日志（可选）
    try:
        from src.core.logger import get_logger
        logger = get_logger()
        HAS_LOGGER = True
    except ImportError:
        logger = None
        HAS_LOGGER = False
    
    results = {}
    
    if HAS_LOGGER and logger:
        logger.info(
            "breadth_first.stage4.started",
            f"开始阶段4：生成视频（{len(episodes)}期数）",
            metadata={"episode_count": len(episodes), "force": force}
        )
    
    print("\n" + "=" * 70)
    print("🎬 阶段4：生成视频（所有期数）")
    print("=" * 70)
    
    for i, ep in enumerate(episodes, 1):
        episode_id = ep.get("episode_id", "")
        if not episode_id:
            continue
        
        print(f"\n[{i}/{len(episodes)}] 处理期数: {episode_id}")
        
        # 检查必需文件（封面和音频）- 先在output根目录，再在最终文件夹
        cover_path = output_dir / f"{episode_id}_cover.png"
        audio_patterns = [
            output_dir / f"{episode_id}_full_mix.mp3",
            output_dir / f"{episode_id}_playlist_full_mix.mp3",
        ]
        has_audio = any(p.exists() for p in audio_patterns)
        
        # 如果根目录没有，检查最终文件夹
        schedule_date_str = ep.get("schedule_date", "")
        title = ep.get("title", "")
        final_dir = None
        if schedule_date_str and title:
            try:
                schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                final_dir = get_final_output_dir(schedule_date, title)
                if not cover_path.exists():
                    final_cover = final_dir / f"{episode_id}_cover.png"
                    if final_cover.exists():
                        cover_path = final_cover
                if not has_audio:
                    final_audio_patterns = [
                        final_dir / f"{episode_id}_full_mix.mp3",
                        final_dir / f"{episode_id}_playlist_full_mix.mp3",
                    ]
                    has_audio = any(p.exists() for p in final_audio_patterns)
            except (ValueError, OSError, AttributeError):
                # 路径解析或文件检查失败，继续使用默认路径
                pass
        
        if not cover_path.exists():
            print(f"  ⚠️  封面文件不存在，跳过")
            results[episode_id] = False
            continue
        
        if not has_audio:
            print(f"  ⚠️  音频文件不存在，跳过")
            results[episode_id] = False
            continue
        
        # 检查视频是否已存在（output根目录或最终文件夹）
        video_patterns = [
            output_dir / f"{episode_id}_youtube.mp4",
            output_dir / f"{episode_id}_youtube.mov",
        ]
        has_video = any(p.exists() for p in video_patterns)
        
        # 如果根目录没有，检查最终文件夹
        if not has_video and final_dir:
            final_video_patterns = [
                final_dir / f"{episode_id}_youtube.mp4",
                final_dir / f"{episode_id}_youtube.mov",
            ]
            has_video = any(p.exists() for p in final_video_patterns)
        
        if not force and has_video:
            print(f"  ✅ 视频文件已存在，跳过")
            results[episode_id] = True
            continue
        
        # 生成视频（使用--no-youtube，因为YouTube资源已在阶段2生成）
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
            "--episode-id", episode_id,
            "--no-youtube",  # 跳过YouTube资源生成
        ]
        if force:
            cmd.append("--force")
        
        try:
            # 视频生成可能需要较长时间，不捕获输出以便实时显示进度
            result = subprocess.run(cmd, timeout=STAGE4_VIDEO_TIMEOUT)
            if result.returncode == 0:
                print(f"  ✅ 视频生成成功")
                # 尝试记录成功日志
                try:
                    from src.core.logger import get_logger
                    logger = get_logger()
                    logger.info(
                        "breadth_first.stage4.episode.success",
                        f"期数 {episode_id} 视频生成成功",
                        episode_id=episode_id
                    )
                except ImportError:
                    pass
                results[episode_id] = True
            else:
                error_msg = f"退出码: {result.returncode}"
                print(f"  ❌ 视频生成失败")
                # 尝试记录错误日志
                try:
                    from src.core.logger import get_logger
                    logger = get_logger()
                    logger.error(
                        "breadth_first.stage4.episode.failed",
                        f"期数 {episode_id} 视频生成失败: {error_msg}",
                        episode_id=episode_id,
                        metadata={"returncode": result.returncode}
                    )
                except ImportError:
                    pass
                results[episode_id] = False
        except subprocess.TimeoutExpired:
            print(f"  ⏱️  生成超时（>3600秒）")
            # 尝试记录超时日志
            try:
                from src.core.logger import get_logger
                logger = get_logger()
                logger.warning(
                    "breadth_first.stage4.episode.timeout",
                    f"期数 {episode_id} 视频生成超时",
                    episode_id=episode_id
                )
            except ImportError:
                pass
            results[episode_id] = False
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            print(f"  ❌ 异常: {type(e).__name__}: {e}")
            results[episode_id] = False
        except Exception as e:
            print(f"  ❌ 未知异常: {type(e).__name__}: {e}")
            results[episode_id] = False
    
    # 记录阶段完成统计
    success_count = sum(1 for v in results.values() if v)
    if HAS_LOGGER and logger:
        logger.info(
            "breadth_first.stage4.completed",
            f"阶段4完成：成功 {success_count}/{len(results)}",
            metadata={"success_count": success_count, "total_count": len(results)}
        )
    
    return results


def stage5_package_episodes(episodes: List[Dict], output_dir: Path, schedule: ScheduleMaster) -> Dict[str, bool]:
    """阶段5：检查并打包集齐资料的期数"""
    # 尝试获取结构化日志（可选）
    try:
        from src.core.logger import get_logger
        logger = get_logger()
        HAS_LOGGER = True
    except ImportError:
        logger = None
        HAS_LOGGER = False
    
    results = {}
    
    if HAS_LOGGER and logger:
        logger.info(
            "breadth_first.stage5.started",
            f"开始阶段5：检查并打包期数（{len(episodes)}期数）",
            metadata={"episode_count": len(episodes)}
        )
    
    print("\n" + "=" * 70)
    print("📦 阶段5：检查并打包期数")
    print("=" * 70)
    
    for i, ep in enumerate(episodes, 1):
        episode_id = ep.get("episode_id", "")
        if not episode_id:
            continue
        
        print(f"\n[{i}/{len(episodes)}] 检查期数: {episode_id}")
        
        # 获取期数信息
        schedule_date_str = ep.get("schedule_date", "")
        title = ep.get("title", "")
        
        if not schedule_date_str or not title:
            print(f"  ⚠️  期数信息不完整，跳过")
            results[episode_id] = False
            continue
        
        try:
            schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
        except:
            try:
                schedule_date = datetime.strptime(episode_id, "%Y%m%d")
            except:
                print(f"  ⚠️  无法解析日期，跳过")
                results[episode_id] = False
                continue
        
        # 检查文件是否完整
        is_complete, missing = check_episode_files_complete(episode_id, output_dir, schedule_date, title)
        
        if not is_complete:
            print(f"  ⏳ 文件未集齐（缺失: {', '.join(missing)}），跳过打包")
            results[episode_id] = False
            continue
        
        # 打包文件到最终文件夹
        final_dir = get_final_output_dir(schedule_date, title)
        final_dir.mkdir(parents=True, exist_ok=True)
        
        # 收集所有需要打包的文件
        files_to_move = []
        episode_pattern = re.compile(rf'^{re.escape(episode_id)}_')
        
        for item in output_dir.iterdir():
            if item.is_file() and episode_pattern.match(item.name):
                files_to_move.append(item)
        
        # 移动文件
        moved_count = 0
        for src_file in files_to_move:
            dst_file = final_dir / src_file.name
            if not dst_file.exists():
                try:
                    shutil.move(str(src_file), str(dst_file))
                    moved_count += 1
                except (PermissionError, OSError, FileNotFoundError) as e:
                    print(f"  ⚠️  移动文件失败 {src_file.name}: {type(e).__name__}: {e}")
                    # 尝试记录警告日志
                    try:
                        from src.core.logger import get_logger
                        logger = get_logger()
                        logger.warning(
                            "breadth_first.stage5.file_move.failed",
                            f"期数 {episode_id} 移动文件失败: {src_file.name}",
                            episode_id=episode_id,
                            metadata={"file": src_file.name, "error": str(e)}
                        )
                    except ImportError:
                        pass
                except Exception as e:
                    print(f"  ⚠️  移动文件失败 {src_file.name}: {type(e).__name__}: {e}")
            else:
                # 目标已存在，删除源文件
                try:
                    src_file.unlink()
                except (PermissionError, FileNotFoundError, OSError):
                    # 文件删除失败（可能已被删除或权限不足），忽略
                    pass
        
        if moved_count > 0:
            print(f"  ✅ 已打包 {moved_count} 个文件到: {final_dir.name}")
            # 尝试记录成功日志
            try:
                from src.core.logger import get_logger
                logger = get_logger()
                logger.info(
                    "breadth_first.stage5.episode.success",
                    f"期数 {episode_id} 打包成功，移动了 {moved_count} 个文件",
                    episode_id=episode_id,
                    metadata={"moved_count": moved_count, "final_dir": str(final_dir.name)}
                )
            except ImportError:
                pass
            results[episode_id] = True
        else:
            print(f"  ℹ️  所有文件已在文件夹中")
            # 尝试记录信息日志
            try:
                from src.core.logger import get_logger
                logger = get_logger()
                logger.info(
                    "breadth_first.stage5.episode.skipped",
                    f"期数 {episode_id} 所有文件已在文件夹中，无需打包",
                    episode_id=episode_id
                )
            except ImportError:
                pass
            results[episode_id] = True
    
    # 记录阶段完成统计
    success_count = sum(1 for v in results.values() if v)
    if HAS_LOGGER and logger:
        logger.info(
            "breadth_first.stage5.completed",
            f"阶段5完成：成功 {success_count}/{len(results)}",
            metadata={"success_count": success_count, "total_count": len(results)}
        )
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="广度优先生成：按阶段批量生成所有期数",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
阶段说明：
  阶段1：选歌+歌单+封面（所有期数，小文件）
  阶段2：YouTube资源（标题、描述、SRT，所有期数，小文件）
  阶段3：音频混音（所有期数，中等文件）
  阶段4：视频合成（所有期数，大文件）
  阶段5：检查并打包（集齐资料的期数）
        """
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新生成所有文件（即使已存在）"
    )
    
    parser.add_argument(
        "--skip-stage",
        nargs="+",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="跳过指定阶段（例如：--skip-stage 4 5 跳过视频生成和打包）"
    )
    
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="阶段间不暂停，自动继续（适合自动化运行）"
    )
    
    args = parser.parse_args()
    
    skip_stages = set(args.skip_stage) if args.skip_stage else set()
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在，请先创建排播表")
        sys.exit(1)
    
    # 获取pending期数
    episodes = get_pending_episodes(schedule)
    if not episodes:
        print("ℹ️  没有pending期数，所有期数已完成或已跳过")
        sys.exit(0)
    
    print(f"\n📋 发现 {len(episodes)} 个pending期数")
    for ep in episodes[:5]:  # 只显示前5个
        print(f"  - {ep.get('episode_id')}: {ep.get('title', '未命名')}")
    if len(episodes) > 5:
        print(f"  ... 还有 {len(episodes) - 5} 个期数")
    
    print("\n" + "=" * 70)
    print("🔄 广度优先生成模式")
    print("=" * 70)
    print("说明：按阶段批量处理，先完成所有期数的阶段1，再进入阶段2，以此类推")
    print("这样可以：")
    print("  - 快速看到所有期数的初步进展")
    print("  - 小文件先生成，大文件后生成（按体积排序）")
    print("  - 如果中途中断，已完成阶段的文件会保留")
    print("=" * 70)
    
    output_dir = REPO_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 执行各阶段（广度优先）
    all_results = {}
    
    if 1 not in skip_stages:
        results1 = stage1_generate_playlists(episodes, output_dir, args.force)
        all_results.update(results1)
        print("\n✅ 阶段1完成：所有期数的歌单和封面已生成")
        if not args.no_pause:
            input("\n按Enter继续下一阶段...")  # 暂停，让用户确认
    else:
        print("\n⏭️  跳过阶段1：生成歌单和封面")
    
    if 2 not in skip_stages:
        results2 = stage2_generate_youtube_assets(episodes, output_dir, args.force)
        all_results.update(results2)
        print("\n✅ 阶段2完成：所有期数的YouTube资源已生成")
        if not args.no_pause:
            input("\n按Enter继续下一阶段...")  # 暂停，让用户确认
    else:
        print("\n⏭️  跳过阶段2：生成YouTube资源")
    
    if 3 not in skip_stages:
        results3 = stage3_generate_audio(episodes, output_dir, args.force)
        all_results.update(results3)
        print("\n✅ 阶段3完成：所有期数的音频已生成")
        if not args.no_pause:
            input("\n按Enter继续下一阶段...")  # 暂停，让用户确认
    else:
        print("\n⏭️  跳过阶段3：生成音频混音")
    
    if 4 not in skip_stages:
        results4 = stage4_generate_videos(episodes, output_dir, args.force)
        all_results.update(results4)
        print("\n✅ 阶段4完成：所有期数的视频已生成")
        if not args.no_pause:
            input("\n按Enter继续下一阶段...")  # 暂停，让用户确认
    else:
        print("\n⏭️  跳过阶段4：生成视频")
    
    if 5 not in skip_stages:
        results5 = stage5_package_episodes(episodes, output_dir, schedule)
        all_results.update(results5)
        print("\n✅ 阶段5完成：所有集齐资料的期数已打包")
    else:
        print("\n⏭️  跳过阶段5：检查并打包")
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("📊 生成结果汇总")
    print("=" * 70)
    
    success_count = sum(1 for v in all_results.values() if v)
    total_count = len(all_results)
    
    print(f"成功: {success_count}/{total_count}")
    if success_count < total_count:
        print("\n失败的期数：")
        for ep_id, success in all_results.items():
            if not success:
                print(f"  - {ep_id}")
    
    print("=" * 70)


if __name__ == "__main__":
    main()

