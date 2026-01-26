# 资产生成流程分析与阻塞点检查

## 资产生成流程概览

### 完整流程

```
1. 创建排播 (create_episode)
   ↓
2. 自动化队列 (channel_automation.enqueue_episode)
   ↓
3. Phase 1: 并行准备 (channel_automation._prepare_episode_parallel)
   ├─ init_episode (playlist + recipe)
   ├─ 文本资产生成 (title, description, captions, tags)
   └─ 封面生成 (cover)
   ↓
4. Phase 2: 串行 Remix (channel_automation._run_remix_stage)
   ├─ 使用 FFmpeg 队列 (plan.py 内部队列)
   ├─ 生成 full_mix.mp3
   └─ 生成 full_mix_timeline.csv
   ↓
5. Phase 3: 自动加入渲染队列 (render_queue.enqueue_render_job)
   ↓
6. 渲染队列处理 (render_queue._process_job)
   ├─ 等待前置条件 (最多5分钟)
   ├─ 执行渲染 (plan._execute_stage with _skip_queue=True)
   └─ 生成 render_complete_flag
   ↓
7. 上传和发布 (render_queue._process_job 继续)
   ├─ 上传到 YouTube
   └─ 验证
```

## 阻塞点分析

### 1. 锁竞争阻塞

#### 1.1 `_STATE_LOCK` (channel_automation.py)
- **位置**: `kat_rec_web/backend/t2r/services/channel_automation.py:63`
- **用途**: 保护 `_CHANNEL_STATES` 字典
- **超时**: 5秒 (`asyncio.wait_for(_STATE_LOCK.acquire(), timeout=5.0)`)
- **风险**: 
  - 如果 worker 在处理任务时崩溃，锁可能不会被释放
  - 多个频道同时操作可能导致锁竞争
- **当前保护**: ✅ 有超时机制，超时后抛出 `RuntimeError`

#### 1.2 `_LOCK` (render_queue.py)
- **位置**: `kat_rec_web/backend/t2r/services/render_queue.py:49`
- **用途**: 保护 `_STATE` (渲染队列状态)
- **超时**: ❌ 无超时机制
- **风险**: 
  - 如果 worker 崩溃，锁可能永久持有
  - 可能导致后续任务无法入队
- **建议**: 添加超时机制或使用 `asyncio.wait_for`

#### 1.3 `_queue_lock` (plan.py)
- **位置**: `kat_rec_web/backend/t2r/routes/plan.py:742, 806`
- **用途**: 保护 FFmpeg 队列状态
- **超时**: ❌ 无超时机制
- **风险**: 
  - 如果 worker 崩溃，锁可能永久持有
  - 可能导致后续 remix/render 任务无法执行
- **建议**: 添加超时机制

### 2. 信号量限制阻塞

#### 2.1 `_LARGE_FILE_SEMAPHORE` (channel_automation.py)
- **位置**: `kat_rec_web/backend/t2r/services/channel_automation.py:69`
- **限制**: 4 个并发
- **用途**: 限制 remix 和 render 的并发数
- **风险**: 
  - 如果 4 个任务都在等待，新任务会阻塞
  - 如果某个任务卡住，会占用一个槽位
- **当前保护**: ✅ 有超时机制（PARALLEL_TASKS_TIMEOUT = 300秒）

#### 2.2 `_SMALL_FILE_SEMAPHORE` (channel_automation.py)
- **位置**: `kat_rec_web/backend/t2r/services/channel_automation.py:67`
- **限制**: 100 个并发
- **用途**: 限制小文件操作（playlist, text, cover）的并发数
- **风险**: 低（限制很高）

### 3. 队列等待阻塞

#### 3.1 `job_done.wait()` (plan.py)
- **位置**: `kat_rec_web/backend/t2r/routes/plan.py:827`
- **用途**: 等待 FFmpeg 任务完成
- **超时**: ❌ 无超时机制
- **风险**: 
  - 如果 worker 崩溃，`job_done` 永远不会被设置
  - 调用者会永久阻塞
- **建议**: 添加超时机制

#### 3.2 `_queue.get()` (plan.py)
- **位置**: `kat_rec_web/backend/t2r/routes/plan.py:747`
- **用途**: 从 FFmpeg 队列获取任务
- **超时**: ❌ 无超时机制（但 worker 会检查队列是否为空）
- **风险**: 低（worker 有退出机制）

### 4. 前置条件等待阻塞

#### 4.1 渲染队列等待前置条件 (render_queue.py)
- **位置**: `kat_rec_web/backend/t2r/services/render_queue.py:156-176`
- **超时**: 300秒（5分钟）
- **检查间隔**: 2秒
- **风险**: 
  - 如果前置条件永远不满足，会等待5分钟后失败
  - 这是预期的行为，但可能影响用户体验
- **当前保护**: ✅ 有超时机制

#### 4.2 文件等待 (file_watcher.py)
- **位置**: `kat_rec_web/backend/t2r/utils/file_watcher.py:59`
- **超时**: 可配置（默认10秒）
- **风险**: 
  - 如果文件永远不生成，会超时
  - 这是预期的行为
- **当前保护**: ✅ 有超时机制

### 5. 并行任务超时阻塞

#### 5.1 Phase 1 并行任务超时 (channel_automation.py)
- **位置**: `kat_rec_web/backend/t2r/services/channel_automation.py:623`
- **超时**: 300秒（5分钟）
- **用途**: 限制并行准备阶段的总时间
- **风险**: 
  - 如果某个任务卡住，整个阶段会超时
  - 可能导致部分任务未完成
- **当前保护**: ✅ 有超时机制

## 潜在死锁场景

### 场景 1: Worker 崩溃导致锁未释放

**问题**: 
- Worker 在处理任务时崩溃，锁没有被释放
- 后续任务无法获取锁，永久阻塞

**影响范围**:
- `_STATE_LOCK`: ✅ 有超时保护
- `_LOCK`: ❌ 无超时保护
- `_queue_lock`: ❌ 无超时保护

**建议**: 为所有锁添加超时机制

### 场景 2: job_done 事件未设置

**问题**: 
- FFmpeg worker 崩溃，`job_done.set()` 从未被调用
- `_execute_stage` 中的 `job_done.wait()` 永久阻塞

**影响范围**: 
- 所有通过 `_execute_stage` 调用的 remix/render 任务

**建议**: 添加超时机制

### 场景 3: 信号量槽位被占用

**问题**: 
- 某个 remix/render 任务卡住，占用 `_LARGE_FILE_SEMAPHORE` 槽位
- 其他任务无法获取信号量，永久阻塞

**影响范围**: 
- 最多影响 4 个并发任务（信号量限制）

**建议**: 
- 添加任务级别的超时
- 定期检查任务状态，超时后释放信号量

## 改进建议

### 优先级 1: 关键阻塞点修复

1. **为 `_LOCK` 添加超时机制** (render_queue.py)
   ```python
   try:
       await asyncio.wait_for(_LOCK.acquire(), timeout=5.0)
   except asyncio.TimeoutError:
       logger.error("[render-queue] Timeout acquiring lock")
       raise RuntimeError("Failed to acquire render queue lock")
   ```

2. **为 `_queue_lock` 添加超时机制** (plan.py)
   ```python
   try:
       async with asyncio.wait_for(_queue_lock, timeout=5.0):
           # ...
   except asyncio.TimeoutError:
       logger.error("[plan] Timeout acquiring queue lock")
       raise RuntimeError("Failed to acquire queue lock")
   ```

3. **为 `job_done.wait()` 添加超时机制** (plan.py)
   ```python
   try:
       await asyncio.wait_for(job_done.wait(), timeout=3600)  # 1小时超时
   except asyncio.TimeoutError:
       logger.error(f"[plan] Timeout waiting for job {job_number} to complete")
       raise RuntimeError(f"Job {job_number} did not complete within timeout")
   ```

### 优先级 2: 任务级别超时

4. **为 remix/render 任务添加超时**
   - 在 `_execute_stage_core` 中包装 FFmpeg 调用
   - 设置合理的超时（例如：30分钟）

5. **定期检查任务状态**
   - 在 worker 中定期检查任务是否还在运行
   - 如果超时，取消任务并释放资源

### 优先级 3: 监控和恢复

6. **添加健康检查**
   - 定期检查 worker 是否还在运行
   - 如果 worker 崩溃，自动重启

7. **添加任务恢复机制**
   - 记录任务状态
   - 如果任务失败，可以手动或自动重试

## 当前流程的健康检查

### ✅ 已有保护机制

1. **锁超时**: `_STATE_LOCK` 有5秒超时
2. **任务超时**: Phase 1 并行任务有300秒超时
3. **前置条件超时**: 渲染队列等待有300秒超时
4. **文件等待超时**: 文件等待有可配置超时

### ❌ 缺少保护机制

1. **`_LOCK` 无超时**: render_queue 的全局锁
2. **`_queue_lock` 无超时**: plan.py 的队列锁
3. **`job_done.wait()` 无超时**: 等待 FFmpeg 任务完成
4. **任务级别超时**: remix/render 任务本身没有超时

## 测试建议

1. **模拟 worker 崩溃**: 
   - 在任务处理中抛出异常
   - 检查锁是否被正确释放

2. **模拟长时间任务**:
   - 创建会运行很长时间的任务
   - 检查超时机制是否生效

3. **模拟锁竞争**:
   - 同时启动多个任务
   - 检查是否有任务永久阻塞

4. **监控资源使用**:
   - 监控信号量使用情况
   - 检查是否有槽位被永久占用

## 相关文件

- `kat_rec_web/backend/t2r/services/channel_automation.py` - 自动化流程
- `kat_rec_web/backend/t2r/services/render_queue.py` - 渲染队列
- `kat_rec_web/backend/t2r/routes/plan.py` - 计划执行和 FFmpeg 队列
- `kat_rec_web/backend/t2r/utils/file_watcher.py` - 文件等待

## 更新日期

2025-01-XX

