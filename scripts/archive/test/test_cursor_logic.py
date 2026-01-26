#!/usr/bin/env python3
"""
测试：验证补齐17日后，指针应该指向23日（因为18-22日都已上传）
"""
from datetime import datetime, timedelta

CODE_START_DATE = "2025-11-12"

# 当前状态：17日缺失，18-22日都已上传，23日往后缺失
CURRENT_UPLOADED = {
    '2025-11-02', '2025-11-12', '2025-11-13', '2025-11-14', 
    '2025-11-15', '2025-11-16',
    # 17日缺失
    '2025-11-18', '2025-11-19', '2025-11-20', '2025-11-21', '2025-11-22',
    # 23日往后缺失
}

# 补齐17日后的状态
AFTER_17_UPLOADED = CURRENT_UPLOADED | {'2025-11-17'}

def find_first_missing_date(uploaded_dates, start_date_str):
    """模拟后端逻辑：查找第一个缺失日期"""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    today = datetime.now()
    end_date = today + timedelta(days=30)  # 检查未来30天
    
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str not in uploaded_dates:
            return date_str
        current_date += timedelta(days=1)
    
    return (end_date + timedelta(days=1)).strftime("%Y-%m-%d")

print("=" * 70)
print("测试：补齐17日后，指针应该指向23日")
print("=" * 70)

print("\n【当前状态（17日缺失）】")
print(f"已上传日期: {sorted(CURRENT_UPLOADED)}")
current_cursor = find_first_missing_date(CURRENT_UPLOADED, CODE_START_DATE)
print(f"时间cursor: {current_cursor}")

print("\n【补齐17日后的状态】")
print(f"已上传日期: {sorted(AFTER_17_UPLOADED)}")
after_17_cursor = find_first_missing_date(AFTER_17_UPLOADED, CODE_START_DATE)
print(f"时间cursor: {after_17_cursor}")

print("\n【验证】")
print(f"期望: 补齐17日后，cursor应该指向 2025-11-23")
print(f"实际: {after_17_cursor}")
if after_17_cursor == "2025-11-23":
    print("✅ 逻辑正确！")
else:
    print(f"❌ 逻辑错误！应该返回 2025-11-23，但返回了 {after_17_cursor}")

# 详细检查12-30日的状态
print("\n【详细检查12-30日的上传状态】")
start = datetime(2025, 11, 12)
for i in range(19):  # 12-30日
    check_date = start + timedelta(days=i)
    date_str = check_date.strftime("%Y-%m-%d")
    is_uploaded = date_str in AFTER_17_UPLOADED
    status = "✅ 已上传" if is_uploaded else "❌ 缺失"
    if not is_uploaded and after_17_cursor == date_str:
        status += " ← 这是cursor"
    print(f"  {date_str}: {status}")

print("\n" + "=" * 70)

