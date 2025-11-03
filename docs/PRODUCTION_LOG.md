# 生产日志系统文档

**⚠️ 已弃用**: 本文档描述了旧的生产日志系统。新架构使用统一状态管理，详见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

本文档保留作为历史参考。

---

## 概述

生产日志系统用于管理基于排播日期的ID生成、追踪生产进度、记录歌库更新历史，确保正式产出物的格式一致性。

## 核心功能

### 1. 排播计划管理

- **起始日期**：默认从 `2025-11-01` 开始
- **排播间隔**：每 2 日一期（可配置）
- **自动计算**：系统自动计算下一个排播日期

### 2. ID 生成逻辑

**旧方式（已废弃）**：
- 基于创建时间：`YYMMDDHHmm` (10位)
- 问题：同一分钟内创建会冲突

**新方式（当前）**：
- 基于排播日期：`YYYYMMDD` (8位)
- 示例：
  - 2025-11-01 → `20251101` (第 1 期)
  - 2025-11-03 → `20251103` (第 2 期)
  - 2025-11-05 → `20251105` (第 3 期)

### 3. 生产记录追踪

每条生产记录包含：
- `episode_id`: 排播日期格式的ID
- `schedule_date`: 排播日期 (YYYY-MM-DD)
- `episode_number`: 期数（从 1 开始）
- `library_snapshot`: 歌库快照（规模、更新时间）
- `created_at`: 创建时间
- `status`: 状态（pending / completed / failed）
- `output_dir`: 输出目录
- `title`: 专辑标题
- `track_count`: 使用的曲目数

### 4. 歌库更新追踪

- 自动记录歌库文件修改时间
- 追踪歌库规模变化
- 记录最后更新时间为生产日志的一部分

## 文件结构

### 生产日志文件（已弃用）

**旧位置**：`config/production_log.json`（已弃用）

**新架构**：状态信息现在存储在 `config/schedule_master.json`，通过统一状态管理器访问。详见 [ARCHITECTURE.md](./ARCHITECTURE.md)

**结构**：
```json
{
  "start_date": "2025-11-01",
  "schedule_interval_days": 2,
  "last_library_update": "2025-11-01T10:30:00",
  "records": [
    {
      "episode_id": "20251101",
      "schedule_date": "2025-11-01",
      "episode_number": 1,
      "library_snapshot": {
        "total_tracks": 420,
        "updated_at": "2025-11-01T09:00:00",
        "library_file": "data/google_sheet/tracklist.tsv"
      },
      "created_at": "2025-11-01T10:30:00",
      "status": "completed",
      "output_dir": "output/20251101_Some_Title",
      "title": "Some Title",
      "track_count": 26
    }
  ]
}
```

## 使用方法

### 1. 单期生成（自动排播日期）

```bash
# 自动使用下一个排播日期
python scripts/local_picker/create_mixtape.py --font_name Lora-Regular
```

### 2. 单期生成（指定排播日期）

```bash
# 指定排播日期（YYYY-MM-DD格式）
python scripts/local_picker/create_mixtape.py \
  --schedule-date 2025-11-03 \
  --font_name Lora-Regular
```

### 3. 批量生成

```bash
# 生成 10 期内容（自动计算排播日期）
make 4kvideo N=10

# 测试模式（使用 DEMO 文件夹）
make 4kvideo N=10 DEMO=1
```

## 配置选项

### 修改起始排播日期

编辑 `scripts/local_picker/state_manager（已迁移）.py`：

```python
DEFAULT_START_DATE = datetime(2025, 11, 1)  # 修改这里
```

### 修改排播间隔

编辑 `scripts/local_picker/state_manager（已迁移）.py`：

```python
SCHEDULE_INTERVAL_DAYS = 2  # 修改这里（改为 1 = 每日一期）
```

## 产能平衡逻辑

### 当前设置

- **歌库规模**：约 400 首（持续增长）
- **日产需求**：31 天需要 806 首（31期 × 26首/期）
- **排播策略**：每 2 日一期
- **月产能**：约 15 期（31天 / 2天）

### 产能计算

```python
# 月需求
daily_episodes = 1
days_per_month = 31
tracks_per_episode = 26
monthly_tracks_needed = daily_episodes * days_per_month * tracks_per_episode
# = 806 首

# 当前歌库
current_library = 400

# 建议间隔
suggested_interval = (current_library * 2) // monthly_tracks_needed
# = 800 / 806 ≈ 1 天（但实际推荐 2 天，留缓冲）

# 实际使用
actual_interval = 2  # 每 2 日一期
```

## 状态管理

### 生产记录状态

- **pending**: 创建中或待完成
- **completed**: 已完成生成
- **failed**: 生成失败

### 状态流转

```
pending → completed ✅
pending → failed ❌
```

## 查询和报告

### 查看生产日志

```python
from scripts.local_picker.state_manager（已迁移） import ProductionLog

log = ProductionLog.load()
print(f"已完成：{sum(1 for r in log.records if r['status'] == 'completed')}")
print(f"待处理：{sum(1 for r in log.records if r['status'] == 'pending')}")
```

### 查看下一期排播日期

```python
from scripts.local_picker.state_manager（已迁移） import ProductionLog

log = ProductionLog.load()
next_date = log.get_next_schedule_date()
print(f"下一期排播日期：{next_date.strftime('%Y-%m-%d')}")
```

## 注意事项

1. **ID 唯一性**：基于排播日期，同一排播日期不会重复生成（除非手动指定已完成的日期）

2. **歌库更新**：每次生成时自动更新歌库快照，追踪规模变化

3. **测试模式**：使用 `--demo` 时，ID仍基于排播日期，但输出目录为 `DEMO/`

4. **备份建议**：定期备份 `config/schedule_master.json（新架构单一数据源）`，避免丢失生产历史

## 故障排除

### 问题：ID 冲突

**原因**：手动指定了已完成的排播日期

**解决**：
- 使用 `--schedule-date` 指定未来的日期
- 或让系统自动计算下一个排播日期

### 问题：生产日志损坏

**解决**：
- 系统会自动创建新的日志文件
- 从备份恢复（如果可用）

### 问题：排播日期计算错误

**检查**：
- `config/schedule_master.json（新架构单一数据源）` 中的 `start_date` 和 `schedule_interval_days`
- 确认记录中的 `schedule_date` 是否连续

## 未来扩展

- [ ] 支持自定义排播计划（跳过特定日期）
- [ ] 支持批量导入历史记录
- [ ] 生成生产报告（Excel/CSV）
- [ ] 歌库更新提醒机制
- [ ] 产能预测和优化建议

