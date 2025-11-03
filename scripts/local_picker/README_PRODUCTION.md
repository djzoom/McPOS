# 生产日志系统快速参考

## 核心概念

**ID 生成逻辑**：从时间戳改为基于**排播日期**

- 旧方式：`YYMMDDHHmm` (10位) - 同一分钟内会冲突 ❌
- 新方式：`YYYYMMDD` (8位) - 基于排播日期，不会冲突 ✅

**排播计划**：每 2 日一期（可配置）

- 2025-11-01 → 第 1 期 (ID: `20251101`)
- 2025-11-03 → 第 2 期 (ID: `20251103`)
- 2025-11-05 → 第 3 期 (ID: `20251105`)

## 快速使用

### 单期生成（自动排播日期）

```bash
python scripts/local_picker/create_mixtape.py --font_name Lora-Regular
```

### 批量生成

```bash
# 生成 10 期完整内容
make 4kvideo N=10

# 测试模式
make 4kvideo N=10 DEMO=1
```

### 指定排播日期

```bash
python scripts/local_picker/create_mixtape.py \
  --schedule-date 2025-11-03 \
  --font_name Lora-Regular
```

## 生产日志文件

- **位置**：`config/production_log.json`
- **自动创建**：首次运行时自动创建
- **自动更新**：每次生成时自动更新

## 产能平衡

- **歌库规模**：约 400 首（持续增长）
- **日产需求**：31 天 × 26 首 = 806 首
- **当前策略**：每 2 日一期 → 月产能约 15 期

## 查看日志

```python
from scripts.local_picker.production_log import ProductionLog

log = ProductionLog.load()
print(f"已完成：{sum(1 for r in log.records if r['status'] == 'completed')}")
print(f"待处理：{sum(1 for r in log.records if r['status'] == 'pending')}")
```

详细文档：`docs/PRODUCTION_LOG.md`

