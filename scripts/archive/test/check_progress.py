#!/usr/bin/env python3
"""
快速查看重命名进度
"""
import csv
from pathlib import Path

def main():
    plan_path = Path("channels/rbr/library/songs/rename_plan_final_all.csv")
    total = 727
    
    if not plan_path.exists():
        print("⏳ CSV文件还未创建")
        return
    
    with plan_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = sum(1 for _ in reader)
    
    percent = count * 100 // total
    remaining = total - count
    
    print("═══════════════════════════════════════════════════════════")
    print("📊 重命名进度")
    print("═══════════════════════════════════════════════════════════")
    print(f"✅ 已处理: {count} / {total} ({percent}%)")
    print(f"⏳ 剩余: {remaining} 个文件")
    if count > 0:
        bar_length = 50
        filled = count * bar_length // total
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"📈 进度条: [{bar}] {percent}%")
    print("═══════════════════════════════════════════════════════════")
    
    # 显示最后3条
    if count > 0:
        print("\n📝 最后3条记录:")
        with plan_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            for i, row in enumerate(rows[-3:], 1):
                title = row["new"].replace(".mp3", "")
                artist = row["artist"]
                idx = count - len(rows) + i
                print(f"  {idx}. {title:40s} | {artist}")

if __name__ == "__main__":
    main()

