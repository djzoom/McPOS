#!/usr/bin/env python3
# coding: utf-8
"""
分析排播表对歌库的使用情况

功能：
1. 统计每首歌曲的使用次数
2. 统计新歌/旧歌的使用情况
3. 分析重复使用模式
4. 生成使用情况报告
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from schedule_master import ScheduleMaster
    from create_mixtape import load_tracklist, Track
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


def analyze_schedule_usage():
    """分析排播表使用情况"""
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在")
        sys.exit(1)
    
    # 加载歌库
    tracklist_path = REPO_ROOT / "data" / "song_library.csv"
    if not tracklist_path.exists():
        print("❌ 歌库文件不存在")
        sys.exit(1)
    
    all_tracks = load_tracklist(tracklist_path)
    all_track_titles = {t.title for t in all_tracks}
    
    print("=" * 70)
    print("📊 排播表使用情况分析")
    print("=" * 70)
    print(f"\n歌库总曲目数: {len(all_tracks)} 首")
    print(f"排播表期数: {len(schedule.episodes)} 期")
    print(f"已生成标题和曲目的期数: {sum(1 for ep in schedule.episodes if ep.get('tracks_used'))} 期")
    
    # 统计每首歌曲的使用次数
    track_usage = Counter()
    episode_tracks = {}  # 每期使用的曲目
    starting_tracks_usage = Counter()  # 起始曲目使用次数
    
    for ep in schedule.episodes:
        tracks_used = ep.get("tracks_used", [])
        if tracks_used:
            episode_tracks[ep["episode_id"]] = set(tracks_used)
            for track in tracks_used:
                track_usage[track] += 1
            
            # 统计起始曲目
            starting_track = ep.get("starting_track")
            if starting_track:
                starting_tracks_usage[starting_track] += 1
    
    # 统计已使用的曲目
    used_tracks = set(track_usage.keys())
    unused_tracks = all_track_titles - used_tracks
    
    print(f"\n{'='*70}")
    print("📈 使用统计")
    print(f"{'='*70}")
    print(f"已使用曲目: {len(used_tracks)} 首 ({len(used_tracks)/len(all_tracks)*100:.1f}%)")
    print(f"未使用曲目: {len(unused_tracks)} 首 ({len(unused_tracks)/len(all_tracks)*100:.1f}%)")
    
    # 使用次数分布
    usage_counts = Counter(track_usage.values())
    print(f"\n使用次数分布:")
    for count in sorted(usage_counts.keys()):
        tracks_count = usage_counts[count]
        print(f"  使用{count}次: {tracks_count} 首")
    
    # 最常用的曲目（使用次数最多的）
    most_used = track_usage.most_common(20)
    print(f"\n{'='*70}")
    print("🎵 最常用曲目（Top 20）")
    print(f"{'='*70}")
    for i, (track, count) in enumerate(most_used, 1):
        print(f"{i:2d}. {track[:50]:<50} ({count}次)")
    
    # 从未使用的曲目（前20）
    if unused_tracks:
        unused_list = sorted(list(unused_tracks))[:20]
        print(f"\n{'='*70}")
        print("🚫 从未使用的曲目（前20）")
        print(f"{'='*70}")
        for i, track in enumerate(unused_list, 1):
            print(f"{i:2d}. {track[:60]}")
        if len(unused_tracks) > 20:
            print(f"\n... 还有 {len(unused_tracks) - 20} 首未显示")
    
    # 起始曲目唯一性分析
    print(f"\n{'='*70}")
    print("🎯 起始曲目分析")
    print(f"{'='*70}")
    unique_starting = len(starting_tracks_usage)
    total_episodes_with_starting = sum(1 for ep in schedule.episodes if ep.get('starting_track'))
    print(f"唯一起始曲目数: {unique_starting} 首")
    print(f"有起始曲目的期数: {total_episodes_with_starting} 期")
    
    if unique_starting < total_episodes_with_starting:
        print(f"⚠️  警告: 有重复的起始曲目！")
        duplicates = [(track, count) for track, count in starting_tracks_usage.items() if count > 1]
        if duplicates:
            print(f"\n重复的起始曲目:")
            for track, count in sorted(duplicates, key=lambda x: x[1], reverse=True):
                print(f"  - {track[:50]} ({count}次)")
    
    # 每期的曲目重叠分析
    print(f"\n{'='*70}")
    print("🔄 期数间曲目重叠分析")
    print(f"{'='*70}")
    
    overlap_stats = []
    for ep_id, tracks in episode_tracks.items():
        overlaps = []
        for other_id, other_tracks in episode_tracks.items():
            if ep_id != other_id:
                overlap_count = len(tracks & other_tracks)
                if overlap_count > 0:
                    overlaps.append((other_id, overlap_count))
        
        if overlaps:
            max_overlap = max(overlaps, key=lambda x: x[1])[1]
            total_overlap = sum(o[1] for o in overlaps)
            overlap_stats.append({
                'episode_id': ep_id,
                'max_overlap': max_overlap,
                'total_overlap': total_overlap,
                'overlap_count': len(overlaps)
            })
    
    if overlap_stats:
        overlap_stats.sort(key=lambda x: x['max_overlap'], reverse=True)
        print(f"期数间有曲目重叠: {len(overlap_stats)} 期")
        print(f"\n重叠最多的情况（前10）:")
        for i, stat in enumerate(overlap_stats[:10], 1):
            ep = schedule.get_episode(stat['episode_id'])
            print(f"{i:2d}. {stat['episode_id']} - 最多重叠: {stat['max_overlap']}首, "
                  f"总重叠: {stat['total_overlap']}首, 与{stat['overlap_count']}期重叠")
    else:
        print("✅ 所有期数的曲目都完全独立（无重叠）")
    
    # 每期的曲目数统计
    print(f"\n{'='*70}")
    print("📊 每期曲目数统计")
    print(f"{'='*70}")
    
    episode_sizes = [len(ep.get("tracks_used", [])) for ep in schedule.episodes if ep.get("tracks_used")]
    if episode_sizes:
        print(f"平均每期: {sum(episode_sizes)/len(episode_sizes):.1f} 首")
        print(f"最少: {min(episode_sizes)} 首")
        print(f"最多: {max(episode_sizes)} 首")
        
        size_dist = Counter(episode_sizes)
        print(f"\n分布:")
        for size in sorted(size_dist.keys()):
            count = size_dist[size]
            print(f"  {size}首: {count}期")
    
    # 新歌使用率（基于第一次使用）
    print(f"\n{'='*70}")
    print("🆕 新歌使用分析")
    print(f"{'='*70}")
    
    first_use = {}  # 每首歌第一次使用的期数
    for i, ep in enumerate(schedule.episodes, 1):
        tracks = ep.get("tracks_used", [])
        for track in tracks:
            if track not in first_use:
                first_use[track] = i
    
    new_tracks_by_episode = defaultdict(list)
    for track, episode_num in first_use.items():
        new_tracks_by_episode[episode_num].append(track)
    
    print(f"首次使用的曲目分布:")
    for ep_num in sorted(new_tracks_by_episode.keys()):
        tracks = new_tracks_by_episode[ep_num]
        ep = schedule.episodes[ep_num - 1]
        print(f"  第{ep_num}期 ({ep['episode_id']}): {len(tracks)} 首新歌")
    
    print(f"\n总计新歌: {len(first_use)} 首")
    print(f"重复使用的曲目: {len(used_tracks) - len(first_use)} 首")
    
    print(f"\n{'='*70}")
    print("✅ 分析完成")
    print(f"{'='*70}")


if __name__ == "__main__":
    analyze_schedule_usage()

