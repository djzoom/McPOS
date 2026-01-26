# 20251112 节目资产缺失问题分析

## 问题描述

20251112 节目的资产文件夹中缺少：
1. **Playlist 3 个文件**：`playlist.csv`, `playlist_metadata.json`, `20251112_manifest.json`
2. **封面文件**：`20251112_cover.png`

同时，description 中包含歌单信息，需要确认来源。

## 日志分析

### 1. Playlist 文件生成流程

**时间线**：
- `16:01:14` - 创建输出目录
- `16:01:14` - 第一次调用 `init_episode`，生成了 `playlist.csv`
- `16:01:22` - 第二次调用 `init_episode`，发现 `playlist.csv` 已存在，**跳过了生成**
- `16:07:04` - 自动化队列开始处理，调用 `_init_episode`，发现 playlist 已存在，**跳过了生成**

**关键日志**：
```
[2025-11-12 16:01:22] [INFO] Found existing playlist for 20251112: /Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251112/playlist.csv
[2025-11-12 16:01:22] [INFO] [init_episode] Completed for 20251112 in 0.00s: status=ok, errors=0
```

**问题根源**：
- `init_episode` 在发现 `playlist.csv` 已存在时，会跳过 `generate_playlist` 调用
- 但是 `generate_playlist` 不仅生成 `playlist.csv`，还会生成 `playlist_metadata.json`
- 由于跳过了 `generate_playlist`，`playlist_metadata.json` 没有被生成

### 2. Manifest 文件生成流程

**代码位置**：`kat_rec_web/backend/t2r/routes/plan.py:461-465`

```python
# Create or load manifest
manifest = load_manifest(request.channel_id, request.episode_id)
if not manifest:
    manifest = create_manifest(request.channel_id, request.episode_id)
    update_manifest_status(request.channel_id, request.episode_id, ManifestStatus.PLANNING)
```

**Manifest 保存位置**：`kat_rec_web/backend/t2r/services/manifest.py:34-48`

```python
def get_manifest_path(channel_id: str, episode_id: str) -> Path:
    output_dir = get_output_dir(channel_id)
    episode_dir = output_dir / episode_id
    return episode_dir / f"{episode_id}_manifest.json"
```

**问题分析**：
- `create_manifest` 会调用 `save_manifest` 保存文件
- 但是日志中没有看到 manifest 文件生成的记录
- 可能的原因：
  1. manifest 已存在，所以跳过了创建
  2. manifest 创建失败，但没有记录错误
  3. manifest 文件被删除或移动

### 3. 封面文件生成流程

**日志显示**：
```
[2025-11-12 16:07:11] [INFO] Cover generated successfully: /Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251112/20251112_cover.png
[2025-11-12 20:49:33] [INFO] Cover generated successfully: /Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251112/20251112_cover.png
[2025-11-12 20:49:33] [ERROR] Failed to generate cover: Cover file was not created: /Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251112/20251112_cover.png
```

**问题分析**：
- 封面生成成功，但随后检查时文件不存在
- 可能的原因：
  1. 文件写入时序问题（异步写入未完成）
  2. 文件被删除或移动
  3. 文件路径错误

### 4. Description 中的歌单来源

**代码位置**：`kat_rec_web/backend/t2r/routes/automation.py:2822-2834`

```python
# 解析 playlist (使用缓存的异步检查)
playlist_data = None
if playlist_path and await file_cache.async_file_exists_cached(playlist_path):
    try:
        playlist_data = await async_parse_playlist(playlist_path)
        logger.info(f"成功解析 playlist: {playlist_path}")
    except Exception as e:
        error_msg = f"解析 playlist 失败: {e}"
        results["errors"].append(error_msg)
```

**歌单信息使用**：
- `_filler_generate_title_desc_srt_tags` 函数会解析 `playlist.csv` 来获取歌单信息
- 使用 `format_tracklist` 函数将歌单格式化为描述文本
- 即使 `playlist_metadata.json` 不存在，只要 `playlist.csv` 存在，就能解析出歌单信息

## 问题总结

### 缺失文件的原因

1. **`playlist_metadata.json`**：
   - `init_episode` 发现 `playlist.csv` 已存在，跳过了 `generate_playlist` 调用
   - `generate_playlist` 会生成 `playlist_metadata.json`，但由于被跳过，文件未生成

2. **`20251112_manifest.json`**：
   - `create_manifest` 应该会保存文件，但可能：
     - 文件已存在（但实际不存在）
     - 保存失败但没有记录错误
     - 文件被删除

3. **`20251112_cover.png`**：
   - 封面生成成功，但文件检查时不存在
   - 可能是文件写入时序问题或文件被删除

### Description 中的歌单来源

- Description 中的歌单信息来自 `playlist.csv` 文件
- 即使 `playlist_metadata.json` 不存在，只要 `playlist.csv` 存在，就能解析出歌单信息
- `async_parse_playlist` 函数会读取 CSV 文件并解析出曲目列表

## 修复建议

### 1. 修复 `init_episode` 的 idempotency 逻辑

**问题**：当 `playlist.csv` 已存在时，跳过了 `generate_playlist`，导致 `playlist_metadata.json` 未生成

**修复方案**：
- 检查 `playlist_metadata.json` 是否存在
- 如果 `playlist.csv` 存在但 `playlist_metadata.json` 不存在，仍然调用 `generate_playlist`（或只生成 metadata）

### 2. 修复封面文件检查逻辑

**问题**：封面生成成功，但文件检查时不存在

**修复方案**：
- 在生成封面后，等待文件写入完成
- 使用文件系统事件或轮询检查文件是否存在
- 添加重试机制

### 3. 确保 manifest 文件生成

**问题**：manifest 文件可能未生成

**修复方案**：
- 在 `init_episode` 中，确保 `create_manifest` 后文件确实被保存
- 添加文件存在性检查
- 如果文件不存在，重新创建

## 相关代码位置

- `kat_rec_web/backend/t2r/routes/plan.py:522-618` - `init_episode` 的 playlist 处理逻辑
- `kat_rec_web/backend/t2r/routes/automation.py:1570` - `playlist_metadata.json` 的生成
- `kat_rec_web/backend/t2r/services/manifest.py:107-132` - `create_manifest` 的实现
- `kat_rec_web/backend/t2r/routes/automation.py:2822-2834` - Description 中歌单信息的解析

## 更新日期

2025-01-XX

