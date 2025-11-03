# 📋 排播表创建（带确认和歌库记录）

## 概述

创建新排播表时，系统会自动：
1. **预览排播表信息** - 显示期数、日期范围、图片使用情况
2. **显示歌库状态** - 显示当前曲目数、与上次快照的对比
3. **要求用户确认** - 确认后才真正创建
4. **记录歌库快照** - 自动保存当前歌库状态到生产日志

---

## 使用方法

### 方式1：交互式确认（推荐）

```bash
# 创建排播表（会显示预览并要求确认）
make schedule EPISODES=30 START_DATE=2025-12-01 INTERVAL=2

# 或直接使用脚本
python scripts/local_picker/create_schedule_with_confirmation.py \
    --episodes 30 \
    --start-date 2025-12-01 \
    --interval 2
```

### 方式2：自动确认（跳过交互）

```bash
# 使用 --yes 参数自动确认
make schedule EPISODES=30 START_DATE=2025-12-01 INTERVAL=2 YES=1

# 或
python scripts/local_picker/create_schedule_with_confirmation.py \
    --episodes 30 \
    --start-date 2025-12-01 \
    --interval 2 \
    --yes
```

### 方式3：强制覆盖已存在的排播表

```bash
# 使用 --force 参数
make schedule EPISODES=30 START_DATE=2025-12-01 INTERVAL=2 FORCE=1

# 或
python scripts/local_picker/create_schedule_with_confirmation.py \
    --episodes 30 \
    --start-date 2025-12-01 \
    --interval 2 \
    --force
```

---

## 确认流程详解

### 1. 排播表预览

系统会显示：
- **总期数**: 要创建的期数
- **起始日期**: 第一期的排播日期
- **结束日期**: 最后一期的排播日期
- **排播间隔**: 每期间隔天数
- **可用图片**: 图片池总数
- **将使用**: 需要使用的图片数
- **剩余图片**: 使用后剩余图片数

### 2. 歌库状态检查

系统会显示：
- **总曲目数**: 当前歌库的曲目总数
- **歌库文件**: 歌库CSV文件路径
- **快照时间**: 当前快照的时间戳
- **上次记录**: 生产日志中上次记录的时间
- **上次快照曲目数**: 上次快照的曲目数
- **变化**: 与上次快照的差异（+X 或 -X）

如果这是第一次创建排播表，会提示：
```
⚠️  生产日志中没有歌库记录，这将创建第一个快照
```

### 3. 用户确认

显示将要执行的操作：
1. 创建永恒排播表（一旦创建不可变更）
2. 记录当前歌库快照到生产日志
3. 更新生产日志的歌库更新时间

输入 `yes`、`y`、`是` 或 `确认` 继续，其他输入取消。

### 4. 执行创建

确认后，系统会：
1. 创建排播表文件 (`config/schedule_master.json`)
2. 保存歌库快照到生产日志 (`config/schedule_master.json（新架构单一数据源）`)
3. 更新生产日志的最后更新时间

---

## 歌库快照记录

每次创建排播表时，系统会记录：

```json
{
  "library_snapshots": [
    {
      "total_tracks": 440,
      "updated_at": "2025-11-01T03:58:01.123456",
      "library_file": "data/song_library.csv"
    }
  ],
  "last_library_update": "2025-11-01T03:58:01.123456"
}
```

### 快照用途

1. **追踪歌库变化**: 记录每次排播表创建时的歌库规模
2. **版本管理**: 可以追溯历史快照
3. **容量规划**: 基于歌库规模规划排播期数

---

## 参数说明

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `--episodes` | 总期数（必须） | - | `30` |
| `--start-date` | 起始日期 | `2025-11-01` | `2025-12-01` |
| `--interval` | 排播间隔（天） | `2` | `3` |
| `--images-dir` | 图片目录 | `assets/design/images` | `/path/to/images` |
| `--force` | 强制覆盖已存在的排播表 | `False` | - |
| `--yes` | 自动确认（跳过交互） | `False` | - |

---

## 注意事项

### ⚠️ 排播表一旦创建不可变更

- 排播表是"永恒标准"，一旦创建不应修改
- 如果需要重新创建，必须使用 `--force` 参数
- 建议在创建前仔细检查预览信息

### ⚠️ 图片数量限制

- 期数不能超过可用图片数量
- 系统会在预览阶段检查并报错
- 如果图片不足，需要先添加图片

### ⚠️ 歌库快照覆盖

- 每次创建排播表都会创建新的快照
- 快照会追加到历史记录中（不会覆盖）
- 可以通过生产日志查看所有历史快照

---

## 示例

### 示例1：创建12月的排播表（30期）

```bash
python scripts/local_picker/create_schedule_with_confirmation.py \
    --episodes 30 \
    --start-date 2025-12-01 \
    --interval 2
```

输出：
```
======================================================================
📋 排播表预览
======================================================================
总期数: 30 期
起始日期: 2025-12-01
结束日期: 2026-01-29
排播间隔: 2 天
可用图片: 131 张
将使用: 30 张
剩余图片: 101 张

======================================================================
📚 当前歌库状态
======================================================================
总曲目数: 440 首
歌库文件: data/song_library.csv
快照时间: 2025-11-01T03:58:01.123456
上次记录: 2025-11-01T03:55:44.114623
上次快照曲目数: 440 首
变化: +0 首

======================================================================
⚠️  确认信息
======================================================================

将要执行的操作：
  1. 创建永恒排播表（一旦创建不可变更）
  2. 记录当前歌库快照到生产日志
  3. 更新生产日志的歌库更新时间

是否继续？(yes/no): yes

✅ 排播表创建成功！
✅ 歌库快照已记录
```

### 示例2：自动确认（适用于自动化脚本）

```bash
python scripts/local_picker/create_schedule_with_confirmation.py \
    --episodes 30 \
    --start-date 2025-12-01 \
    --interval 2 \
    --yes
```

---

## 查看记录的歌库快照

```python
from scripts.local_picker.state_manager（已迁移） import ProductionLog

log = ProductionLog.load()
snapshots = getattr(log, 'library_snapshots', [])

for i, snapshot in enumerate(snapshots, 1):
    print(f"快照 {i}: {snapshot['total_tracks']} 首, {snapshot['updated_at']}")
```

---

## 相关命令

- **查看排播表**: `make show-schedule` 或 `python scripts/local_picker/show_schedule.py`
- **生成完整排播**: `python scripts/local_picker/generate_full_schedule.py`
- **分析使用情况**: `python scripts/local_picker/analyze_schedule_usage.py`

---

**最后更新**: 2025-11-01

