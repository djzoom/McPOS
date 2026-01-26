#!/usr/bin/env python3
# coding: utf-8
"""
检查episode素材完整性

用法:
    python3 scripts/check_episode_assets.py kat 2026 2
    python3 scripts/check_episode_assets.py kat kat_20260227
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List
import calendar

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcpos.models import EpisodeSpec, StageName
from mcpos.adapters.filesystem import build_asset_paths, detect_episode_state_from_filesystem
from mcpos.config import get_config


def check_episode_assets(channel_id: str, episode_id: str) -> Dict:
    """检查单期节目的素材完整性"""
    date = episode_id.split("_")[-1] if "_" in episode_id else episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=episode_id,
    )
    
    config = get_config()
    paths = build_asset_paths(spec, config)
    state = detect_episode_state_from_filesystem(spec, paths)
    
    # 检查各阶段文件
    assets = {
        "episode_id": episode_id,
        "date": date,
        "output_dir": str(paths.episode_output_dir),
        "output_dir_exists": paths.episode_output_dir.exists(),
        "stages": {},
    }
    
    # INIT 阶段
    assets["stages"]["INIT"] = {
        "playlist_csv": {
            "path": str(paths.playlist_csv),
            "exists": paths.playlist_csv.exists(),
            "size": paths.playlist_csv.stat().st_size if paths.playlist_csv.exists() else 0,
        },
        "recipe_json": {
            "path": str(paths.recipe_json),
            "exists": paths.recipe_json.exists(),
            "size": paths.recipe_json.stat().st_size if paths.recipe_json.exists() else 0,
        },
    }
    
    # TEXT_BASE 阶段
    assets["stages"]["TEXT_BASE"] = {
        "youtube_title_txt": {
            "path": str(paths.youtube_title_txt),
            "exists": paths.youtube_title_txt.exists(),
            "size": paths.youtube_title_txt.stat().st_size if paths.youtube_title_txt.exists() else 0,
        },
        "youtube_description_txt": {
            "path": str(paths.youtube_description_txt),
            "exists": paths.youtube_description_txt.exists(),
            "size": paths.youtube_description_txt.stat().st_size if paths.youtube_description_txt.exists() else 0,
        },
        "youtube_tags_txt": {
            "path": str(paths.youtube_tags_txt),
            "exists": paths.youtube_tags_txt.exists(),
            "size": paths.youtube_tags_txt.stat().st_size if paths.youtube_tags_txt.exists() else 0,
        },
    }
    
    # COVER 阶段
    assets["stages"]["COVER"] = {
        "cover_png": {
            "path": str(paths.cover_png),
            "exists": paths.cover_png.exists(),
            "size": paths.cover_png.stat().st_size if paths.cover_png.exists() else 0,
        },
    }
    
    # MIX 阶段
    assets["stages"]["MIX"] = {
        "final_mix_mp3": {
            "path": str(paths.final_mix_mp3),
            "exists": paths.final_mix_mp3.exists(),
            "size": paths.final_mix_mp3.stat().st_size if paths.final_mix_mp3.exists() else 0,
        },
        "timeline_csv": {
            "path": str(paths.timeline_csv),
            "exists": paths.timeline_csv.exists(),
            "size": paths.timeline_csv.stat().st_size if paths.timeline_csv.exists() else 0,
        },
    }
    
    # TEXT_SRT 阶段
    assets["stages"]["TEXT_SRT"] = {
        "youtube_srt": {
            "path": str(paths.youtube_srt),
            "exists": paths.youtube_srt.exists(),
            "size": paths.youtube_srt.stat().st_size if paths.youtube_srt.exists() else 0,
        },
    }
    
    # RENDER 阶段
    assets["stages"]["RENDER"] = {
        "youtube_mp4": {
            "path": str(paths.youtube_mp4),
            "exists": paths.youtube_mp4.exists(),
            "size": paths.youtube_mp4.stat().st_size if paths.youtube_mp4.exists() else 0,
        },
        "render_complete_flag": {
            "path": str(paths.render_complete_flag),
            "exists": paths.render_complete_flag.exists(),
            "size": paths.render_complete_flag.stat().st_size if paths.render_complete_flag.exists() else 0,
        },
    }
    
    # 添加状态信息
    assets["state"] = {
        "current_stage": state.current_stage.value if state.current_stage else None,
        "stage_completed": {k.value: v for k, v in state.stage_completed.items()},
        "is_core_complete": state.is_core_complete(),
        "error_message": state.error_message,
    }
    
    return assets


def print_episode_assets(assets: Dict):
    """打印单期节目的素材信息"""
    print(f"\n{'='*80}")
    print(f"📦 素材完整性检查: {assets['episode_id']}")
    print(f"{'='*80}")
    print(f"输出目录: {assets['output_dir']}")
    print(f"目录存在: {'✅' if assets['output_dir_exists'] else '❌'}")
    
    if not assets['output_dir_exists']:
        print(f"\n⚠️  输出目录不存在！")
        return
    
    # 检查各阶段
    stage_names = {
        "INIT": "初始化",
        "TEXT_BASE": "文本生成",
        "COVER": "封面生成",
        "MIX": "混音",
        "TEXT_SRT": "字幕生成",
        "RENDER": "渲染",
    }
    
    for stage_name, stage_display in stage_names.items():
        if stage_name not in assets["stages"]:
            continue
        
        print(f"\n📋 {stage_display} ({stage_name}):")
        stage_assets = assets["stages"][stage_name]
        
        all_exist = True
        for asset_name, asset_info in stage_assets.items():
            exists = asset_info["exists"]
            size = asset_info["size"]
            icon = "✅" if exists else "❌"
            size_str = f" ({size / 1024:.1f} KB)" if exists and size > 0 else ""
            print(f"   {icon} {asset_name}: {exists}{size_str}")
            if not exists:
                all_exist = False
        
        if not all_exist:
            print(f"   ⚠️  阶段不完整")
    
    # 显示状态
    print(f"\n📊 状态信息:")
    state = assets["state"]
    print(f"   当前阶段: {state['current_stage'] or '未开始'}")
    print(f"   核心完成: {'✅' if state['is_core_complete'] else '❌'}")
    if state['error_message']:
        print(f"   ⚠️  错误: {state['error_message']}")
    
    print(f"{'='*80}\n")


def check_month_episodes(channel_id: str, year: int, month: int):
    """检查整月的所有节目"""
    _, last_day = calendar.monthrange(year, month)
    
    dates = []
    for day in range(1, last_day + 1):
        date_str = f"{year:04d}{month:02d}{day:02d}"
        dates.append(date_str)
    
    print(f"\n{'='*80}")
    print(f"📦 批量素材完整性检查")
    print(f"{'='*80}")
    print(f"   频道: {channel_id}")
    print(f"   月份: {year}年{month}月")
    print(f"   总期数: {len(dates)}")
    print(f"{'='*80}\n")
    
    results = []
    issues = []
    
    for date in dates:
        episode_id = f"{channel_id}_{date}"
        assets = check_episode_assets(channel_id, episode_id)
        results.append(assets)
        
        # 检查是否有问题
        if not assets["output_dir_exists"]:
            issues.append({
                "episode_id": episode_id,
                "issue": "输出目录不存在",
                "severity": "critical",
            })
        else:
            # 检查各阶段完整性
            for stage_name, stage_assets in assets["stages"].items():
                for asset_name, asset_info in stage_assets.items():
                    if not asset_info["exists"]:
                        # 检查是否应该是必需的
                        if stage_name in ["INIT", "COVER", "MIX", "RENDER"]:
                            # 这些阶段的核心文件是必需的
                            if asset_name in ["playlist_csv", "recipe_json", "cover_png", 
                                            "final_mix_mp3", "youtube_mp4", "render_complete_flag"]:
                                issues.append({
                                    "episode_id": episode_id,
                                    "issue": f"{stage_name}阶段缺少{asset_name}",
                                    "severity": "high",
                                })
    
    # 打印汇总
    print(f"\n{'='*80}")
    print(f"📊 汇总信息")
    print(f"{'='*80}")
    
    complete_count = sum(1 for r in results if r["state"]["is_core_complete"])
    in_progress_count = sum(1 for r in results 
                           if any(r["state"]["stage_completed"].values()) 
                           and not r["state"]["is_core_complete"])
    not_started_count = sum(1 for r in results 
                          if not any(r["state"]["stage_completed"].values()))
    
    print(f"   ✅ 已完成: {complete_count}/{len(results)}")
    print(f"   🔄 制作中: {in_progress_count}")
    print(f"   ⚪ 未开始: {not_started_count}")
    
    if issues:
        print(f"\n   ⚠️  发现问题: {len(issues)}个")
        print(f"\n详细问题列表:")
        for issue in issues:
            severity_icon = "🔴" if issue["severity"] == "critical" else "🟡"
            print(f"   {severity_icon} {issue['episode_id']}: {issue['issue']}")
    else:
        print(f"\n   ✅ 未发现问题")
    
    print(f"{'='*80}\n")
    
    # 打印有问题的节目详情
    if issues:
        print(f"\n{'='*80}")
        print(f"📋 问题节目详情")
        print(f"{'='*80}\n")
        
        problem_episodes = {issue["episode_id"] for issue in issues}
        for episode_id in sorted(problem_episodes):
            assets = next(r for r in results if r["episode_id"] == episode_id)
            print_episode_assets(assets)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="检查episode素材完整性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检查单期节目
  python3 scripts/check_episode_assets.py kat kat_20260227
  
  # 检查整月节目
  python3 scripts/check_episode_assets.py kat 2026 2
        """
    )
    parser.add_argument("channel_id", help="频道ID，如 kat")
    parser.add_argument("episode_or_year", help="节目ID（如 kat_20260227）或年份（如 2026）")
    parser.add_argument("month", nargs="?", type=int, help="月份（如果第一个参数是年份）")
    
    args = parser.parse_args()
    
    # 判断是单期还是整月
    if args.month is not None:
        # 整月检查
        year = int(args.episode_or_year)
        check_month_episodes(args.channel_id, year, args.month)
    else:
        # 单期检查
        episode_id = args.episode_or_year
        assets = check_episode_assets(args.channel_id, episode_id)
        print_episode_assets(assets)


if __name__ == "__main__":
    main()
