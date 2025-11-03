#!/usr/bin/env python3
# coding: utf-8
"""
期数恢复工具

功能：
1. 检测失败的期数（status=error或缺少输出文件）
2. 重置状态为pending
3. 记录恢复操作到日志
4. 可选：自动重新触发生成流程

用法：
    python scripts/local_picker/recover_episode.py --episode-id 20251102
    python scripts/local_picker/recover_episode.py --episode-id 20251102 --rerun
    python scripts/local_picker/recover_episode.py --all  # 恢复所有失败的期数
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    from schedule_master import ScheduleMaster
    from core.state_manager import get_state_manager, STATUS_PENDING, STATUS_ERROR
    from core.logger import get_logger
    STATE_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  警告：无法导入新模块，使用旧方式: {e}")
    STATE_MANAGER_AVAILABLE = False


class EpisodeRecoverer:
    """期数恢复器"""
    
    def __init__(self):
        self.schedule = ScheduleMaster.load()
        if not self.schedule:
            raise ValueError("排播表不存在")
        
        if STATE_MANAGER_AVAILABLE:
            self.state_manager = get_state_manager()
            self.logger = get_logger()
        else:
            self.state_manager = None
            self.logger = None
    
    def find_failed_episodes(self) -> List[str]:
        """
        查找所有失败的期数
        
        Returns:
            失败期数的ID列表
        """
        failed = []
        
        for ep in self.schedule.episodes:
            ep_id = ep.get("episode_id")
            status = ep.get("status", "")
            
            if status == STATUS_ERROR:
                failed.append(ep_id)
            elif status != "completed" and status != "pending":
                # 检查是否有输出文件（如果没有，可能卡在中间状态）
                if not self._has_output_files(ep_id):
                    failed.append(ep_id)
        
        return failed
    
    def _has_output_files(self, episode_id: str) -> bool:
        """检查期数是否有输出文件"""
        output_dir = REPO_ROOT / "output"
        
        # 检查output根目录
        patterns = [
            f"{episode_id}_cover.png",
            f"{episode_id}_playlist.csv",
            f"{episode_id}_full_mix.mp3",
            f"{episode_id}_playlist_full_mix.mp3",
        ]
        
        for pattern in patterns:
            if (output_dir / pattern).exists():
                return True
        
        # 检查期数文件夹
        for folder in output_dir.iterdir():
            if folder.is_dir() and episode_id in folder.name:
                for pattern in patterns:
                    if (folder / pattern).exists():
                        return True
        
        return False
    
    def recover_episode(self, episode_id: str, rerun: bool = False) -> bool:
        """
        恢复单个期数
        
        Args:
            episode_id: 期数ID
            rerun: 是否自动重新运行生成
        
        Returns:
            是否成功恢复
        """
        ep = self.schedule.get_episode(episode_id)
        if not ep:
            print(f"❌ 期数不存在: {episode_id}")
            return False
        
        old_status = ep.get("status", "")
        
        # 恢复状态
        if STATE_MANAGER_AVAILABLE and self.state_manager:
            success = self.state_manager.rollback_status(episode_id, target_status=STATUS_PENDING)
            
            if self.logger:
                self.logger.info(
                    event_name="episode.recovered",
                    message=f"期数 {episode_id} 已恢复：{old_status} → pending",
                    episode_id=episode_id,
                    metadata={"old_status": old_status, "rerun": rerun}
                )
        else:
            # 旧方式
            self.schedule.update_episode(episode_id, status="pending")
            self.schedule.save()
            success = True
            print(f"✅ 期数 {episode_id} 状态已重置为 pending（旧方式）")
        
        if not success:
            print(f"❌ 恢复期数 {episode_id} 失败")
            return False
        
        print(f"✅ 期数 {episode_id} 已恢复（状态: {old_status} → pending）")
        
        # 自动重新运行
        if rerun:
            print(f"\n🔄 自动重新运行生成流程...")
            return self._rerun_generation(episode_id)
        
        return True
    
    def _rerun_generation(self, episode_id: str) -> bool:
        """重新运行生成流程"""
        script_path = REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"
        
        if not script_path.exists():
            print(f"❌ 未找到生成脚本: {script_path}")
            return False
        
        try:
            cmd = [
                sys.executable,
                str(script_path),
                "--episode-id", episode_id
            ]
            
            print(f"执行命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=False)
            
            if result.returncode == 0:
                print(f"✅ 期数 {episode_id} 重新生成成功")
                
                if self.logger:
                    self.logger.info(
                        event_name="episode.rerun.success",
                        message=f"期数 {episode_id} 重新生成成功",
                        episode_id=episode_id
                    )
                return True
            else:
                print(f"❌ 期数 {episode_id} 重新生成失败（退出码: {result.returncode}）")
                
                if self.logger:
                    self.logger.error(
                        event_name="episode.rerun.failed",
                        message=f"期数 {episode_id} 重新生成失败",
                        episode_id=episode_id,
                        metadata={"exit_code": result.returncode}
                    )
                return False
        except Exception as e:
            print(f"❌ 执行生成脚本失败: {e}")
            
            if self.logger:
                import traceback
                self.logger.error(
                    event_name="episode.rerun.error",
                    message=f"期数 {episode_id} 重新生成时发生异常",
                    episode_id=episode_id,
                    traceback=traceback.format_exc()
                )
            return False
    
    def recover_all(self, rerun: bool = False) -> Dict:
        """
        恢复所有失败的期数
        
        Args:
            rerun: 是否自动重新运行生成
        
        Returns:
            恢复结果统计
        """
        failed_episodes = self.find_failed_episodes()
        
        if not failed_episodes:
            print("✅ 没有需要恢复的期数")
            return {"total": 0, "recovered": 0, "failed": 0}
        
        print(f"📋 发现 {len(failed_episodes)} 个失败的期数")
        print(f"   期数ID: {', '.join(failed_episodes)}")
        
        recovered = 0
        failed = 0
        
        for ep_id in failed_episodes:
            if self.recover_episode(ep_id, rerun=rerun):
                recovered += 1
            else:
                failed += 1
        
        return {
            "total": len(failed_episodes),
            "recovered": recovered,
            "failed": failed
        }


def main():
    parser = argparse.ArgumentParser(
        description="期数恢复工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 恢复单个期数
  python scripts/local_picker/recover_episode.py --episode-id 20251102
  
  # 恢复并自动重新运行
  python scripts/local_picker/recover_episode.py --episode-id 20251102 --rerun
  
  # 恢复所有失败的期数
  python scripts/local_picker/recover_episode.py --all
        """
    )
    parser.add_argument(
        "--episode-id",
        type=str,
        help="要恢复的期数ID（YYYYMMDD格式）"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="恢复所有失败的期数"
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="恢复后自动重新运行生成流程"
    )
    
    args = parser.parse_args()
    
    if not args.episode_id and not args.all:
        parser.error("必须指定 --episode-id 或 --all")
    
    try:
        recoverer = EpisodeRecoverer()
        
        if args.all:
            print("=" * 70)
            print("恢复所有失败的期数")
            print("=" * 70)
            result = recoverer.recover_all(rerun=args.rerun)
            print("\n" + "=" * 70)
            print(f"恢复完成: 总计 {result['total']} 个，成功 {result['recovered']} 个，失败 {result['failed']} 个")
            print("=" * 70)
            sys.exit(0 if result['failed'] == 0 else 1)
        else:
            print("=" * 70)
            print(f"恢复期数: {args.episode_id}")
            print("=" * 70)
            success = recoverer.recover_episode(args.episode_id, rerun=args.rerun)
            print("=" * 70)
            sys.exit(0 if success else 1)
    
    except Exception as e:
        print(f"❌ 恢复失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

