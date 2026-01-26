# RESET 功能检查报告

## 检查日期
2025-01-XX

## 功能概述

RESET 功能用于清理指定 channel 的所有数据，包括：
- Schedule 文件
- Output 目录（所有节目资产）
- Asset usage 文件
- 数据库中的 asset usage 记录
- Log 文件

## 当前实现检查

### ✅ 已正确清理的内容

1. **Schedule 文件** (`_clear_schedule_files`)
   - ✅ Channel-specific `schedule_master.json`
   - ✅ Legacy `schedule_master.json`
   - ✅ 写入最小化的空 schedule

2. **Output 目录** (`_clear_output_directories`)
   - ✅ Channel-specific output 目录下的所有子目录和文件
   - ✅ Legacy output 目录
   - ✅ **包括 manifest 文件**（存储在 `output/{episode_id}/{episode_id}_manifest.json`）

3. **Asset Usage 文件** (`_clear_asset_usage_files`)
   - ✅ Channel-specific `asset_usage_index.json`
   - ✅ Legacy `asset_usage_index.json`

4. **数据库 Asset Usage** (`_reset_asset_usage_db`)
   - ✅ 重置所有 Tracks 的 `times_used=0`, `usage_status=UNUSED`
   - ✅ 重置所有 Images 的 `times_used=0`, `usage_status=UNUSED`
   - ✅ 重置所有 AssetUsage 记录的 `times_used=0`
   - ✅ 包含验证逻辑确保重置成功

5. **Log 文件** (`_clear_log_files`)
   - ✅ Channel 目录下的 `logs` 目录

### ❌ 遗漏的内容

1. **Recipe 文件** (`data/{episode_id}-*.json`)
   - ❌ **未清理**
   - 存储位置：`DATA_ROOT`（通常是 `data/` 目录）
   - 文件模式：`{episode_id}-{hash}.json`
   - 影响：重置后，旧的 recipe 文件仍然存在，可能导致 idempotency 问题

2. **Run Journal 文件** (`data/run_journal.json`)
   - ❌ **未清理**
   - 存储位置：`DATA_ROOT / "run_journal.json"`
   - 影响：重置后，旧的运行记录仍然存在

## 问题分析

### Recipe 文件的影响

Recipe 文件存储在 `data/` 目录下，格式为 `{episode_id}-{hash}.json`。这些文件在 `init_episode` 时会被检查：

```python
existing_recipe_files = list(episode_output_dir.glob(f"{request.episode_id}-*.json"))
existing_recipe_files.extend(list(DATA_ROOT.glob(f"{request.episode_id}-*.json")))
```

如果 RESET 后这些文件仍然存在，可能会导致：
1. 旧的 recipe 被重用，而不是生成新的
2. 可能导致不一致的状态

### Run Journal 文件的影响

Run Journal 文件记录运行历史，如果 RESET 后仍然存在，可能会导致：
1. 旧的运行记录影响新的运行
2. 统计数据不准确

## 修复建议

### 1. 添加 Recipe 文件清理

在 `_clear_output_directories` 或新增 `_clear_data_files` 函数中：

```python
def _clear_data_files(channel_id: str, deleted_files: list, errors: list):
    """Clear recipe and journal files from data directory"""
    import os
    from ..routes.plan import DATA_ROOT
    
    if not DATA_ROOT.exists():
        return
    
    # 1. Delete all recipe files for episodes in this channel
    # We need to get episode IDs from schedule before it's cleared
    # Or delete all recipe files matching pattern {episode_id}-*.json
    # Since we don't know episode IDs after schedule is cleared,
    # we should delete recipe files BEFORE clearing schedule
    
    # 2. Delete run_journal.json
    run_journal_path = DATA_ROOT / "run_journal.json"
    if run_journal_path.exists():
        _delete_file_safe(run_journal_path, deleted_files, errors)
```

**注意**：Recipe 文件清理应该在清理 schedule 之前进行，因为我们需要从 schedule 中获取 episode_id 列表。

### 2. 修改清理顺序

当前清理顺序：
1. Schedule 文件
2. Output 目录
3. Asset usage 文件
4. 数据库 asset usage
5. Log 文件

**建议顺序**：
1. **Data 文件（Recipe, Run Journal）** - 需要从 schedule 获取 episode_id
2. Schedule 文件
3. Output 目录
4. Asset usage 文件
5. 数据库 asset usage
6. Log 文件

## 修复实现

需要在 `reset.py` 中添加：

1. `_clear_data_files` 函数
2. 在 `reset_channel` 中调用，顺序在清理 schedule 之前

## 相关代码位置

- `kat_rec_web/backend/t2r/routes/reset.py` - RESET 功能主文件
- `kat_rec_web/backend/t2r/routes/plan.py:64` - DATA_ROOT 定义
- `kat_rec_web/backend/t2r/routes/plan.py:409-410` - Recipe 文件查找逻辑

## 更新日期

2025-01-XX

