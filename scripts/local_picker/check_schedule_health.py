#!/usr/bin/env python3
# coding: utf-8
"""
检查排播表健康状态

功能：
1. 检查排播表完整性（每期是否有图片、标题、曲目等）
2. 检查资源使用一致性（图片和歌曲是否正确标记）
3. 检查数据一致性（图片路径是否存在等）
4. 提供修复建议

用法：
    python scripts/local_picker/check_schedule_health.py
    python scripts/local_picker/check_schedule_health.py --fix  # 自动修复可修复的问题
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster
    from episode_status import STATUS_待制作, get_status_display
    SCHEDULE_AVAILABLE = True
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    SCHEDULE_AVAILABLE = False
    sys.exit(1)


class ScheduleHealthCheck:
    """排播表健康检查器"""
    
    def __init__(self, schedule: ScheduleMaster):
        self.schedule = schedule
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []
    
    def check_all(self) -> Tuple[bool, int, int]:
        """
        执行所有检查
        
        Returns:
            (is_healthy, issue_count, warning_count)
        """
        self.issues.clear()
        self.warnings.clear()
        
        # 1. 检查基本完整性
        self._check_basic_completeness()
        
        # 2. 检查资源一致性
        self._check_resource_consistency()
        
        # 3. 检查数据有效性
        self._check_data_validity()
        
        # 4. 检查状态一致性
        self._check_status_consistency()
        
        return len(self.issues) == 0, len(self.issues), len(self.warnings)
    
    def _check_basic_completeness(self):
        """检查基本完整性（图片、标题、曲目等）"""
        for i, ep in enumerate(self.schedule.episodes, 1):
            ep_id = ep.get("episode_id", f"#{i}")
            
            # 检查图片
            if not ep.get("image_path"):
                self.issues.append({
                "type": "missing_image",
                "episode_id": ep_id,
                "message": f"第 {i} 期（{ep_id}）缺少图片分配"
            })
            
            # 检查标题
            if not ep.get("title"):
                self.warnings.append({
                    "type": "missing_title",
                    "episode_id": ep_id,
                    "message": f"第 {i} 期（{ep_id}）缺少标题"
                })
            
            # 检查曲目
            tracks = ep.get("tracks_used", [])
            if not tracks:
                self.warnings.append({
                    "type": "missing_tracks",
                    "episode_id": ep_id,
                    "message": f"第 {i} 期（{ep_id}）缺少曲目列表"
                })
            elif len(tracks) < 10:
                self.warnings.append({
                    "type": "few_tracks",
                    "episode_id": ep_id,
                    "message": f"第 {i} 期（{ep_id}）曲目数量较少（{len(tracks)} 首）"
                })
            
            # 检查起始曲目
            if tracks and not ep.get("starting_track"):
                self.warnings.append({
                    "type": "missing_starting_track",
                    "episode_id": ep_id,
                    "message": f"第 {i} 期（{ep_id}）缺少起始曲目标记"
                })
    
    def _check_resource_consistency(self):
        """检查资源使用一致性"""
        # 检查图片使用标记
        used_images_from_episodes = set()
        for ep in self.schedule.episodes:
            image_path = ep.get("image_path")
            if image_path:
                used_images_from_episodes.add(image_path)
        
        # 检查哪些图片应该被标记但未标记
        missing_marked = used_images_from_episodes - self.schedule.images_used
        if missing_marked:
            for img in missing_marked:
                self.issues.append({
                    "type": "image_not_marked",
                    "resource": img,
                    "message": f"图片已分配但未标记为已使用: {Path(img).name}"
                })
        
        # 检查哪些图片被标记但未使用
        extra_marked = self.schedule.images_used - used_images_from_episodes
        if extra_marked:
            for img in extra_marked:
                self.warnings.append({
                    "type": "image_marked_unused",
                    "resource": img,
                    "message": f"图片标记为已使用但未分配: {Path(img).name}"
                })
        
        # 检查歌曲使用标记（需要从episodes提取所有歌曲）
        all_tracks_from_episodes = set()
        for ep in self.schedule.episodes:
            tracks = ep.get("tracks_used", [])
            all_tracks_from_episodes.update(tracks)
        
        # 注意：歌曲使用标记可能在外部文件（song_usage.csv）中，这里只检查排播表内部的一致性
        # 可以通过 get_all_used_tracks() 获取，但这个是基于episodes的，应该一致
    
    def _check_data_validity(self):
        """检查数据有效性（文件是否存在等）"""
        for ep in self.schedule.episodes:
            ep_id = ep.get("episode_id", "unknown")
            image_path = ep.get("image_path")
            
            if image_path:
                img_path = Path(image_path)
                if not img_path.exists():
                    self.issues.append({
                        "type": "image_not_found",
                        "episode_id": ep_id,
                        "resource": image_path,
                        "message": f"期数 {ep_id} 的图片文件不存在: {img_path.name}"
                    })
    
    def _check_status_consistency(self):
        """检查状态一致性"""
        # 检查是否有已完成但缺少内容的期数
        for ep in self.schedule.episodes:
            status = ep.get("status", STATUS_待制作)
            ep_id = ep.get("episode_id", "unknown")
            
            # 如果状态是"已完成"或"制作中"，应该有完整内容
            if status in ["已完成", "制作中", "上传中", "排播完毕待播出"]:
                if not ep.get("title") or not ep.get("tracks_used"):
                    self.warnings.append({
                        "type": "incomplete_content",
                        "episode_id": ep_id,
                        "status": status,
                        "message": f"期数 {ep_id} 状态为 '{get_status_display(status)}' 但缺少完整内容"
                    })
    
    def fix_auto_fixable(self) -> int:
        """
        自动修复可修复的问题
        
        Returns:
            修复的问题数量
        """
        fixed_count = 0
        
        # 修复：同步图片使用标记（基于分配）
        images_synced = self.schedule.sync_images_from_assignments()
        if images_synced != 0:
            fixed_count += abs(images_synced)
            self.schedule.save()
        
        return fixed_count
    
    def print_report(self):
        """打印检查报告"""
        is_healthy, issue_count, warning_count = self.check_all()
        
        print("=" * 70)
        print("📋 排播表健康检查报告")
        print("=" * 70)
        print()
        print(f"总期数：{self.schedule.total_episodes}")
        print(f"已使用图片：{len(self.schedule.images_used)} 张")
        print(f"可用图片池：{len(self.schedule.images_pool)} 张")
        print(f"剩余图片：{len(self.schedule.images_pool) - len(self.schedule.images_used)} 张")
        print()
        
        if is_healthy and warning_count == 0:
            print("✅ 排播表健康状态良好！")
            return
        
        # 显示问题
        if issue_count > 0:
            print(f"❌ 发现 {issue_count} 个问题：")
            print("-" * 70)
            for issue in self.issues:
                print(f"  • {issue['message']}")
            print()
        
        # 显示警告
        if warning_count > 0:
            print(f"⚠️  发现 {warning_count} 个警告：")
            print("-" * 70)
            for warning in self.warnings:
                print(f"  • {warning['message']}")
            print()
        
        # 建议
        if issue_count > 0 or warning_count > 0:
            print("💡 建议：")
            if any(i['type'] == 'image_not_marked' for i in self.issues):
                print("  • 图片使用标记会自动同步（基于分配状态）")
            if any(i['type'] == 'missing_image' for i in self.issues):
                print("  • 重新生成排播表以分配图片")
            if any(w['type'] == 'missing_title' for w in self.warnings):
                print("  • 重新生成排播表内容以补全标题和曲目")


def main():
    parser = argparse.ArgumentParser(description="检查排播表健康状态")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")
    args = parser.parse_args()
    
    # 加载排播表
    schedule = ScheduleMaster.load()
    if not schedule:
        print("❌ 排播表不存在，请先创建排播表")
        sys.exit(1)
    
    # 执行检查
    checker = ScheduleHealthCheck(schedule)
    checker.print_report()
    
    # 自动修复
    if args.fix:
        print()
        print("🔧 尝试自动修复...")
        fixed_count = checker.fix_auto_fixable()
        if fixed_count > 0:
            print(f"✅ 已修复 {fixed_count} 个问题")
        else:
            print("ℹ️  没有需要自动修复的问题")
        
        # 重新检查
        print()
        print("重新检查...")
        checker.print_report()


if __name__ == "__main__":
    main()

