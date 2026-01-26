# 重置时间游标并生成12月所有LP

## 概述

本脚本用于：
1. **重置时间游标**到 2025年12月1日
2. **初始化12月排播表**（创建所有期数的文件夹和playlist.csv）
3. **批量生成12月的所有LP**（执行完整制播流程，**只生成不上传**）

## 重要特性

### ✅ 使用未使用过的图片

- 封面生成会自动检查 `asset_usage_index.json`
- 优先选择**从未使用过的图片**制作封面
- 如果所有图片都已使用，会从所有图片中随机选择
- 确保每期使用不同的图片，避免重复

### ✅ 只生成不上传

- 批量生成**不会自动上传**到YouTube
- 执行阶段：`Init → Cover → Text → Remix → Render`
- **不包括 Upload 阶段**
- 生成完成后，可以手动选择上传

## 使用方法

### 基本用法

```bash
# 使用默认设置（频道: kat_lofi, 时间游标: 2025-12-01）
python scripts/reset_and_generate_december.py

# 指定频道
python scripts/reset_and_generate_december.py --channel kat_lofi

# 指定时间游标日期
python scripts/reset_and_generate_december.py --cursor-date 2025-12-01

# 指定API URL（如果后端不在localhost:8000）
python scripts/reset_and_generate_december.py --api-url http://localhost:8000
```

### 预览模式（Dry Run）

在执行前先预览将要执行的操作：

```bash
python scripts/reset_and_generate_december.py --dry-run
```

### 完整示例

```bash
# 重置到12月1日，然后生成整个12月的所有LP（使用未使用的图片，不上传）
python scripts/reset_and_generate_december.py \
  --channel kat_lofi \
  --cursor-date 2025-12-01 \
  --api-url http://localhost:8000
```

## 执行步骤

脚本会按以下顺序执行：

1. **重置时间游标**
   - 设置 `work_cursor_date` 为 `2025-12-01`
   - 使用API端点 `/api/t2r/schedule/work-cursor/set`
   - 如果API失败，会回退到直接更新文件

2. **初始化排播表**
   - 调用 `/api/t2r/schedule/initialize`
   - 创建12月所有期数的输出文件夹
   - 生成空的 `playlist.csv` 文件
   - 更新 `schedule_master.json`

3. **批量生成**（**只生成不上传**）
   - 调用 `/api/t2r/automation/batch-generate`
   - 对每期执行完整制播流程：
     - **Init**（初始化）- 生成playlist和recipe
     - **Cover**（封面生成）- **使用未使用过的图片**
     - **Text**（文本资产）- 生成标题、描述、标签、字幕
     - **Remix**（音频混音）- 生成MP3和WAV
     - **Render**（视频渲染）- 生成MP4视频
     - **❌ 不包括 Upload** - 不会上传到YouTube

## 图片选择机制

### 如何确保使用未使用的图片

1. **读取 asset_usage_index.json**
   - 系统会读取 `data/asset_usage_index.json` 文件
   - 该文件记录了每张图片被哪些期数使用过

2. **过滤未使用的图片**
   - 扫描图片库中的所有图片
   - 排除已在 `asset_usage_index.json` 中记录的图片
   - 从剩余图片中随机选择

3. **更新使用记录**
   - 生成封面后，会更新 `asset_usage_index.json`
   - 记录该图片被当前期数使用

### 示例

假设有100张图片，其中50张已被使用：
- 系统会从剩余的50张未使用的图片中选择
- 如果50张都用完了，会从所有100张中随机选择

## 生成内容

批量生成会为每期创建以下文件：

### 必需文件

- `playlist.csv` - 歌单文件
- `recipe.json` - 配方文件
- `{episode_id}_cover.png` - 封面图片（4K）
- `{episode_id}_youtube_title.txt` - YouTube标题
- `{episode_id}_youtube_description.txt` - YouTube描述
- `{episode_id}_youtube_tags.txt` - YouTube标签
- `{episode_id}_youtube.srt` - YouTube字幕
- `{episode_id}_full_mix.mp3` - 混音音频（MP3）
- `{episode_id}_final_mix.wav` - 预混音音频（WAV）
- `{episode_id}_youtube.mp4` - 最终视频（4K）

### 检查点文件

- `{episode_id}.remix.complete.flag` - 混音完成标记
- `{episode_id}.render.complete.flag` - 渲染完成标记

## 上传（手动）

批量生成**不会自动上传**。如果需要上传，可以：

### 方法1: 使用批量上传API

```bash
# 批量上传已生成的期数
curl -X POST "http://localhost:8000/api/t2r/upload/batch-start" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "kat_lofi",
    "episode_ids": ["20251201", "20251203", ...],
    "priority": "high",
    "auto_schedule": true
  }'
```

### 方法2: 使用前端界面

访问 `/t2r/batch` 页面，使用批量上传功能。

## API端点

### 手动设置时间游标

```bash
POST /api/t2r/schedule/work-cursor/set?channel_id=kat_lofi
Content-Type: application/json

{
  "cursor_date": "2025-12-01"
}
```

### 初始化排播表

```bash
POST /api/t2r/schedule/initialize?channel_id=kat_lofi
Content-Type: application/json

{
  "days": 31,
  "start_date": "2025-12-01"
}
```

### 批量生成（只生成不上传）

```bash
POST /api/t2r/automation/batch-generate
Content-Type: application/json

{
  "channel_id": "kat_lofi",
  "days": 31
}
```

## 注意事项

1. **时间游标的作用**
   - 时间游标（work_cursor_date）定义了系统开始工作的日期
   - 早于时间游标的期数不会被处理
   - 重置时间游标后，系统会从该日期开始工作

2. **12月期数计算**
   - 12月有31天
   - 假设每2天一期，大约会创建15-16期
   - 具体期数取决于排播间隔设置

3. **图片使用**
   - 系统会自动避免使用已使用的图片
   - 如果图片库不足，可能会重复使用图片
   - 建议确保有足够的未使用图片（至少15-20张）

4. **批量生成时间**
   - 批量生成是后台任务，可能需要较长时间
   - 每期大约需要5-10分钟（取决于音频长度）
   - 15期大约需要1.5-2.5小时
   - 可以通过WebSocket实时查看进度

5. **不上传**
   - 批量生成**不会自动上传**
   - 生成完成后，需要手动选择上传
   - 可以批量上传，也可以单期上传

## 监控进度

### 通过WebSocket

批量生成会通过WebSocket发送进度事件：

- `batch_generate_started` - 批量生成开始
- `batch_generate_progress` - 批量生成进度
- `batch_generate_completed` - 批量生成完成

### 通过API

```bash
# 查看排播表状态
GET /api/t2r/schedule/episodes?channel_id=kat_lofi

# 查看时间游标
GET /api/t2r/schedule/work-cursor?channel_id=kat_lofi

# 查看图片使用情况
cat data/asset_usage_index.json | jq '.images | keys | length'
```

## 故障排查

### 时间游标重置失败

- 检查频道ID是否正确
- 检查日期格式是否为 `YYYY-MM-DD`
- 检查 `schedule_master.json` 文件权限

### 排播表初始化失败

- 检查输出目录权限
- 检查磁盘空间
- 查看后端日志

### 批量生成失败

- 检查音频库和图片库是否充足
- 检查API配额（如OpenAI API）
- 查看具体期数的错误日志
- 确保有足够的未使用图片

### 图片重复使用

- 检查 `asset_usage_index.json` 是否正确更新
- 检查图片库是否有足够的图片
- 查看封面生成日志

## 相关文档

- [频道制播流程技术规范](./CHANNEL_PRODUCTION_SPEC.md)
- [批量制播管理前端架构设计](./BATCH_PRODUCTION_UI_DESIGN.md)


