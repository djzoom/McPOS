#!/usr/bin/env python3
"""
测试脚本：模拟17日上传完毕后，时间cursor会如何变化
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "kat_rec_web" / "backend"))

# 模拟当前YouTube已上传的日期
# 当前：['2025-11-02', '2025-11-12', '2025-11-13', '2025-11-14', '2025-11-15', '2025-11-16']
# 假设17日上传完毕后的情况
CURRENT_UPLOADED_DATES = {
    '2025-11-02', '2025-11-12', '2025-11-13', '2025-11-14', 
    '2025-11-15', '2025-11-16'
}

AFTER_17_UPLOADED_DATES = {
    '2025-11-02', '2025-11-12', '2025-11-13', '2025-11-14', 
    '2025-11-15', '2025-11-16', '2025-11-17'  # 添加17日
}

CODE_START_DATE = "2025-11-12"

def find_first_missing_date(uploaded_dates, start_date_str, end_date_str=None):
    """查找第一个空缺日期"""
    if end_date_str is None:
        end_date_str = datetime.now().strftime("%Y-%m-%d")
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    # 检查未来30天
    check_end = end_date + timedelta(days=30)
    
    current_date = start_date
    while current_date <= check_end:
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str not in uploaded_dates:
            return date_str
        current_date += timedelta(days=1)
    
    # 如果所有日期都已上传，返回最后检查日期的下一天
    return (check_end + timedelta(days=1)).strftime("%Y-%m-%d")

def calculate_date_range_from_cursor(cursor_date, days=14):
    """从cursor日期计算日期范围"""
    start = datetime.strptime(cursor_date, "%Y-%m-%d")
    end = start + timedelta(days=days - 1)
    return {
        'from': start.strftime("%Y-%m-%d"),
        'to': end.strftime("%Y-%m-%d")
    }

print("=" * 60)
print("测试：17日上传完毕后，时间cursor和显示的变化")
print("=" * 60)

# 当前状态
print("\n【当前状态】")
current_cursor = find_first_missing_date(CURRENT_UPLOADED_DATES, CODE_START_DATE)
print(f"已上传日期: {sorted(CURRENT_UPLOADED_DATES)}")
print(f"时间cursor: {current_cursor}")
current_range = calculate_date_range_from_cursor(current_cursor, 14)
print(f"日期范围: {current_range['from']} 至 {current_range['to']}")
print(f"格子显示: 从 {current_range['from']} 开始")

# 17日上传完毕后的状态
print("\n【17日上传完毕后的状态】")
after_17_cursor = find_first_missing_date(AFTER_17_UPLOADED_DATES, CODE_START_DATE)
print(f"已上传日期: {sorted(AFTER_17_UPLOADED_DATES)}")
print(f"时间cursor: {after_17_cursor}")
after_17_range = calculate_date_range_from_cursor(after_17_cursor, 14)
print(f"日期范围: {after_17_range['from']} 至 {after_17_range['to']}")
print(f"格子显示: 从 {after_17_range['from']} 开始")

# 分析
print("\n【分析】")
print(f"时间cursor变化: {current_cursor} → {after_17_cursor}")
print(f"日期范围变化: {current_range['from']} 至 {current_range['to']} → {after_17_range['from']} 至 {after_17_range['to']}")
print(f"格子起始日期变化: {current_range['from']} → {after_17_range['from']}")

# 检查18日及之后的日期
print("\n【检查后续日期】")
today = datetime.now()
check_dates = []
for i in range(18, 25):  # 检查18-24日
    check_date = datetime(2025, 11, i)
    date_str = check_date.strftime("%Y-%m-%d")
    is_uploaded = date_str in AFTER_17_UPLOADED_DATES
    check_dates.append((date_str, is_uploaded))
    if not is_uploaded:
        print(f"  {date_str}: 未上传 (这将是下一个cursor)")
        break
    else:
        print(f"  {date_str}: 已上传")

print("\n" + "=" * 60)
print("结论：")
print(f"1. 时间指针会从 {current_cursor} 变为 {after_17_cursor}")
print(f"2. 日期范围会从 {current_range['from']} 开始变为从 {after_17_range['from']} 开始")
print(f"3. 格子会从 {current_range['from']} 开始显示变为从 {after_17_range['from']} 开始显示")
print("=" * 60)

