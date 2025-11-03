# KAT Records 命令行工作流

完整的命令行工作流程，用于生成排播表和批量生成视频。

## 📋 工作流概述

```
1. 生成排播表 → 2. 查看排播表 → 3. 生成视频（按ID或批量）
```

---

## 🎯 步骤1：生成排播表

生成永恒排播表（一旦创建不再变更）。

### 基本用法

```bash
# 生成100期的排播表（默认从系统当前日期开始，间隔2天）
python scripts/local_picker/create_schedule_master.py --episodes 100

# 指定起始日期和间隔
python scripts/local_picker/create_schedule_master.py \
  --episodes 100 \
  --start-date 2025-12-01 \
  --interval 2

# 强制覆盖已存在的排播表
python scripts/local_picker/create_schedule_master.py \
  --episodes 100 \
  --force
```

### 参数说明

| 参数 | 必需 | 说明 | 默认值 |
|------|------|------|--------|
| `--episodes N` | ✅ | 总期数（必须 ≤ 可用图片数量） | - |
| `--start-date YYYY-MM-DD` | ❌ | 起始日期 | 系统当前日期 |
| `--interval DAYS` | ❌ | 排播间隔（天） | 2 |
| `--images-dir PATH` | ❌ | 图片目录 | assets/design/images |
| `--force` | ❌ | 强制覆盖已存在的排播表 | False |

### 输出

- 排播表保存到：`config/schedule_master.json`
- 包含所有期数的ID、日期、图片分配等信息

---

## 📊 步骤2：查看排播表

### 查看排播表内容

```bash
# 使用Python查看
python -c "
from scripts.local_picker.schedule_master import ScheduleMaster
import json
master = ScheduleMaster.load()
if master:
    print(f'总期数: {master.total_episodes}')
    print(f'起始日期: {master.start_date}')
    print(f'已使用图片: {len(master.images_used)}')
    print(f'剩余图片: {len(master.images_pool) - len(master.images_used)}')
    print('\n前10期:')
    for ep in master.episodes[:10]:
        status = ep.get('status', 'pending')
        print(f\"  {ep['episode_id']}: {ep['schedule_date']} [{status}]\")
"
```

### 检查剩余资源

```bash
python -c "
from scripts.local_picker.schedule_master import ScheduleMaster
master = ScheduleMaster.load()
if master:
    remaining, used = master.check_remaining_images()
    print(f'剩余图片: {remaining} 张')
    if remaining < 10:
        print('⚠️  警告：剩余图片不足10张！')
"
```

---

## 🎬 步骤3：生成视频

### 方式1：按ID生成单期

```bash
# 生成指定ID的视频（例如：20251101）
python scripts/local_picker/create_mixtape.py \
  --font_name Lora-Regular \
  --episode-id 20251101

# 测试模式（使用DEMO文件夹）
python scripts/local_picker/create_mixtape.py \
  --font_name Lora-Regular \
  --episode-id 20251101 \
  --demo
```

### 方式2：批量生成N期（按顺序）

```bash
# 生成10期（从排播表第一个pending开始）
make 4kvideo N=10

# 或直接调用
python scripts/local_picker/batch_generate_videos.py 10

# 测试模式
python scripts/local_picker/batch_generate_videos.py 10 --demo
```

### 方式3：按日期范围生成

```bash
# 生成指定日期范围内的所有期数
python scripts/local_picker/batch_generate_by_date.py \
  --start-date 2025-11-01 \
  --end-date 2025-11-30
```

---

## 📝 完整示例

### 示例1：首次创建排播表并生成前5期

```bash
# 1. 创建排播表（假设有100张图片）
python scripts/local_picker/create_schedule_master.py --episodes 100

# 2. 查看排播表
python -c "
from scripts.local_picker.schedule_master import ScheduleMaster
master = ScheduleMaster.load()
print(f'前5期ID: {[ep[\"episode_id\"] for ep in master.episodes[:5]]}')
"

# 3. 生成前5期
python scripts/local_picker/batch_generate_videos.py 5
```

### 示例2：按具体ID生成

```bash
# 生成2025年11月1日的视频
python scripts/local_picker/create_mixtape.py \
  --font_name Lora-Regular \
  --episode-id 20251101 \
  --codec_v auto \
  --duration-fix 1fps-precise
```

### 示例3：持续生产（每天生成）

```bash
# 每天生成下一期
python scripts/local_picker/batch_generate_videos.py 1

# 或者手动指定今天的ID
TODAY=$(date +%Y%m%d)
python scripts/local_picker/create_mixtape.py \
  --font_name Lora-Regular \
  --episode-id $TODAY
```

---

## 🔧 高级用法

### 指定视频编码器

```bash
# 使用硬件加速（macOS）
python scripts/local_picker/create_mixtape.py \
  --font_name Lora-Regular \
  --episode-id 20251101 \
  --codec_v h264_videotoolbox \
  --v_bitrate 6M

# 使用x264（跨平台）
python scripts/local_picker/create_mixtape.py \
  --font_name Lora-Regular \
  --episode-id 20251101 \
  --codec_v libx264 \
  --crf 22 \
  --preset veryfast
```

### 只生成特定步骤

```bash
# 仅生成封面和歌单（不混音、不生成视频）
python scripts/local_picker/create_mixtape.py \
  --font_name Lora-Regular \
  --episode-id 20251101 \
  --no-remix \
  --no-video

# 仅生成封面（最快测试）
python scripts/local_picker/create_mixtape.py \
  --font_name Lora-Regular \
  --episode-id 20251101 \
  --no-remix \
  --no-video \
  --no-youtube
```

---

## 📂 输出目录结构

生成后的文件按以下结构组织：

```
output/
├── DEMO/                          # 测试模式
│   ├── preview_cover.png
│   ├── preview_playlist.csv
│   └── ...
└── 20251101_Title_Name/           # 生产模式（ID_标题）
    ├── 20251101_cover.png
    ├── 20251101_playlist.csv
    ├── 20251101_full_mix.mp3
    ├── 20251101_video.mp4
    ├── 20251101.srt
    ├── 20251101_description.txt
    └── 20251101_youtube_upload.csv
```

---

## ⚠️ 注意事项

1. **排播表一旦创建不可变更**：如需重新创建，使用 `--force`
2. **图片不能重复使用**：确保图片数量 ≥ 期数
3. **ID格式**：YYYYMMDD（如 20251101）
4. **测试模式**：使用 `--demo` 时所有输出在 `DEMO/` 文件夹

---

## 🚨 故障排查

### 排播表不存在

```bash
# 检查排播表
ls -l config/schedule_master.json

# 如果不存在，先创建
python scripts/local_picker/create_schedule_master.py --episodes 100
```

### 图片不足

```bash
# 检查剩余图片
python -c "
from scripts.local_picker.schedule_master import ScheduleMaster
master = ScheduleMaster.load()
remaining, _ = master.check_remaining_images()
print(f'剩余: {remaining} 张')
"
```

### 指定ID不存在

```bash
# 查看所有ID
python -c "
from scripts.local_picker.schedule_master import ScheduleMaster
master = ScheduleMaster.load()
ids = [ep['episode_id'] for ep in master.episodes]
print('可用ID:', ids[:20])
"
```

---

## 📚 相关文档

- [文档索引](./README.md) - 完整文档索引
- [排播表指南](./SCHEDULE_MASTER_GUIDE.md) - 排播表详细指南
- [生产日志说明](./PRODUCTION_LOG.md) - 生产日志系统
- [命令行参考](./cli_reference.md) - CLI命令参考

---

## 🎯 快速参考（Make命令）

```bash
# 创建排播表
make schedule EPISODES=100

# 查看排播表
make show-schedule

# 按ID生成单期
make video-id ID=20251101

# 批量生成N期
make 4kvideo N=10
```

---

## 💡 完整工作流示例

```bash
# 1. 创建排播表（假设有100张图片）
make schedule EPISODES=100

# 2. 查看排播表
make show-schedule

# 3. 生成第一期（按ID）
make video-id ID=20251101

# 或者批量生成前10期
make 4kvideo N=10
```

