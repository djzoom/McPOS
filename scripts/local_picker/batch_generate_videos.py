#!/usr/bin/env python3
# coding: utf-8
"""
批量生成完整视频内容

功能：
- 支持生成 N 期完整内容（封面+歌单+混音+视频+YouTube资源）
- 基于排播日志系统，确保ID唯一性
- 串行生成，避免资源竞争
- 进度显示和错误处理
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 添加当前脚本目录到路径
script_dir = Path(__file__).parent
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(repo_root / "scripts" / "local_picker"))

try:
    from schedule_master import ScheduleMaster
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    print("[WARN] 无法导入 schedule_master，将使用 production_log（向后兼容）")

# 注意：production_log导入用于向后兼容（当排播表不可用时作为回退）
# 新架构优先使用schedule_master.json，production_log仅作为回退方案
from production_log import ProductionLog


def batch_generate_videos(n: int):
    """
    批量生成 N 期完整视频内容（基于排播表）
    
    Args:
        n: 生成期数
    """
    root_dir = Path(__file__).parent.parent.parent
    
    # 优先使用排播表
    episode_ids = []
    if SCHEDULE_AVAILABLE:
        schedule = ScheduleMaster.load()
        if schedule:
            # 获取前N个pending的期数
            pending_eps = [ep for ep in schedule.episodes if ep.get("status") == "pending"]
            episode_ids = [ep["episode_id"] for ep in pending_eps[:n]]
            
            print(f"=" * 60)
            print(f"批量生成：{n} 期完整内容（基于排播表）")
            print(f"总期数：{schedule.total_episodes}")
            print(f"Pending期数：{len(pending_eps)}")
            print(f"将生成：{len(episode_ids)} 期")
            if episode_ids:
                print(f"期数ID：{', '.join(episode_ids[:5])}{'...' if len(episode_ids) > 5 else ''}")
            print(f"=" * 60)
        else:
            print("⚠️  排播表不存在，使用production_log")
    
    # 回退到production_log（如果排播表不可用）
    if not episode_ids:
        production_log = ProductionLog.load()
        print(f"=" * 60)
        print(f"批量生成：{n} 期完整内容（基于生产日志）")
        print(f"起始排播日期：{production_log.start_date}")
        print(f"排播间隔：{production_log.schedule_interval_days} 天")
        print(f"=" * 60)
        # 这里episode_ids为空，将在循环中自动计算
    
    success_count = 0
    failed_count = 0
    failed_episodes = []
    
    for i in range(1, n + 1):
        print(f"\n{'='*60}")
        
        # 构建命令
        cmd = [
            sys.executable,
            str(root_dir / "scripts" / "local_picker" / "create_mixtape.py"),
            "--font_name", "Lora-Regular",
        ]
        
        # 如果使用排播表且有指定ID，直接使用
        if episode_ids and i <= len(episode_ids):
            episode_id = episode_ids[i - 1]
            ep = schedule.get_episode(episode_id)
            print(f"[{i}/{n}] 生成ID: {episode_id} ({ep.get('schedule_date', '未知日期')})")
            cmd.extend(["--episode-id", episode_id])
        else:
            print(f"[{i}/{n}] 开始生成第 {i} 期（自动计算ID）...")
        
        try:
            # 执行生成
            result = subprocess.run(
                cmd,
                cwd=root_dir,
                capture_output=False,  # 实时输出
                text=True,
            )
            
            if result.returncode == 0:
                success_count += 1
                episode_id = episode_ids[i - 1] if episode_ids and i <= len(episode_ids) else "自动"
                print(f"\n[{i}/{n}] ✅ 生成成功 (ID: {episode_id})")
            else:
                failed_count += 1
                episode_id = episode_ids[i - 1] if episode_ids and i <= len(episode_ids) else "未知"
                failed_episodes.append((i, episode_id))
                print(f"\n[{i}/{n}] ❌ 生成失败 (ID: {episode_id}, 返回码：{result.returncode})")
        
        except Exception as e:
            failed_count += 1
            episode_id = episode_ids[i - 1] if episode_ids and i <= len(episode_ids) else "异常"
            failed_episodes.append((i, episode_id))
            print(f"\n[{i}/{n}] ❌ 生成异常：{e}")
        
        # 短暂停顿，避免资源竞争
        if i < n:
            import time
            time.sleep(2)
    
    # 输出总结报告
    print(f"\n{'='*60}")
    print(f"批量生成完成")
    print(f"{'='*60}")
    print(f"成功：{success_count}/{n}")
    print(f"失败：{failed_count}/{n}")
    
    if failed_episodes:
        print(f"\n失败的期数：")
        for episode_num, episode_id in failed_episodes:
            print(f"  - 第 {episode_num} 期（ID: {episode_id}）")
    
    # 显示排播表或生产日志摘要
    if SCHEDULE_AVAILABLE and schedule:
        remaining, _ = schedule.check_remaining_images()
        completed = sum(1 for ep in schedule.episodes if ep.get("status") == "completed")
        pending = sum(1 for ep in schedule.episodes if ep.get("status") == "pending")
        print(f"\n排播表摘要：")
        print(f"  已完成：{completed}/{schedule.total_episodes} 期")
        print(f"  Pending：{pending} 期")
        print(f"  剩余图片：{remaining} 张")
    else:
        log = ProductionLog.load()
        print(f"\n生产日志摘要：")
        print(f"  已完成期数：{sum(1 for r in log.records if r.get('status') == 'completed')}")
        print(f"  待处理期数：{sum(1 for r in log.records if r.get('status') == 'pending')}")
        print(f"  最后歌库更新：{log.last_library_update or '未知'}")
    
    return success_count, failed_count


def main():
    parser = argparse.ArgumentParser(description="批量生成完整视频内容")
    parser.add_argument(
        "N",
        type=int,
        help="生成期数",
    )
    args = parser.parse_args()
    
    if args.N <= 0:
        print("错误：期数必须大于 0")
        sys.exit(1)
    
    batch_generate_videos(args.N)


if __name__ == "__main__":
    main()

