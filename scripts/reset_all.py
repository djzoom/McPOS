#!/usr/bin/env python3
# coding: utf-8
"""
完整重置初始化工具

功能（统一状态管理架构）：
1. 删除所有制成品、半成品（output目录下所有文件）
2. 保留排播表结构，但重置所有状态为"pending"
3. 清空images_used和tracks_used（但保留期数列表）
4. 不再操作production_log.json和song_usage.csv（单一数据源原则）

设计原则：
- schedule_master.json 为单一数据源
- 只重置状态，不删除排播表结构
- 其他数据源（production_log, song_usage.csv）通过unified_sync.py从文件系统重建

用法：
    python scripts/reset_all.py          # 交互式确认
    python scripts/reset_all.py --yes    # 跳过确认直接执行
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def clear_output_directory() -> bool:
    """清除output目录下所有内容（包括期数文件夹和根目录文件，保留logs目录结构）"""
    output_dir = REPO_ROOT / "output"
    if not output_dir.exists():
        print("ℹ️  output目录不存在，跳过")
        return True
    
    deleted_files = 0
    deleted_folders = 0
    episode_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}_')
    
    try:
        # 删除期数文件夹
        for item in list(output_dir.iterdir()):
            if item.is_dir():
                if item.name != "logs":
                    try:
                        shutil.rmtree(item)
                        print(f"  ✅ 已删除文件夹: {item.name}/")
                        deleted_folders += 1
                    except Exception as e:
                        print(f"  ❌ 删除文件夹失败 {item.name}: {e}")
                        return False
                else:
                    # 保留logs目录，但清空其内容
                    try:
                        for log_file in item.iterdir():
                            log_file.unlink()
                        print(f"  ✅ 已清空logs目录")
                    except Exception as e:
                        print(f"  ⚠️  清空logs目录失败: {e}")
            
            # 删除根目录文件（如playlist.csv, cover.png等）
            elif item.is_file():
                if item.name != ".gitkeep":
                    try:
                        item.unlink()
                        print(f"  ✅ 已删除文件: {item.name}")
                        deleted_files += 1
                    except Exception as e:
                        print(f"  ❌ 删除文件失败 {item.name}: {e}")
                        return False
        
        print(f"\n   📊 统计: 删除 {deleted_folders} 个文件夹，{deleted_files} 个文件")
        return True
    except Exception as e:
        print(f"❌ 清除output目录失败: {e}")
        return False


def reset_schedule_master() -> bool:
    """
    重置排播表（保留结构，重置状态）
    
    新架构：不删除排播表，只重置状态为pending，清空使用记录
    """
    schedule_path = REPO_ROOT / "config" / "schedule_master.json"
    if not schedule_path.exists():
        print("ℹ️  排播表不存在，跳过")
        return True
    
    try:
        import json
        with schedule_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 重置所有期数状态为pending
        for ep in data.get("episodes", []):
            ep["status"] = "pending"
            ep["tracks_used"] = []
            ep["starting_track"] = None
            # 清除错误信息
            ep.pop("error_details", None)
            ep.pop("error_occurred_at", None)
            ep.pop("status_message", None)
            ep.pop("status_updated_at", None)
            ep.pop("rollback_from", None)
            ep.pop("rollback_at", None)
        
        # 清空images_used（保留images_pool）
        data["images_used"] = []
        
        # 保存
        with schedule_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已重置排播表（所有状态为pending，使用记录已清空）")
        return True
    except Exception as e:
        print(f"❌ 重置排播表失败: {e}")
        return False


# 注意：不再删除production_log.json（单一数据源原则）
# production_log.json应该通过unified_sync.py从文件系统重建


def reset_image_library() -> bool:
    """重置图库使用标记（清空schedule_master.json中的images_used）"""
    schedule_path = REPO_ROOT / "config" / "schedule_master.json"
    if not schedule_path.exists():
        print("ℹ️  排播表不存在，无需重置图库标记")
        return True
    
    try:
        import json
        with schedule_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 清空images_used
        data["images_used"] = []
        
        with schedule_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print("✅ 已重置图库使用标记")
        return True
    except Exception as e:
        print(f"❌ 重置图库标记失败: {e}")
        return False


# 注意：不再操作song_usage.csv（单一数据源原则）
# song_usage.csv应该通过unified_sync.py从schedule_master.json重建
# tracks_used的清空已合并到reset_schedule_master()中


def verify_reset() -> bool:
    """验证重置结果"""
    print("\n" + "=" * 60)
    print("🔍 验证重置结果...")
    print("=" * 60)
    
    all_ok = True
    
    # 1. 检查output目录
    output_dir = REPO_ROOT / "output"
    if output_dir.exists():
        # 检查是否还有期数文件
        episode_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}_')
        remaining_items = []
        for item in output_dir.iterdir():
            if item.is_dir() and item.name != "logs":
                if episode_pattern.match(item.name):
                    remaining_items.append(item.name)
            elif item.is_file() and item.name not in [".gitkeep"]:
                # 检查是否是期数相关文件
                if re.match(r'^\d{8}_', item.name):
                    remaining_items.append(item.name)
        
        if remaining_items:
            print(f"  ❌ output目录仍有残留: {len(remaining_items)} 个")
            all_ok = False
        else:
            print(f"  ✅ output目录已清空")
    else:
        print(f"  ℹ️  output目录不存在（正常）")
    
    # 2. 检查排播表
    schedule_path = REPO_ROOT / "config" / "schedule_master.json"
    if schedule_path.exists():
        print(f"  ⚠️  排播表仍存在（但可能已被清空使用标记）")
        # 进一步检查images_used和tracks_used
        try:
            import json
            with schedule_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            images_used = data.get("images_used", [])
            if isinstance(images_used, list):
                images_count = len(images_used)
            else:
                images_count = len(set(images_used))
            
            tracks_used_total = 0
            for ep in data.get("episodes", []):
                tracks_used_total += len(ep.get("tracks_used", []))
            
            if images_count > 0:
                print(f"  ⚠️  图库使用标记未完全清空: {images_count} 张")
                all_ok = False
            else:
                print(f"  ✅ 图库使用标记已清空")
            
            if tracks_used_total > 0:
                print(f"  ⚠️  歌库使用标记未完全清空: {tracks_used_total} 首")
                all_ok = False
            else:
                print(f"  ✅ 歌库使用标记已清空")
        except Exception as e:
            print(f"  ⚠️  无法验证排播表: {e}")
    else:
        print(f"  ✅ 排播表已删除")
    
    # 3. 检查production_log.json
    production_log_path = REPO_ROOT / "config" / "production_log.json"
    if production_log_path.exists():
        print(f"  ⚠️  生产日志仍存在")
        all_ok = False
    else:
        print(f"  ✅ 生产日志已删除")
    
    # 4. 检查song_usage.csv
    song_usage_path = REPO_ROOT / "data" / "song_usage.csv"
    if song_usage_path.exists():
        try:
            with song_usage_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if len(rows) > 0:
                    print(f"  ⚠️  song_usage.csv仍有记录: {len(rows)} 条")
                    all_ok = False
                else:
                    print(f"  ✅ song_usage.csv已清空")
        except Exception as e:
            print(f"  ⚠️  无法读取song_usage.csv: {e}")
    else:
        print(f"  ℹ️  song_usage.csv不存在（正常）")
    
    print("=" * 60)
    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="完整重置初始化：清空所有制成品、排播表和使用标记",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  %(prog)s          # 交互式确认后执行
  %(prog)s --yes    # 跳过确认直接执行

⚠️  警告：此操作不可逆！将执行：
  - 删除output目录下所有文件（包括期数文件夹）
  - 重置排播表状态（保留结构，所有状态重置为pending）
  - 清空图库使用标记（images_used）
  - 清空歌库使用标记（tracks_used）
  
注意：不会删除production_log.json和song_usage.csv（可通过unified_sync.py重建）
        """
    )
    
    parser.add_argument(
        "--yes",
        action="store_true",
        help="跳过确认提示，直接执行"
    )
    
    args = parser.parse_args()
    
    # 确认提示
    if not args.yes:
        print("⚠️  警告：此操作不可逆！")
        print("   将执行以下操作：")
        print("  1. 删除output目录下所有文件（包括期数文件夹）")
        print("  2. 重置排播表状态（保留结构，所有状态重置为pending）")
        print("  3. 清空图库使用标记（images_used）")
        print("  4. 清空歌库使用标记（tracks_used）")
        print("\n  💡 注意：不会删除production_log.json和song_usage.csv")
        print("     它们可通过 unified_sync.py 从文件系统重建")
        response = input("\n确认执行完整重置？(yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ 已取消")
            sys.exit(0)
    
    print("\n🔄 开始完整重置初始化...")
    print("=" * 60)
    
    success = True
    
    # 1. 清除output目录
    print("\n📁 步骤 1/4: 清除output目录...")
    if not clear_output_directory():
        success = False
    
    # 2. 重置排播表（保留结构，重置状态）
    print("\n📋 步骤 2/4: 重置排播表状态...")
    if not reset_schedule_master():
        success = False
    
    # 3. 重置图库使用标记（已包含在reset_schedule_master中，但为清晰单独列出）
    print("\n🖼️  步骤 3/4: 重置图库使用标记...")
    print("  ℹ️  已在步骤2中完成（清空images_used）")
    
    # 4. 重置歌库使用标记（已包含在reset_schedule_master中）
    print("\n🎵 步骤 4/4: 重置歌库使用标记...")
    print("  ℹ️  已在步骤2中完成（清空tracks_used）")
    print("\n  💡 提示：production_log.json和song_usage.csv可通过以下命令重建：")
    print("     python scripts/local_picker/unified_sync.py --sync")
    
    # 5. 验证重置结果
    print("\n🔍 验证重置结果...")
    if not verify_reset():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 完整重置初始化完成！")
        print("\n💡 提示：")
        print("  - 排播表状态已重置，所有期数为pending状态")
        print("  - 如果需要重建production_log.json和song_usage.csv，运行：")
        print("    python scripts/local_picker/unified_sync.py --sync")
        print("  - 现在可以开始新的制作流程")
    else:
        print("⚠️  重置完成，但部分操作失败，请检查上述输出")
        sys.exit(1)


if __name__ == "__main__":
    main()

