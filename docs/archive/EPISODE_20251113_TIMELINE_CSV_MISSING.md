# 20251113 节目 Timeline CSV 文件缺失问题分析

## 问题描述

20251113 节目的 MP3 音频文件已合成完成（`20251113_full_mix.mp3` 存在），但是缺少第 10 个文件 `20251113_full_mix_timeline.csv`，导致抽屉显示"合成中"。

## 日志分析

### Timeline CSV 生成日志

**时间线**：
- `20:30:16` - 开始生成 timeline CSV
- `20:30:16` - 从 playlist 读取了 43 个 timeline 事件
- `20:30:16` - 过滤后得到 21 个 clean timeline 事件
- `20:30:16` - 写入 timeline CSV 文件
- `20:30:16` - ✅ 生成成功：`20251113_full_mix_timeline.csv (21 events, 652 bytes)`
- `20:30:16` - 更新 schedule：`Updated assets.timeline_csv for episode 20251113`

**关键日志**：
```
[2025-11-12 20:30:16] [INFO] Writing timeline CSV to /Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251113/20251113_full_mix_timeline.csv
[2025-11-12 20:30:16] [INFO] ✅ Generated timeline CSV: /Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251113/20251113_full_mix_timeline.csv (21 events, 652 bytes)
[2025-11-12 20:30:16] [INFO] Updated assets.timeline_csv for episode 20251113: /Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251113/20251113_full_mix_timeline.csv
```

### 文件系统检查

**实际文件列表**：
```
channels/kat_lofi/output/20251113/
├── 20251113_cover.png
├── 20251113_full_mix.mp3          ✅ 存在
├── 20251113_manifest.json
├── 20251113_youtube.srt
├── 20251113_youtube_description.txt
├── 20251113_youtube_tags.txt
├── 20251113_youtube_title.txt
├── playlist.csv
└── playlist_metadata.json
```

**缺失文件**：
- ❌ `20251113_full_mix_timeline.csv` - **不存在**

## 问题分析

### 可能的原因

1. **文件写入失败但未抛出异常**
   - 代码中使用了 `with timeline_csv_path.open("w", ...)` 写入文件
   - 如果写入失败，应该会抛出异常
   - 但日志显示"✅ Generated timeline CSV"，说明写入时没有异常

2. **文件写入后又被删除**
   - 没有找到删除 timeline CSV 的代码
   - 但可能有其他清理逻辑删除了文件

3. **文件写入到错误的位置**
   - 代码中使用 `episode_output_dir / f"{episode_id}_full_mix_timeline.csv"`
   - 路径应该是正确的：`channels/kat_lofi/output/20251113/20251113_full_mix_timeline.csv`

4. **文件系统同步问题**
   - 文件写入后，文件系统可能没有立即同步
   - 但日志显示文件已生成，说明写入应该已完成

5. **文件写入后检查失败**
   - 代码中有检查：`if not timeline_csv_path.exists()`
   - 如果检查失败，应该会抛出 `FileNotFoundError`
   - 但日志显示检查通过

### 代码逻辑分析

**文件写入代码** (`plan.py:1345-1370`):
```python
# Write timeline CSV (English format for SRT/description)
logger.info(f"Writing timeline CSV to {timeline_csv_path}")
with timeline_csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Timecode", "Track Name", "Side"])
    for event in clean_timeline_events:
        timestamp = event.get("timestamp", "")
        description = event.get("description", "")
        side = event.get("side", "")
        if timestamp and description:
            writer.writerow([timestamp, description, side])

# Verify timeline CSV file was created and is not empty
if not timeline_csv_path.exists():
    raise FileNotFoundError(f"Timeline CSV file was not created: {timeline_csv_path}")

# Check file size (should be at least header size)
file_size = timeline_csv_path.stat().st_size
if file_size == 0:
    logger.warning(f"Timeline CSV file is empty: {timeline_csv_path}")
elif file_size < 20:
    logger.warning(f"Timeline CSV file is suspiciously small ({file_size} bytes): {timeline_csv_path}")

timeline_generated = True
logger.info(f"✅ Generated timeline CSV: {timeline_csv_path} ({len(clean_timeline_events)} events, {file_size} bytes)")
```

**问题**：
- 代码逻辑看起来是正确的
- 文件写入后立即检查存在性
- 如果文件不存在，应该会抛出异常
- 但日志显示文件已生成，说明检查通过

## 修复建议

### 1. 增强文件写入的可靠性

**问题**：文件写入可能在某些情况下失败，但没有被正确检测到

**修复方案**：
- 在文件写入后，使用 `flush()` 和 `sync()` 确保数据写入磁盘
- 添加重试机制，如果写入失败，重试几次
- 在写入后立即读取文件内容，验证写入成功

### 2. 添加文件持久化验证

**问题**：文件写入后可能被删除或移动

**修复方案**：
- 在写入后，等待一小段时间（例如 100ms），再次检查文件是否存在
- 如果文件不存在，重新生成
- 记录文件写入和检查的时间戳，便于调试

### 3. 改进错误处理

**问题**：文件写入失败可能被静默忽略

**修复方案**：
- 确保所有文件写入操作都有异常处理
- 如果写入失败，记录详细错误信息
- 不要静默忽略错误，应该抛出异常或记录警告

### 4. 添加文件完整性检查

**问题**：文件可能被部分写入或损坏

**修复方案**：
- 在写入后，验证文件大小是否符合预期
- 读取文件内容，验证格式是否正确
- 如果文件不完整，重新生成

## 临时解决方案

### 手动重新生成 Timeline CSV

如果文件确实缺失，可以：

1. **从 playlist.csv 重新生成**：
   - 读取 `playlist.csv` 文件
   - 提取 Timeline 事件
   - 生成 `20251113_full_mix_timeline.csv` 文件

2. **触发 remix 阶段重新执行**：
   - 删除 `20251113_full_mix.mp3` 文件（或移动到备份位置）
   - 重新触发 remix 阶段
   - 系统会重新生成 MP3 和 timeline CSV

## 相关代码位置

- `kat_rec_web/backend/t2r/routes/plan.py:1295-1370` - Timeline CSV 生成逻辑
- `kat_rec_web/backend/t2r/routes/plan.py:1401-1407` - Timeline CSV 路径更新到 schedule
- `kat_rec_web/backend/t2r/routes/plan.py:1442-1470` - Remix 完成事件广播（需要 timeline CSV 存在）

## 更新日期

2025-01-XX

