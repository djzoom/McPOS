# 异步函数迁移待办事项

## 问题1：13-16期第三条进度条修复 ✅

**问题**：刷新后，13-16期节目的第三条进度条消失。

**原因**：刷新后 `runbookState` 可能丢失，导致 `isDeliveryReady` 为 false，第三条进度条不显示。

**修复**：在 `calculateStageStatus` 中添加了基于资产状态的判断：
- 如果 `renderDone && !uploadDone && !hasUploadHistory`，显示第三条进度条为 inProgress
- 这确保即使 `runbookState` 丢失，也能正确显示第三条进度条

## 问题2：应改为异步的重要同步函数

### 高优先级（文件I/O操作，频繁调用）

1. **`sync_episode_assets_from_filesystem`** (`render_queue_sync.py:30`)
   - **原因**：执行大量文件系统操作（检查文件存在、读取文件等）
   - **调用位置**：
     - `check_episode_assets_status` (auto_complete_episodes.py:44)
     - `sync_all_episodes_assets` (render_queue_sync.py:223)
     - `episodes.py` 路由中多次调用
   - **影响**：在API请求中阻塞，影响响应时间
   - **建议**：改为 `async def sync_episode_assets_from_filesystem`，使用 `async_file_exists` 等异步文件操作

2. **`check_episode_assets_status`** (`auto_complete_episodes.py:22`)
   - **原因**：调用了 `sync_episode_assets_from_filesystem`
   - **调用位置**：
     - `auto_complete_episode` (auto_complete_episodes.py:147)
     - `auto_complete_episodes_range` (间接调用)
   - **影响**：阻塞自动完成流程
   - **建议**：改为 `async def check_episode_assets_status`

3. **`load_manifest`** (`manifest.py:51`)
   - **原因**：文件I/O操作（读取JSON文件）
   - **调用位置**：`plan.py` 路由中多次调用（20次）
   - **影响**：在计划执行流程中阻塞
   - **建议**：改为 `async def load_manifest`，使用 `async_read_json`

4. **`save_manifest`** (`manifest.py:74`)
   - **原因**：文件I/O操作（写入JSON文件）
   - **调用位置**：`plan.py` 和 `upload.py` 路由中调用
   - **影响**：在计划执行和上传流程中阻塞
   - **建议**：改为 `async def save_manifest`，使用 `async_write_json`

### 中优先级（可能涉及外部调用）

5. **`check_video_completion`** (`video_completion_checker.py`)
   - **原因**：可能调用 `ffprobe` 等外部工具
   - **调用位置**：`sync_episode_assets_from_filesystem` (render_queue_sync.py:116)
   - **影响**：在资产同步时阻塞
   - **建议**：改为 `async def check_video_completion`，使用 `asyncio.create_subprocess_exec` 调用 ffprobe

6. **`get_uploaded_episodes_assets`** (`cleanup_service.py:279`)
   - **原因**：可能涉及文件系统扫描
   - **调用位置**：清理服务中调用
   - **影响**：在清理流程中阻塞
   - **建议**：检查是否涉及文件I/O，如果是则改为异步

### 低优先级（纯计算或配置读取）

7. **`get_channel_config`** (`channel_config.py:75`)
   - **原因**：读取配置文件，但通常只调用一次
   - **建议**：如果频繁调用，考虑改为异步

8. **`build_episode_model_from_schedule`** (`episode_flow_helper.py:34`)
   - **原因**：纯数据转换，无I/O操作
   - **建议**：保持同步即可

## 迁移建议

1. **优先迁移**：`sync_episode_assets_from_filesystem` 和 `check_episode_assets_status`
   - 这两个函数在API请求中被频繁调用
   - 迁移后可以显著提升API响应速度

2. **使用异步文件操作工具**：
   - `async_file_exists` (from `utils.async_file_ops`)
   - `async_read_json` (from `utils.async_file_ops`)
   - `async_write_json` (from `utils.async_file_ops`)

3. **保持向后兼容**：
   - 可以保留同步版本作为 `_sync` 后缀
   - 或者使用 `asyncio.run()` 在需要时调用异步版本

4. **测试重点**：
   - API响应时间
   - 并发请求处理能力
   - 文件操作的原子性

