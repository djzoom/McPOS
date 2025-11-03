#!/usr/bin/env python3
# coding: utf-8
"""
生成完整排播表（包含标题和曲目）

功能：
1. 加载排播表
2. 为每期生成标题和选曲（不生成完整视频）
3. 更新排播表，记录标题和曲目
4. 导出为可读的格式（CSV、Markdown）

用法：
    python scripts/local_picker/generate_full_schedule.py
    python scripts/local_picker/generate_full_schedule.py --format markdown
    python scripts/local_picker/generate_full_schedule.py --output schedule_2025_11.md
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster
    from create_mixtape import Track, select_tracks, load_tracklist
    from src.creation_utils import get_dominant_color
# generate_poetic_title removed: no longer using local fallback
    SCHEDULE_AVAILABLE = True
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    SCHEDULE_AVAILABLE = False
    sys.exit(1)


def generate_episode_content(
    episode: Dict, 
    schedule: ScheduleMaster, 
    all_tracks: List[Track],
    additional_excluded_starting_tracks: Optional[Set[str]] = None
) -> Dict:
    """
    为一期生成标题和曲目（不生成完整视频）
    
    Args:
        episode: 期数信息
        schedule: 排播表对象
        all_tracks: 所有曲目列表
        additional_excluded_starting_tracks: 额外的排除起始曲目集合（用于实时跟踪）
    
    Returns:
        包含title, side_a, side_b等信息的字典
    """
    # 获取图片路径
    image_path = Path(episode.get("image_path", ""))
    if not image_path.exists():
        print(f"⚠️  警告：图片不存在 {image_path}，跳过 {episode['episode_id']}")
        return None
    
    # 提取颜色
    try:
        dominant_color = get_dominant_color(image_path)
    except Exception as e:
        print(f"⚠️  颜色提取失败 {episode['episode_id']}: {e}")
        dominant_color = (100, 100, 100)  # 默认颜色
    
    # 获取排除列表
    excluded_tracks = schedule.get_recent_tracks(episode["episode_id"], window=5)
    excluded_starting_tracks = schedule.get_used_starting_tracks()
    # 合并额外的排除列表（实时跟踪）
    if additional_excluded_starting_tracks:
        excluded_starting_tracks = excluded_starting_tracks.union(additional_excluded_starting_tracks)
    all_used_tracks = schedule.get_all_used_tracks()
    
    # 选曲（A/B面）
    seed = hash(episode["episode_id"]) % 1000000  # 基于ID的固定种子
    side_a, side_b = select_tracks(
        all_tracks,
        seed=seed,
        excluded_tracks=excluded_tracks,
        excluded_starting_tracks=excluded_starting_tracks,
        all_used_tracks=all_used_tracks,
        new_track_ratio=0.7
    )
    
    # 生成标题
    playlist_keywords = []
    for track in side_a[:5] + side_b[:5]:  # 取前5首作为关键词
        playlist_keywords.append(track.title.lower())
    
    # 尝试API生成，失败则用本地
    title = None
    title_pattern = None
    is_unique = True  # 初始化为True，表示假设是唯一的
    
    # 必须使用API，无fallback
    from api_config import require_api_key
    openai_key = require_api_key()  # 强制要求，不允许交互式输入
    
    # require_api_key已经强制要求，如果无API会直接sys.exit(1)，这里不会执行到
    
    try:
        from create_mixtape import _try_api_title
        from api_config import get_api_base_url, get_api_model, get_api_config
        
        config = get_api_config()
        provider = config.get_provider()
        base_url = config.get_base_url(provider)
        model = config.get_model(provider)
        
        # 重试生成标题，直到得到有效的（最多7个词，完整表达）
        max_title_attempts = 5
        api_title = None
        for attempt in range(max_title_attempts):
            api_title = _try_api_title(
                image_filename=str(image_path.name),
                dominant_rgb=dominant_color,
                playlist_keywords=playlist_keywords,
                seed=seed + attempt * 1000,  # 每次重试改变seed
                api_key=openai_key,
                base_url=base_url,
                model=model,
                provider=provider,
            )
            if api_title:
                # 验证标题长度（最多7个词）
                words = api_title.split()
                if len(words) <= 7:
                    title = api_title
                    break
                else:
                    print(f"  ⚠️  标题超过7个词（{len(words)}词），重试... (尝试 {attempt+1}/{max_title_attempts})")
                    api_title = None
            else:
                print(f"  ⚠️  API返回空标题，重试... (尝试 {attempt+1}/{max_title_attempts})")
        
        # 检查是否成功生成标题
        if not title:
            raise RuntimeError(f"API生成标题失败（已重试{max_title_attempts}次），无法生成有效的标题（最多7个词）")
        
        # 检查去重（首次生成后立即检查）
        is_unique, title_pattern = schedule.check_title_pattern(title)
        if is_unique:
            print(f"  ✅ API标题生成成功: {title}")
        else:
            print(f"  ⚠️  API标题模式重复: {title_pattern}，将在去重逻辑中处理")
    except SystemExit:
        # 重新抛出SystemExit（来自require_api_key）
        raise
    except Exception as e:
        print(f"  ❌ API标题生成失败: {e}")
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"标题生成失败，无法继续: {e}")
    
    # 标题去重检查（如果标题模式重复，重新生成，最多再试2次）
    if not is_unique:
        print(f"  ⚠️  标题模式重复 ({title_pattern})，重新生成...")
        for retry in range(2):  # 再试2次
            seed += 1000
            if openai_key:
                try:
                    from create_mixtape import _try_api_title
                    from api_config import get_api_base_url, get_api_model, get_api_config
                    
                    config = get_api_config()
                    provider = config.get_provider()
                    base_url = config.get_base_url(provider)
                    model = config.get_model(provider)
                    
                    api_title = _try_api_title(
                        image_filename=str(image_path.name),
                        dominant_rgb=dominant_color,
                        playlist_keywords=playlist_keywords,
                        seed=seed + retry * 1000,
                        api_key=openai_key,
                        base_url=base_url,
                        model=model,
                        provider=provider,
                    )
                    if api_title:
                        # 验证标题长度（最多7个词）
                        words = api_title.split()
                        if len(words) <= 7:
                            is_unique, new_pattern = schedule.check_title_pattern(api_title)
                            if is_unique:
                                title = api_title
                                title_pattern = new_pattern
                                print(f"  ✅ 重新生成成功（API）: {title}")
                                break
                        else:
                            print(f"  ⚠️  重新生成的标题超过7个词（{len(words)}词），继续重试...")
                    else:
                        print(f"  ⚠️  API返回空标题，继续重试... (重试 {retry+1}/2)")
                except Exception as e:
                    if retry == 0:
                        print(f"  ⚠️  API重试失败: {e}")
                    # 继续重试，不立即失败
        
        # 检查重试后是否成功生成唯一标题
        if not title or not is_unique:
            # 如果最终还是没有唯一标题，添加当前pattern并继续（避免阻塞）
            if title_pattern:
                schedule.add_title_pattern(title_pattern)
                print(f"  ⚠️  无法生成唯一标题，已添加模式 {title_pattern} 到已使用列表")
            if not title:
                raise RuntimeError(f"API重试失败，无法生成标题（已重试2次）")
    
    return {
        "episode_id": episode["episode_id"],
        "episode_number": episode["episode_number"],
        "schedule_date": episode["schedule_date"],
        "title": title,
        "title_pattern": title_pattern,
        "side_a": side_a,
        "side_b": side_b,
        "starting_track": side_a[0].title if side_a else None,
        "image_path": str(image_path)
    }


def export_to_markdown(episodes: List[Dict], output_path: Path):
    """导出为Markdown格式"""
    with output_path.open("w", encoding="utf-8") as f:
        f.write("# KAT Records 排播表\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        for ep in episodes:
            f.write(f"## 第 {ep['episode_number']} 期 - {ep['schedule_date']}\n\n")
            f.write(f"**ID**: `{ep['episode_id']}`  \n")
            f.write(f"**标题**: {ep['title']}  \n")
            f.write(f"**起始曲目**: {ep['starting_track']}  \n\n")
            
            # Side A
            f.write("### Side A\n\n")
            for i, track in enumerate(ep['side_a'], 1):
                f.write(f"{i:2d}. {track.title} ({track.duration_str})\n")
            
            total_a = sum(t.duration_sec for t in ep['side_a'])
            f.write(f"\n**时长**: {int(total_a//60)}:{int(total_a%60):02d} ({len(ep['side_a'])}首)\n\n")
            
            # Side B
            f.write("### Side B\n\n")
            for i, track in enumerate(ep['side_b'], 1):
                f.write(f"{i:2d}. {track.title} ({track.duration_str})\n")
            
            total_b = sum(t.duration_sec for t in ep['side_b'])
            f.write(f"\n**时长**: {int(total_b//60)}:{int(total_b%60):02d} ({len(ep['side_b'])}首)\n\n")
            
            f.write("---\n\n")
        
        # 统计
        total_episodes = len(episodes)
        total_tracks = sum(len(ep['side_a']) + len(ep['side_b']) for ep in episodes)
        f.write(f"## 统计\n\n")
        f.write(f"- **总期数**: {total_episodes}\n")
        f.write(f"- **总曲目数**: {total_tracks}\n")
        f.write(f"- **平均每期**: {total_tracks/total_episodes:.1f}首\n")


def export_to_csv(episodes: List[Dict], output_path: Path):
    """导出为CSV格式"""
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "期数", "ID", "日期", "标题", 
            "A面曲数", "A面时长", "B面曲数", "B面时长", 
            "起始曲目", "A面曲目列表", "B面曲目列表"
        ])
        
        for ep in episodes:
            side_a_tracks = " | ".join([f"{i}.{t.title}" for i, t in enumerate(ep['side_a'], 1)])
            side_b_tracks = " | ".join([f"{i}.{t.title}" for i, t in enumerate(ep['side_b'], 1)])
            
            total_a = sum(t.duration_sec for t in ep['side_a'])
            total_b = sum(t.duration_sec for t in ep['side_b'])
            
            writer.writerow([
                ep['episode_number'],
                ep['episode_id'],
                ep['schedule_date'],
                ep['title'],
                len(ep['side_a']),
                f"{int(total_a//60)}:{int(total_a%60):02d}",
                len(ep['side_b']),
                f"{int(total_b//60)}:{int(total_b%60):02d}",
                ep['starting_track'],
                side_a_tracks,
                side_b_tracks
            ])


def main():
    parser = argparse.ArgumentParser(description="生成完整排播表（包含标题和曲目）")
    parser.add_argument(
        "--format",
        choices=["markdown", "csv", "both"],
        default="markdown",
        help="输出格式（默认：markdown）"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="输出文件路径（默认：schedule_YYYY_MM.md）"
    )
    parser.add_argument(
        "--update-schedule",
        action="store_true",
        help="更新排播表，记录标题和曲目（否则只生成预览）"
    )
    
    args = parser.parse_args()
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在！请先创建：")
        print("   python scripts/local_picker/create_schedule_master.py --episodes 15")
        sys.exit(1)
    
    # 加载曲库
    tracklist_path = REPO_ROOT / "data" / "song_library.csv"
    if not tracklist_path.exists():
        print("❌ 曲库不存在！请先生成：")
        print("   python scripts/local_picker/generate_song_library.py")
        sys.exit(1)
    
    all_tracks = load_tracklist(tracklist_path)
    print(f"✅ 已加载曲库：{len(all_tracks)} 首")
    
    # 生成每期的内容
    print(f"\n📋 生成排播表内容（{len(schedule.episodes)} 期）...")
    print("=" * 60)
    
    episodes_content = []
    # 用于实时跟踪已使用的起始曲目（在生成过程中更新）
    used_starting_tracks_in_progress = set()
    
    for i, episode in enumerate(schedule.episodes, 1):
        print(f"\n[{i}/{len(schedule.episodes)}] {episode['episode_id']} - {episode['schedule_date']}")
        
        # 在生成前，先合并所有已使用的起始曲目（包括已保存的和本次生成过程中的）
        all_excluded_starting_tracks = set(schedule.get_used_starting_tracks())
        all_excluded_starting_tracks.update(used_starting_tracks_in_progress)
        
        # 直接传递合并后的排除列表
        content = generate_episode_content(
            episode, 
            schedule, 
            all_tracks,
            additional_excluded_starting_tracks=all_excluded_starting_tracks
        )
        
        if content:
            # 确保 starting_track 正确设置（从 side_a[0] 获取，而不是从返回值）
            # 因为 generate_episode_content 可能返回错误的值
            actual_starting_track = None
            if content.get("side_a") and len(content["side_a"]) > 0:
                actual_starting_track = content["side_a"][0].title
                content["starting_track"] = actual_starting_track
            elif content.get("starting_track"):
                actual_starting_track = content["starting_track"]
            
            # 立即将本次生成的起始曲目添加到进行中的列表（在更新排播表之前）
            if actual_starting_track:
                used_starting_tracks_in_progress.add(actual_starting_track)
                print(f"  📝 起始曲目已记录: {actual_starting_track} (已排除: {len(all_excluded_starting_tracks)} 首)")
            else:
                print(f"  ⚠️  警告：无法获取起始曲目")
            
            episodes_content.append(content)
            
            # 更新排播表（如果指定）
            if args.update_schedule:
                schedule.update_episode(
                    episode["episode_id"],
                    title=content["title"],
                    tracks_used=[t.title for t in content["side_a"] + content["side_b"]],
                    starting_track=content["starting_track"]
                )
                print(f"  ✅ 已更新排播表")
        else:
            print(f"  ⚠️  跳过")
    
    # 保存排播表（如果更新了）
    if args.update_schedule:
        schedule.save()
        print(f"\n✅ 排播表已更新并保存")
    
    # 导出
    if not args.output:
        first_date = datetime.strptime(episodes_content[0]["schedule_date"], "%Y-%m-%d")
        args.output = REPO_ROOT / "output" / f"schedule_{first_date.strftime('%Y_%m')}.md"
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    if args.format in ["markdown", "both"]:
        export_to_markdown(episodes_content, args.output)
        print(f"\n✅ Markdown已导出: {args.output}")
    
    if args.format in ["csv", "both"]:
        csv_path = args.output.with_suffix(".csv")
        export_to_csv(episodes_content, csv_path)
        print(f"✅ CSV已导出: {csv_path}")
    
    # 显示预览
    print(f"\n{'='*60}")
    print("📋 排播表预览（前3期）")
    print("=" * 60)
    for ep in episodes_content[:3]:
        print(f"\n第 {ep['episode_number']} 期 - {ep['schedule_date']}")
        print(f"  标题: {ep['title']}")
        print(f"  Side A: {len(ep['side_a'])}首")
        print(f"  Side B: {len(ep['side_b'])}首")
        print(f"  起始: {ep['starting_track']}")
    
    print(f"\n✅ 完成！共生成 {len(episodes_content)} 期")


if __name__ == "__main__":
    main()

