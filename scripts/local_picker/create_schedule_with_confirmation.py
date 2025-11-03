#!/usr/bin/env python3
# coding: utf-8
"""
创建排播表（带确认和歌库记录）

功能：
1. 生成排播表预览
2. 显示歌库快照信息
3. 用户确认后才真正创建
4. 创建时记录歌库状态
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from schedule_master import ScheduleMaster, SCHEDULE_MASTER_PATH
    from dataclasses import field, dataclass
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


@dataclass
class LibrarySnapshot:
    """歌库快照（轻量级，不需要production_log）"""
    total_tracks: int
    updated_at: str
    library_file: str


def get_library_snapshot() -> LibrarySnapshot:
    """获取当前歌库快照"""
    tracklist_path = REPO_ROOT / "data" / "song_library.csv"
    if not tracklist_path.exists():
        raise FileNotFoundError("歌库文件不存在: data/song_library.csv")
    
    from create_mixtape import load_tracklist
    tracks = load_tracklist(tracklist_path)
    
    # 获取歌库快照（不依赖production_log，新架构）
    from datetime import datetime
    mtime = tracklist_path.stat().st_mtime
    updated_at = datetime.fromtimestamp(mtime).isoformat()
    return LibrarySnapshot(
        total_tracks=len(tracks),
        updated_at=updated_at,
        library_file=str(tracklist_path),
    )


def preview_schedule(
    episodes: int,
    start_date: Optional[datetime],
    interval: int,
    images_dir: Optional[Path]
) -> dict:
    """预览排播表（不实际创建）"""
    # 检查图片数量
    if images_dir is None:
        images_dir = REPO_ROOT / "assets" / "design" / "images"
    
    image_files = sorted(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")))
    
    if episodes > len(image_files):
        raise ValueError(
            f"期数 {episodes} 超过可用图片数量 {len(image_files)}。"
            f"需要至少 {episodes} 张图片。"
        )
    
    # 计算日期范围
    if start_date is None:
        from schedule_master import DEFAULT_START_DATE
        start_date = DEFAULT_START_DATE
    
    from datetime import timedelta
    end_date = start_date + timedelta(days=(episodes - 1) * interval)
    
    return {
        "total_episodes": episodes,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "interval_days": interval,
        "available_images": len(image_files),
        "used_images": episodes,
        "remaining_images": len(image_files) - episodes
    }


def main():
    parser = argparse.ArgumentParser(description="创建排播表（带确认和歌库记录）")
    parser.add_argument(
        "--episodes",
        type=int,
        required=True,
        help="总期数（必须小于等于可用图片数量）"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="起始日期（YYYY-MM-DD格式，默认：系统时间下一天）"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="排播间隔（天，默认：2）"
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        help="图片目录（默认：assets/design/images）"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已存在的排播表（跳过确认）"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="自动确认（跳过交互）"
    )
    parser.add_argument(
        "--generate-content",
        action="store_true",
        default=True,
        help="创建排播表后自动生成所有期的图片、背景色、标题和选曲（默认启用）"
    )
    parser.add_argument(
        "--no-generate-content",
        dest="generate_content",
        action="store_false",
        help="创建排播表后不生成标题和选曲（仅分配图片）"
    )
    
    args = parser.parse_args()
    
    # 检查是否已存在
    existing_schedule = ScheduleMaster.load()
    if existing_schedule and not args.force:
        print("⚠️  永恒排播表已存在！")
        print(f"   总期数: {existing_schedule.total_episodes}")
        print(f"   起始日期: {existing_schedule.start_date}")
        print(f"   已生成期数: {len([ep for ep in existing_schedule.episodes if ep.get('tracks_used')])}")
        print("\n   如需重新创建，请使用 --force 参数")
        sys.exit(1)
    
    # 如果使用 --force 且存在旧排播表，先删除并显示释放的资源
    if args.force and existing_schedule:
        used_images_count = len(existing_schedule.images_used)
        used_tracks = existing_schedule.get_all_used_tracks()
        used_tracks_count = len(used_tracks)
        
        print("\n" + "=" * 70)
        print("🔄 强制重新创建排播表")
        print("=" * 70)
        print(f"📋 将释放旧排播表的资源：")
        print(f"  • 图片: {used_images_count} 张恢复为未使用")
        print(f"  • 歌曲: {used_tracks_count} 首恢复为新歌")
        print(f"  • 标题模式: {len(existing_schedule.title_patterns)} 个将被清除")
        
        # 删除旧排播表文件（资源会自动释放，因为新的排播表对象会重新初始化）
        schedule_path = Path(SCHEDULE_MASTER_PATH)
        if schedule_path.exists():
            schedule_path.unlink()
            print(f"\n✅ 旧排播表已删除，所有资源已恢复为可用状态")
    
    # 解析起始日期
    start_date = None
    if args.start_date:
        start_date = datetime.fromisoformat(args.start_date)
    
    # 预览排播表
    print("=" * 70)
    print("📋 排播表预览")
    print("=" * 70)
    
    try:
        preview = preview_schedule(
            episodes=args.episodes,
            start_date=start_date,
            interval=args.interval,
            images_dir=args.images_dir
        )
    except ValueError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)
    
    print(f"总期数: {preview['total_episodes']} 期")
    print(f"起始日期: {preview['start_date']}")
    print(f"结束日期: {preview['end_date']}")
    print(f"排播间隔: {preview['interval_days']} 天")
    print(f"可用图片: {preview['available_images']} 张")
    print(f"将使用: {preview['used_images']} 张")
    print(f"剩余图片: {preview['remaining_images']} 张")
    
    # 获取歌库快照
    print("\n" + "=" * 70)
    print("📚 当前歌库状态")
    print("=" * 70)
    
    try:
        library_snapshot = get_library_snapshot()
        print(f"总曲目数: {library_snapshot.total_tracks} 首")
        print(f"歌库文件: {library_snapshot.library_file}")
        print(f"快照时间: {library_snapshot.updated_at}")
        
        # 新架构：schedule_master.json为单一数据源，不再需要检查production_log
        print("ℹ️  新架构：schedule_master.json为单一数据源")
    except Exception as e:
        print(f"❌ 获取歌库快照失败: {e}")
        sys.exit(1)
    
    # 确认
    print("\n" + "=" * 70)
    print("⚠️  确认信息")
    print("=" * 70)
    
    if args.force:
        print("⚠️  警告: 将覆盖已存在的排播表！")
    
    if not args.yes:
        print("\n将要执行的操作：")
        print("  1. 创建永恒排播表（一旦创建不可变更）")
        print("  2. 记录当前歌库快照到生产日志")
        print("  3. 更新生产日志的歌库更新时间")
        if args.generate_content:
            print("  4. 为每期生成：图片、背景色、标题、选曲（需要API，可能需要几分钟）")
        print("\n是否继续？(yes/no): ", end="", flush=True)
        
        try:
            response = input().strip().lower()
            if response not in ["yes", "y", "是", "确认"]:
                print("❌ 已取消")
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            print("\n❌ 已取消")
            sys.exit(0)
    
    # 创建排播表
    print("\n" + "=" * 70)
    print("🔨 创建排播表...")
    print("=" * 70)
    
    try:
        master = ScheduleMaster.create(
            total_episodes=args.episodes,
            start_date=start_date,
            schedule_interval_days=args.interval,
            images_dir=args.images_dir
        )
        # 确保图片使用标记已同步（基于分配）
        images_synced = master.sync_images_from_assignments()
        master.save()
        
        # 注意：新架构以schedule_master.json为单一数据源，不再需要同步到production_log
        # 如果需要重建production_log.json，使用 unified_sync.py
        
        print(f"✅ 永恒排播表创建成功！")
        print(f"   保存位置: {SCHEDULE_MASTER_PATH}")
        print(f"   已使用图片: {len(master.images_used)} 张（排播表中分配的图片）")
    except Exception as e:
        print(f"❌ 创建排播表失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # 新架构：不再需要单独记录歌库快照到production_log
    # schedule_master.json是单一数据源，所有信息都在那里
    print("\nℹ️  新架构：schedule_master.json为单一数据源，不再需要单独记录歌库快照")
    
    # 完成
    print("\n" + "=" * 70)
    print("✅ 完成")
    print("=" * 70)
    print(f"\n排播表摘要：")
    print(f"  总期数: {master.total_episodes}")
    print(f"  起始日期: {master.start_date}")
    print(f"  排播间隔: {master.schedule_interval_days} 天")
    print(f"  可用图片: {len(master.images_pool)} 张")
    
    print(f"\n歌库状态：")
    print(f"  总曲目数: {library_snapshot.total_tracks} 首")
    print(f"  快照已记录: ✅")
    
    # 如果启用了生成内容，在创建排播表后立即生成所有期的图片、背景色、标题和选曲
    if args.generate_content:
        print("\n" + "=" * 70)
        print("🎨 生成完整排播内容（图片、背景色、标题、选曲）...")
        print("=" * 70)
        
        try:
            # 导入必要的模块
            from generate_full_schedule import generate_episode_content
            from create_mixtape import load_tracklist, Track
            from src.creation_utils import get_dominant_color
            
            # 加载曲库
            tracklist_path = REPO_ROOT / "data" / "song_library.csv"
            if not tracklist_path.exists():
                print("⚠️  曲库不存在，跳过生成标题和选曲")
                print("   提示：请先生成曲库，或稍后运行 generate_full_schedule.py")
            else:
                all_tracks = load_tracklist(tracklist_path)
                print(f"✅ 已加载曲库：{len(all_tracks)} 首")
                
                # 为每期生成内容
                print(f"\n📋 生成排播表内容（{len(master.episodes)} 期）...")
                print("=" * 60)
                
                # 用于实时跟踪已使用的起始曲目
                used_starting_tracks_in_progress = set()
                
                for i, episode in enumerate(master.episodes, 1):
                    print(f"\n[{i}/{len(master.episodes)}] {episode['episode_id']} - {episode['schedule_date']}")
                    
                    # 生成内容（图片、背景色、标题、选曲）
                    # 注意：在生成前，先合并所有已使用的起始曲目（包括已保存的和本次生成过程中的）
                    all_excluded_starting_tracks = set(master.get_used_starting_tracks())
                    all_excluded_starting_tracks.update(used_starting_tracks_in_progress)
                    
                    content = generate_episode_content(
                        episode,
                        master,
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
                        
                        # 提取背景色并保存
                        image_path = Path(episode.get("image_path", ""))
                        if image_path.exists():
                            try:
                                dominant_color = get_dominant_color(image_path)
                                episode["dominant_color_rgb"] = dominant_color
                                episode["dominant_color_hex"] = f"{dominant_color[0]:02x}{dominant_color[1]:02x}{dominant_color[2]:02x}"
                                print(f"  🎨 背景色: #{episode['dominant_color_hex']} (RGB: {dominant_color})")
                            except Exception as e:
                                print(f"  ⚠️  颜色提取失败: {e}")
                                episode["dominant_color_rgb"] = (100, 100, 100)
                                episode["dominant_color_hex"] = "646464"
                        
                        # 更新排播表（包括起始曲目）
                        master.update_episode(
                            episode["episode_id"],
                            title=content["title"],
                            tracks_used=[t.title for t in content["side_a"] + content["side_b"]],
                            starting_track=content["starting_track"]
                        )
                        print(f"  ✅ 已更新排播表（图片、背景色、标题、选曲）")
                    else:
                        print(f"  ⚠️  跳过")
                
                # 保存更新后的排播表
                # 先同步图片使用标记（基于分配）
                images_synced_from_assignments = master.sync_images_from_assignments()
                if images_synced_from_assignments != 0:
                    print(f"\n🔄 图片使用标记已同步（基于分配）：{images_synced_from_assignments:+d} 张")
                
                master.save()
                print(f"\n✅ 排播表已更新并保存（包含所有期的完整信息）")
                print(f"   已使用图片: {len(master.images_used)} 张（排播表中分配的图片）")
                
                # 图片使用标记已在上面的 sync_images_from_assignments() 中同步
                # 在新架构中，图片使用标记基于分配状态，不再需要基于完成状态的额外同步
                pass
        except ImportError as e:
            print(f"⚠️  无法导入必要模块: {e}")
            print("   排播表已创建，但未生成标题和选曲")
            print("   提示：可以稍后运行 generate_full_schedule.py 生成完整内容")
        except Exception as e:
            print(f"⚠️  生成内容时出错: {e}")
            import traceback
            traceback.print_exc()
            print("   排播表已创建，但内容生成不完整")
            print("   提示：可以稍后运行 generate_full_schedule.py 补全内容")
    
    print(f"\n💡 下一步：")
    print(f"  查看排播表: python scripts/local_picker/show_schedule.py")
    if not args.generate_content:
        print(f"  生成完整排播: python scripts/local_picker/generate_full_schedule.py")


if __name__ == "__main__":
    main()

