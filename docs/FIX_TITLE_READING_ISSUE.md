# 🔧 修复标题读取问题

## ❌ 问题描述

上传视频时使用了错误的标题：
- **错误标题**: `Kat Records Lo-Fi Mix - 20260201`（默认值）
- **正确标题**: `Whispers of Evening Rainlight Vinyl | Kat Records Presents Echoes of Solitude & Liquid Reflections`
- **标题文件**: `channels/kat/output/kat_20260201/kat_20260201_youtube_title.txt`

## 🔍 根本原因

`read_metadata_files` 函数无法正确读取标题文件，因为：

1. **episode_id 格式不匹配**：
   - 上传脚本使用 `--episode 20260201`（日期格式）
   - 但实际文件名是 `kat_20260201_youtube_title.txt`（完整格式）

2. **文件查找逻辑**：
   - 函数只查找 `{episode_id}_youtube_title.txt` 格式
   - 当 `episode_id = "20260201"` 时，查找 `20260201_youtube_title.txt`
   - 但实际文件是 `kat_20260201_youtube_title.txt`，因此找不到

## ✅ 修复方案

修改了 `scripts/uploader/upload_to_youtube.py` 中的 `read_metadata_files` 函数：

### 1. 自动推断完整的 episode_id 格式

从视频文件路径自动推断完整的 episode_id：
- 如果 `episode_id = "20260201"`（日期格式）
- 视频文件在 `channels/kat/output/kat_20260201/kat_20260201_youtube.mp4`
- 则推断出 `inferred_episode_id = "kat_20260201"`

### 2. 支持两种格式的文件查找

查找元数据文件时，同时尝试两种格式：
- `{inferred_episode_id}_youtube_title.txt`（完整格式，优先）
- `{episode_id}_youtube_title.txt`（日期格式，备用）

### 3. 修复的文件类型

- ✅ 标题文件：`*_youtube_title.txt`
- ✅ 描述文件：`*_youtube_description.txt`
- ✅ 字幕文件：`*_youtube.srt`
- ✅ 缩略图文件：`*_cover.png`

## 🧪 测试结果

修复后测试：

```python
episode_id = '20260201'  # 日期格式
video_file = Path('channels/kat/output/kat_20260201/kat_20260201_youtube.mp4')
metadata = read_metadata_files(episode_id, video_file)

# ✅ 结果：成功读取正确的标题
# 标题: Whispers of Evening Rainlight Vinyl | Kat Records Presents Echoes of Solitude & Liquid Reflections
```

## 📝 修改的文件

- `scripts/uploader/upload_to_youtube.py`
  - 修改了 `read_metadata_files` 函数
  - 添加了 `inferred_episode_id` 推断逻辑
  - 更新了所有元数据文件的查找逻辑

## 🎯 预期效果

修复后，上传脚本能够：
1. ✅ 正确读取标题文件（从 `kat_20260201_youtube_title.txt`）
2. ✅ 正确读取描述文件（从 `kat_20260201_youtube_description.txt`）
3. ✅ 正确读取字幕文件（从 `kat_20260201_youtube.srt`）
4. ✅ 正确读取缩略图文件（从 `kat_20260201_cover.png`）

## 🔄 下一步

1. **重新授权OAuth**（使用正确的账号）：
   ```bash
   python3 scripts/reauthorize_kat_records_studio.py
   ```

2. **重新上传视频**（使用正确的标题和账号）：
   ```bash
   python3 scripts/uploader/upload_to_youtube.py \
       --episode 20260201 \
       --video channels/kat/output/kat_20260201/kat_20260201_youtube.mp4
   ```

## 📋 相关文档

- `docs/FIX_WRONG_ACCOUNT_UPLOAD.md` - 账号错误修复指南
- `docs/YOUTUBE_UPLOAD_MODULES_COMPLETE_ANALYSIS.md` - 上传模块完整分析
