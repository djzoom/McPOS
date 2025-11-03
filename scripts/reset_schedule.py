#!/usr/bin/env python3
# coding: utf-8
"""
重置排播表和输出文件

功能：
1. 清除排播表（config/schedule_master.json）
2. 可选清除output下的期数文件夹（保留logs）
3. 可选完全清除output目录（包括logs）

用法：
    python scripts/reset_schedule.py --schedule-only          # 只清除排播表
    python scripts/reset_schedule.py --include-output         # 清除排播表 + 期数文件夹
    python scripts/reset_schedule.py --full-reset             # 完全清除（排播表 + 所有output）
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def clear_schedule_master() -> bool:
    """清除排播表"""
    schedule_path = REPO_ROOT / "config" / "schedule_master.json"
    if schedule_path.exists():
        try:
            schedule_path.unlink()
            print(f"✅ 已删除排播表: {schedule_path}")
            return True
        except Exception as e:
            print(f"❌ 删除排播表失败: {e}")
            return False
    else:
        print("ℹ️  排播表不存在，跳过")
        return True


def clear_episode_folders(output_dir: Path) -> tuple[int, int]:
    """清除output下的期数文件夹（匹配模式 YYYY-MM-DD_*），保留logs目录"""
    if not output_dir.exists():
        print("ℹ️  output目录不存在，跳过")
        return 0, 0
    
    episode_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}_')
    deleted_count = 0
    skipped_count = 0
    
    for item in output_dir.iterdir():
        if item.is_dir() and item.name != "logs":
            if episode_pattern.match(item.name):
                try:
                    shutil.rmtree(item)
                    print(f"  ✅ 已删除: {item.name}/")
                    deleted_count += 1
                except Exception as e:
                    print(f"  ❌ 删除失败 {item.name}: {e}")
                    skipped_count += 1
    
    return deleted_count, skipped_count


def clear_all_output(output_dir: Path) -> bool:
    """完全清除output目录（包括logs）"""
    if not output_dir.exists():
        print("ℹ️  output目录不存在，跳过")
        return True
    
    try:
        shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ 已完全清除output目录: {output_dir}")
        return True
    except Exception as e:
        print(f"❌ 清除output目录失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="重置排播表和输出文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  %(prog)s --schedule-only          # 只清除排播表
  %(prog)s --include-output         # 清除排播表 + output下的期数文件夹（保留logs）
  %(prog)s --full-reset             # 完全清除（排播表 + 所有output内容）

⚠️  警告：此操作不可逆！请谨慎使用。
        """
    )
    
    # 互斥选项
    reset_group = parser.add_mutually_exclusive_group(required=True)
    reset_group.add_argument(
        "--schedule-only",
        action="store_true",
        help="只清除排播表（config/schedule_master.json）"
    )
    reset_group.add_argument(
        "--include-output",
        action="store_true",
        help="清除排播表 + output下的期数文件夹（保留logs目录）"
    )
    reset_group.add_argument(
        "--full-reset",
        action="store_true",
        help="完全清除：排播表 + output目录下所有内容（包括logs）"
    )
    
    parser.add_argument(
        "--yes",
        action="store_true",
        help="跳过确认提示，直接执行"
    )
    
    args = parser.parse_args()
    
    # 确认提示
    if not args.yes:
        if args.schedule_only:
            action = "清除排播表"
        elif args.include_output:
            action = "清除排播表并删除output下的期数文件夹（保留logs）"
        else:
            action = "完全清除排播表和output目录（包括logs）"
        
        print("⚠️  警告：此操作不可逆！")
        print(f"   将执行: {action}")
        response = input("\n确认执行？(yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ 已取消")
            sys.exit(0)
    
    print("\n🔄 开始重置...")
    print("=" * 60)
    
    output_dir = REPO_ROOT / "output"
    success = True
    
    # 清除排播表
    print("\n📋 清除排播表...")
    if not clear_schedule_master():
        success = False
    
    # 根据选项清除output
    if args.include_output:
        print("\n📁 清除output下的期数文件夹...")
        deleted, skipped = clear_episode_folders(output_dir)
        print(f"   ✅ 已删除 {deleted} 个文件夹")
        if skipped > 0:
            print(f"   ⚠️  跳过 {skipped} 个文件夹（删除失败）")
            success = False
    
    elif args.full_reset:
        print("\n📁 完全清除output目录...")
        if not clear_all_output(output_dir):
            success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 重置完成！")
    else:
        print("⚠️  重置完成，但部分操作失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

