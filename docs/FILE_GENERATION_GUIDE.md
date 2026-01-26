# 文件生成完整指南

**最后更新**: 2025-01-XX

---

## 📋 概述

本指南说明如何确保所有 episode 文件夹中的所有必需文件都被正确生成。

---

## 🎯 必需文件列表

### 阶段 1: 初始化 (init_episode)
- `{episode_id}_manifest.json` - 期数清单文件
- `playlist_metadata.json` - 播放列表元数据
- `playlist.csv` - 播放列表 CSV

### 阶段 2: 准备阶段 (preparation)
- `{episode_id}_cover.png` - 封面图片
- `{episode_id}_youtube_title.txt` - YouTube 标题
- `{episode_id}_youtube_description.txt` - YouTube 描述
- `{episode_id}_youtube.srt` - YouTube 字幕
- `{episode_id}_youtube_tags.txt` - YouTube 标签

### 阶段 3: 混音 (remix)
- `{episode_id}_full_mix.mp3` - 完整混音音频
- `{episode_id}_full_mix_timeline.csv` - 时间线 CSV

### 阶段 4: 渲染 (render)
- `{episode_id}_youtube.mp4` - YouTube 视频

---

## 🔧 工具使用

### 1. 检查单个 Episode

```bash
# 检查单个 episode 的所有文件
python scripts/ensure_all_files_generated.py \
  --channel kat_lofi \
  --episode 20251112

# 检查单个 episode 的特定阶段
python scripts/ensure_all_files_generated.py \
  --channel kat_lofi \
  --episode 20251112 \
  --stage preparation

# 检查并自动触发生成缺失的文件
python scripts/ensure_all_files_generated.py \
  --channel kat_lofi \
  --episode 20251112 \
  --auto-generate
```

### 2. 检查所有 Episode

```bash
# 检查所有 episode
python scripts/ensure_all_files_generated.py \
  --channel kat_lofi \
  --all

# 检查所有 episode 并自动生成缺失的文件
python scripts/ensure_all_files_generated.py \
  --channel kat_lofi \
  --all \
  --auto-generate

# 详细输出
python scripts/ensure_all_files_generated.py \
  --channel kat_lofi \
  --all \
  --verbose
```

### 3. 其他验证工具

#### 诊断生成流程
```bash
python scripts/diagnose_episode_generation.py 20251112 --channel kat_lofi
```

#### 验证资产完整性
```bash
python scripts/verify_episode_assets.py \
  --channel kat_lofi \
  --episode 20251112 \
  --verbose
```

---

## 🚀 自动生成流程

### 手动触发生成

#### 1. 初始化 Episode
```bash
# 通过 API
curl -X POST http://localhost:8080/api/t2r/init-episode \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251112",
    "channel_id": "kat_lofi",
    "avoid_duplicates": true,
    "seo_template": true
  }'
```

#### 2. 生成资产
```bash
# 生成封面
curl -X POST http://localhost:8080/api/t2r/regenerate-asset \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251112",
    "channel_id": "kat_lofi",
    "asset_type": "cover"
  }'

# 生成标题
curl -X POST http://localhost:8080/api/t2r/regenerate-asset \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251112",
    "channel_id": "kat_lofi",
    "asset_type": "title"
  }'
```

#### 3. 运行混音
```bash
curl -X POST http://localhost:8080/api/t2r/run \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251112",
    "channel_id": "kat_lofi",
    "stages": ["remix"]
  }'
```

#### 4. 运行渲染
```bash
curl -X POST http://localhost:8080/api/t2r/run \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251112",
    "channel_id": "kat_lofi",
    "stages": ["render"]
  }'
```

---

## 📊 文件生成顺序

```
1. init_episode
   ├── manifest.json
   ├── playlist_metadata.json
   └── playlist.csv

2. preparation (并行)
   ├── cover.png
   ├── youtube_title.txt
   ├── youtube_description.txt
   ├── youtube.srt
   └── youtube_tags.txt

3. remix (串行)
   ├── full_mix.mp3
   └── full_mix_timeline.csv

4. render (串行)
   └── youtube.mp4
```

---

## ⚠️ 常见问题

### 问题 1: 文件未生成

**可能原因**:
- 前置阶段未完成
- 任务执行失败但错误被吞掉
- 文件生成到错误的位置

**解决方法**:
1. 检查日志: `grep '[PARALLEL]' logs/backend.log | grep {episode_id}`
2. 检查任务状态: 查看 WebSocket 消息
3. 使用诊断工具: `python scripts/diagnose_episode_generation.py {episode_id}`

### 问题 2: 部分文件缺失

**解决方法**:
1. 使用验证工具检查: `python scripts/verify_episode_assets.py --channel {channel} --episode {episode_id}`
2. 使用自动生成工具: `python scripts/ensure_all_files_generated.py --channel {channel} --episode {episode_id} --auto-generate`

### 问题 3: 文件生成顺序错误

**解决方法**:
- 确保按顺序执行: init → preparation → remix → render
- 使用自动化工作流，它会自动处理依赖关系

---

## 🔍 验证检查清单

- [ ] 所有必需文件都存在
- [ ] 文件大小合理（不为 0）
- [ ] 文件时间戳正确
- [ ] 文件内容有效（可以打开/解析）
- [ ] 所有阶段都已完成

---

## 📝 相关文档

- [工作流和自动化指南](./02_WORKFLOW_AND_AUTOMATION.md)
- [上传管道 v2 架构](./ARCHITECTURE_UPLOAD_V2.md)
- [验证管道 v2 架构](./ARCHITECTURE_VERIFY_V2.md)

---

## 🛠️ 维护建议

1. **定期检查**: 每周运行一次完整检查
   ```bash
   python scripts/ensure_all_files_generated.py --channel kat_lofi --all
   ```

2. **自动化**: 设置定时任务自动检查并生成缺失文件
   ```bash
   # 添加到 crontab
   0 2 * * * cd /path/to/Kat_Rec && python scripts/ensure_all_files_generated.py --channel kat_lofi --all --auto-generate
   ```

3. **监控**: 监控日志文件，及时发现生成失败

---

**最后更新**: 2025-01-XX

