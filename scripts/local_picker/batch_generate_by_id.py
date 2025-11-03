#!/usr/bin/env python3
# coding: utf-8
"""
按ID批量生成视频

用法：
    python scripts/local_picker/batch_generate_by_id.py 20251101 20251103 20251105
    python scripts/local_picker/batch_generate_by_id.py --pending 10  # 生成前10个pending的
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from schedule_master import ScheduleMaster
except ImportError:
    print("❌ 无法导入 schedule_master")
    sys.exit(1)


def generate_by_id(episode_id: str):
    """生成指定ID的视频"""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
        "--font_name", "Lora-Regular",
        "--episode-id", episode_id,
    ]
    
    print(f"\n{'='*60}")
    print(f"生成ID: {episode_id}")
    print(f"{'='*60}")
    
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
    )
    
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="按ID批量生成视频")
    parser.add_argument(
        "ids",
        nargs="*",
        help="要生成的ID列表（例如：20251101 20251103）"
    )
    parser.add_argument(
        "--pending",
        type=int,
        help="生成前N个pending状态的期数"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="生成所有pending状态的期数（自动获取数量）"
    )
    args = parser.parse_args()
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 未找到排播表！请先创建：")
        print("   python scripts/local_picker/create_schedule_master.py --episodes 100")
        sys.exit(1)
    
    episode_ids = []
    
    if args.all:
        # 生成所有pending的期数（排除可能正在处理的期数）
        pending_eps = [ep for ep in schedule.episodes if ep.get("status") in ["pending", "待制作"]]
        
        # 检查哪些期数可能正在处理（已有部分文件但未完成）
        def is_likely_in_progress(ep_id: str) -> bool:
            """检查期数是否可能正在处理中"""
            ep = schedule.get_episode(ep_id)
            if not ep:
                return False
            
            from pathlib import Path
            from utils import get_final_output_dir
            from datetime import datetime
            
            output_dir = Path(__file__).parent.parent.parent / "output"
            
            # 检查output根目录和最终文件夹
            def check_file_in_location(base_dir: Path, filename: str) -> bool:
                return (base_dir / filename).exists()
            
            # 获取最终文件夹路径
            final_dir = None
            try:
                schedule_date_str = ep.get("schedule_date")
                title = ep.get("title", "")
                if schedule_date_str and title:
                    schedule_date = datetime.fromisoformat(schedule_date_str)
                    final_dir = get_final_output_dir(schedule_date, title)
            except:
                pass
            
            # 检查封面和歌单（在output根目录或最终文件夹）
            has_cover = (check_file_in_location(output_dir, f"{ep_id}_cover.png") or
                        (final_dir and check_file_in_location(final_dir, f"{ep_id}_cover.png")))
            has_playlist = (check_file_in_location(output_dir, f"{ep_id}_playlist.csv") or
                           (final_dir and check_file_in_location(final_dir, f"{ep_id}_playlist.csv")))
            
            # 检查视频（在output根目录或最终文件夹）
            has_video = (check_file_in_location(output_dir, f"{ep_id}_youtube.mp4") or
                        (final_dir and check_file_in_location(final_dir, f"{ep_id}_youtube.mp4")))
            
            # 如果有封面/歌单但没有视频，可能正在处理
            return (has_cover or has_playlist) and not has_video
        
        # 分离正在处理、已完成和未开始的期数
        in_progress = []
        completed = []
        not_started = []
        
        for ep in pending_eps:
            ep_id = ep["episode_id"]
            
            # 先检查是否已完成（有视频）
            from pathlib import Path
            from utils import get_final_output_dir
            from datetime import datetime
            output_dir = Path(__file__).parent.parent.parent / "output"
            
            ep_record = schedule.get_episode(ep_id)
            final_dir = None
            has_video = False
            if ep_record:
                try:
                    schedule_date_str = ep_record.get("schedule_date")
                    title = ep_record.get("title", "")
                    if schedule_date_str and title:
                        schedule_date = datetime.fromisoformat(schedule_date_str)
                        final_dir = get_final_output_dir(schedule_date, title)
                        has_video = ((output_dir / f"{ep_id}_youtube.mp4").exists() or
                                   (final_dir / f"{ep_id}_youtube.mp4").exists())
                except:
                    pass
            
            if has_video:
                completed.append(ep_id)
            elif is_likely_in_progress(ep_id):
                in_progress.append(ep_id)
            else:
                not_started.append(ep_id)
        
        episode_ids = not_started
        
        if completed:
            print(f"✅ 检测到 {len(completed)} 个期数已完成（有视频），将跳过：")
            for ep_id in completed:
                ep = schedule.get_episode(ep_id)
                if ep:
                    print(f"   {ep_id} - {ep.get('schedule_date', '未知日期')} - {ep.get('title', '无标题')}")
            print()
        
        if in_progress:
            print(f"⚠️  检测到 {len(in_progress)} 个期数可能正在处理中，将跳过：")
            for ep_id in in_progress:
                ep = schedule.get_episode(ep_id)
                if ep:
                    print(f"   {ep_id} - {ep.get('schedule_date', '未知日期')} - {ep.get('title', '无标题')}")
            print()
        
        print(f"📋 将生成 {len(episode_ids)} 个未开始的pending期数：")
        for ep_id in episode_ids:
            ep = schedule.get_episode(ep_id)
            if ep:
                print(f"   {ep_id} - {ep.get('schedule_date', '未知日期')} - {ep.get('title', '无标题')}")
    elif args.pending:
        # 生成前N个pending的（排除可能正在处理的）
        pending_eps = [ep for ep in schedule.episodes if ep.get("status") in ["pending", "待制作"]]
        
        # 检查正在处理的期数
        def is_likely_in_progress(ep_id: str) -> bool:
            from pathlib import Path
            from utils import get_final_output_dir
            from datetime import datetime
            
            output_dir = Path(__file__).parent.parent.parent / "output"
            ep = schedule.get_episode(ep_id)
            if not ep:
                return False
            
            # 检查最终文件夹
            final_dir = None
            try:
                schedule_date_str = ep.get("schedule_date")
                title = ep.get("title", "")
                if schedule_date_str and title:
                    schedule_date = datetime.fromisoformat(schedule_date_str)
                    final_dir = get_final_output_dir(schedule_date, title)
            except:
                pass
            
            def check_file(path: Path) -> bool:
                return path.exists()
            
            has_cover = (check_file(output_dir / f"{ep_id}_cover.png") or
                        (final_dir and check_file(final_dir / f"{ep_id}_cover.png")))
            has_video = (check_file(output_dir / f"{ep_id}_youtube.mp4") or
                        (final_dir and check_file(final_dir / f"{ep_id}_youtube.mp4")))
            
            return has_cover and not has_video
        
        # 排除正在处理的期数
        available_eps = [ep for ep in pending_eps if not is_likely_in_progress(ep["episode_id"])]
        
        if len(available_eps) < args.pending:
            print(f"⚠️  警告：只有 {len(available_eps)} 个可用的pending期数（已排除可能正在处理的），少于请求的 {args.pending} 个")
        episode_ids = [ep["episode_id"] for ep in available_eps[:args.pending]]
        print(f"📋 将生成前 {len(episode_ids)} 个pending期数：")
        for ep_id in episode_ids:
            ep = schedule.get_episode(ep_id)
            if ep:
                print(f"   {ep_id} - {ep.get('schedule_date', '未知日期')} - {ep.get('title', '无标题')}")
    elif args.ids:
        # 使用指定的ID列表
        episode_ids = args.ids
    else:
        parser.print_help()
        sys.exit(1)
    
    if not episode_ids:
        print("❌ 没有要生成的期数")
        sys.exit(1)
    
    # 生成
    success = 0
    failed = []
    
    for i, ep_id in enumerate(episode_ids, 1):
        print(f"\n[{i}/{len(episode_ids)}]")
        if generate_by_id(ep_id):
            success += 1
            print(f"✅ {ep_id} 生成成功")
        else:
            failed.append(ep_id)
            print(f"❌ {ep_id} 生成失败")
    
    # 总结
    print(f"\n{'='*60}")
    print(f"完成：成功 {success}/{len(episode_ids)}")
    if failed:
        print(f"失败：{', '.join(failed)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

