# Episode 20251114 Timeline CSV 缺失问题分析

## 问题描述

Episode 20251114 在 mix mp3 音频文件之后没有输出 mix timeline CSV，导致：
1. 抽屉显示"合成中"（因为 timeline CSV 缺失）
2. 无法进入渲染队列（因为渲染队列需要所有 prerequisites 都满足）

## 日志分析

### 第一次 remix (16:19:43)
- ✅ 成功生成 timeline CSV
- ✅ 日志显示：`✅ Generated timeline CSV: ... (24 events, 804 bytes)`
- ✅ 更新了 `assets.timeline_csv`

### 第二次 remix (20:47:24)
- ✅ 成功生成 timeline CSV
- ✅ 日志显示：`✅ Generated timeline CSV: ... (23 events, 761 bytes)`
- ✅ 更新了 `assets.timeline_csv`

### 第三次 remix (21:16:10)
- ❌ **没有生成 timeline CSV**
- ❌ 日志显示：`Timeline CSV not found for 20251114, remix may not be fully complete. Will not broadcast completion.`
- ❌ **没有** "Reading playlist from ... to generate timeline CSV" 的日志
- ❌ **没有** "Writing timeline CSV to ..." 的日志
- ❌ **没有** "✅ Generated timeline CSV" 的日志

## 问题分析

### 可能的原因

1. **Timeline CSV 生成代码没有被执行**
   - 代码在 `plan.py` 的 `_execute_stage_core` 函数中（第 1295-1406 行）
   - 如果 playlist_path 不存在或不可读，会抛出 `FileNotFoundError` 或 `PermissionError`
   - 但这些错误会被捕获，并记录警告日志
   - **但第三次 remix 时没有任何错误日志**

2. **Timeline CSV 生成被跳过**
   - 可能因为某种条件判断导致代码没有执行到 timeline CSV 生成部分
   - 需要检查是否有提前返回的逻辑

3. **文件写入失败但错误被吞掉**
   - 虽然代码中有错误处理，但可能某些异常没有被正确记录

## 渲染队列入队条件

### 当前判断依据

根据 `kat_rec_web/backend/t2r/utils/path_helpers.py` 的 `validate_render_prerequisites` 函数：

**必需文件**：
1. ✅ `{episode_id}_cover.png` - 封面
2. ✅ `{episode_id}_full_mix.mp3` - 音频
3. ✅ `{episode_id}_youtube_title.txt` - 标题
4. ✅ `{episode_id}_youtube_description.txt` - 描述
5. ✅ `{episode_id}_youtube.srt` - 字幕

**注意**：`timeline CSV` **不在**渲染队列的必需文件列表中！

### 自动化入队逻辑

根据 `kat_rec_web/backend/t2r/services/channel_automation.py` 的 `_process_automation_job` 函数：

```python
# Phase 3: Auto-enqueue for rendering after remix completes
is_valid, missing_files = await async_validate_render_prerequisites(
    channel_id=channel_id,
    episode_id=episode_id,
    episode_output_dir=episode_output_dir
)

if is_valid:
    queued = await enqueue_render_job(channel_id, episode_id)
```

**问题**：如果 timeline CSV 缺失，但其他文件都存在，系统仍然会尝试入队。但 timeline CSV 缺失会导致：
1. 前端显示"合成中"（因为 `hasAudio` 需要 timeline CSV）
2. 可能影响后续的 SRT/description 生成

## 解决方案

### 1. 修复 timeline CSV 生成问题

需要检查为什么第三次 remix 时 timeline CSV 生成代码没有被执行。可能的原因：
- playlist_path 路径问题
- 异常被捕获但没有记录
- 代码逻辑有提前返回

### 2. 增强错误日志

在 timeline CSV 生成代码中添加更详细的日志，确保所有执行路径都有日志记录。

### 3. 检查文件是否存在

在 remix 完成后，验证 timeline CSV 文件是否真的存在，如果不存在则抛出错误。

## 当前状态

- ✅ MP3 文件已生成：`20251114_full_mix.mp3` (84.5 MB)
- ❌ Timeline CSV 文件缺失：`20251114_full_mix_timeline.csv`
- ✅ 其他文件都存在：cover, title, description, captions, tags
- ❌ 无法进入渲染队列（因为前端判断 `hasAudio` 需要 timeline CSV）

## 下一步

1. 检查第三次 remix 的完整日志，找出为什么 timeline CSV 生成代码没有被执行
2. 手动生成 timeline CSV（如果需要）
3. 修复 timeline CSV 生成逻辑，确保每次 remix 都能成功生成

