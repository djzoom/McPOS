#!/usr/bin/env python3
"""
详细测试：17日上传完毕后，完整的前后端流程
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "kat_rec_web" / "backend"))

CODE_START_DATE = "2025-11-12"

# 当前YouTube已上传的日期（从日志中获取）
CURRENT_UPLOADED = {
    '2025-11-02', '2025-11-12', '2025-11-13', '2025-11-14', 
    '2025-11-15', '2025-11-16'
}

# 17日上传完毕后的日期
AFTER_17_UPLOADED = CURRENT_UPLOADED | {'2025-11-17'}

def simulate_cursor_calculation(uploaded_dates, start_date_str):
    """模拟后端calculate_work_cursor_date的逻辑"""
    # 从CODE_START_DATE开始，检查未来30天
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    today = datetime.now()
    end_date = today + timedelta(days=30)
    
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str not in uploaded_dates:
            return date_str
        current_date += timedelta(days=1)
    
    # 如果所有日期都已上传，返回最后检查日期的下一天
    return (end_date + timedelta(days=1)).strftime("%Y-%m-%d")

def simulate_frontend_date_range(cursor_date, days=14):
    """模拟前端calculateDateRangeFromCursor的逻辑"""
    start = datetime.strptime(cursor_date, "%Y-%m-%d")
    end = start + timedelta(days=days - 1)
    return {
        'from': start.strftime("%Y-%m-%d"),
        'to': end.strftime("%Y-%m-%d")
    }

def simulate_date_array(cursor_date, date_range):
    """模拟前端dateArray的计算逻辑"""
    dates = []
    cursor_dt = datetime.strptime(cursor_date, "%Y-%m-%d")
    end_dt = datetime.strptime(date_range['to'], "%Y-%m-%d")
    
    current = cursor_dt
    while current <= end_dt:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    return dates

print("=" * 70)
print("完整流程测试：17日上传完毕后的变化")
print("=" * 70)

# 步骤1: 当前状态
print("\n【步骤1: 当前状态（17日未上传）】")
current_cursor = simulate_cursor_calculation(CURRENT_UPLOADED, CODE_START_DATE)
current_range = simulate_frontend_date_range(current_cursor, 14)
current_date_array = simulate_date_array(current_cursor, current_range)

print(f"后端返回的work_cursor_date: {current_cursor}")
print(f"前端计算的dateRange: {current_range['from']} 至 {current_range['to']}")
print(f"前端计算的dateArray (前5个): {current_date_array[:5]}")
print(f"时间指针显示: {current_cursor}")
print(f"格子起始日期: {current_date_array[0]}")

# 步骤2: 17日上传完毕
print("\n【步骤2: 17日上传完毕（触发上传完成事件）】")
print("WebSocket事件: upload_state_changed")
print("前端操作: queryClient.invalidateQueries({ queryKey: ['t2r-work-cursor'] })")
print("→ 立即重新获取work cursor date")

# 步骤3: 后端重新计算
print("\n【步骤3: 后端重新计算work cursor】")
after_17_cursor = simulate_cursor_calculation(AFTER_17_UPLOADED, CODE_START_DATE)
print(f"后端查询YouTube，发现17日已上传")
print(f"后端返回新的work_cursor_date: {after_17_cursor}")

# 步骤4: 前端接收并更新
print("\n【步骤4: 前端接收新的work cursor date】")
print(f"useScheduleHydrator: setWorkCursorDate('kat_lofi', '{after_17_cursor}')")
print(f"Store更新: workCursorDate['kat_lofi'] = '{after_17_cursor}'")

# 步骤5: 自动更新日期范围
print("\n【步骤5: useScheduleWindow自动更新dateRange】")
print(f"检测到: dateRange.from ({current_range['from']}) < workCursorDate ({after_17_cursor})")
after_17_range = simulate_frontend_date_range(after_17_cursor, 14)
print(f"自动更新dateRange: {after_17_range['from']} 至 {after_17_range['to']}")

# 步骤6: OverviewGrid重新计算dateArray
print("\n【步骤6: OverviewGrid重新计算dateArray】")
after_17_date_array = simulate_date_array(after_17_cursor, after_17_range)
print(f"从workCursorDate ({after_17_cursor}) 开始计算")
print(f"新的dateArray (前5个): {after_17_date_array[:5]}")

# 步骤7: 最终显示
print("\n【步骤7: 最终显示结果】")
print(f"时间指针显示: {after_17_cursor}")
print(f"日期范围显示: {after_17_range['from']} 至 {after_17_range['to']}")
print(f"格子起始日期: {after_17_date_array[0]}")
print(f"格子列数: {len(after_17_date_array)} 列")

# 总结
print("\n" + "=" * 70)
print("【总结】")
print("=" * 70)
print(f"1. 时间指针: {current_cursor} → {after_17_cursor}")
print(f"2. 日期范围: {current_range['from']} 至 {current_range['to']} → {after_17_range['from']} 至 {after_17_range['to']}")
print(f"3. 格子显示: 从 {current_date_array[0]} 开始 → 从 {after_17_date_array[0]} 开始")
print(f"4. 更新时机: 上传完成后，WebSocket立即触发，无需等待30秒轮询")
print("=" * 70)

