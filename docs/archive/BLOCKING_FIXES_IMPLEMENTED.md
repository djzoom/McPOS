# 阻塞点修复实现总结

## 修复概述

实现了优先级 1 的关键阻塞点修复，为所有关键锁和等待操作添加了超时机制，防止死锁和永久阻塞。

## 修复内容

### 1. render_queue.py - `_LOCK` 超时机制

**文件**: `kat_rec_web/backend/t2r/services/render_queue.py`

**修复内容**:
- 添加 `_LOCK_TIMEOUT = 5.0` 常量
- 创建 `_acquire_lock_with_timeout()` 辅助函数
- 替换所有 `async with _LOCK:` 为带超时的锁获取

**修复位置**:
- `enqueue_render_job()` - 入队操作
- `_worker()` - Worker 启动和队列检查
- `get_render_queue_snapshot()` - 获取队列快照

**超时时间**: 5秒

**错误处理**: 超时后抛出 `RuntimeError`，包含详细的错误信息

### 2. plan.py - `_queue_lock` 超时机制

**文件**: `kat_rec_web/backend/t2r/routes/plan.py`

**修复内容**:
- 添加 `_QUEUE_LOCK_TIMEOUT = 5.0` 常量
- 创建 `_acquire_queue_lock_with_timeout()` 辅助函数
- 替换所有 `async with _queue_lock:` 为带超时的锁获取

**修复位置**:
- `_execute_stage_queue_worker()` - Worker 停止检查
- `_execute_stage()` - 启动 worker 时的锁获取

**超时时间**: 5秒

**错误处理**: 超时后抛出 `RuntimeError`，包含详细的错误信息

### 3. plan.py - `job_done.wait()` 超时机制

**文件**: `kat_rec_web/backend/t2r/routes/plan.py`

**修复内容**:
- 添加 `_JOB_DONE_TIMEOUT = 3600.0` 常量（1小时）
- 使用 `asyncio.wait_for()` 包装 `job_done.wait()`

**修复位置**:
- `_execute_stage()` - 等待 FFmpeg 任务完成

**超时时间**: 3600秒（1小时）

**错误处理**: 超时后抛出 `RuntimeError`，包含任务编号和阶段信息

## 修复前后对比

### 修复前

```python
# render_queue.py
async with _LOCK:
    # 操作队列
    # 如果 worker 崩溃，锁可能永久持有

# plan.py
async with _queue_lock:
    # 操作队列状态
    # 如果 worker 崩溃，锁可能永久持有

await job_done.wait()
# 如果 worker 崩溃，job_done 永远不会被设置，永久阻塞
```

### 修复后

```python
# render_queue.py
await _acquire_lock_with_timeout()
try:
    # 操作队列
finally:
    _LOCK.release()
# 5秒超时，防止死锁

# plan.py
await _acquire_queue_lock_with_timeout()
try:
    # 操作队列状态
finally:
    _queue_lock.release()
# 5秒超时，防止死锁

try:
    await asyncio.wait_for(job_done.wait(), timeout=_JOB_DONE_TIMEOUT)
except asyncio.TimeoutError:
    raise RuntimeError(f"Job did not complete within {_JOB_DONE_TIMEOUT}s")
# 1小时超时，防止永久阻塞
```

## 超时时间选择

### `_LOCK_TIMEOUT` 和 `_QUEUE_LOCK_TIMEOUT`: 5秒

**理由**:
- 锁操作应该是瞬时的（只是检查状态和更新标志）
- 5秒足够处理正常的锁竞争
- 如果超过5秒，很可能发生了死锁或 worker 崩溃

### `_JOB_DONE_TIMEOUT`: 3600秒（1小时）

**理由**:
- FFmpeg 任务（remix/render）可能需要很长时间
- 1小时足够处理大多数正常任务
- 如果超过1小时，任务可能卡住或崩溃

## 错误处理

所有超时都会：
1. 记录详细的错误日志（包含超时时间和可能的死锁信息）
2. 抛出 `RuntimeError` 异常，包含清晰的错误消息
3. 允许调用者捕获异常并采取恢复措施

## 测试建议

### 1. 模拟 worker 崩溃

```python
# 在 worker 中故意抛出异常
# 检查锁是否被正确释放
# 检查后续任务是否能正常获取锁
```

### 2. 模拟长时间任务

```python
# 创建会运行很长时间的任务
# 检查超时机制是否生效
# 检查错误是否正确抛出
```

### 3. 模拟锁竞争

```python
# 同时启动多个任务
# 检查是否有任务永久阻塞
# 检查超时是否正确触发
```

## 后续改进建议

### 优先级 2: 任务级别超时

- 为 remix/render 任务添加超时（例如：30分钟）
- 定期检查任务状态，超时后取消任务并释放资源

### 优先级 3: 监控和恢复

- 添加健康检查，自动重启崩溃的 worker
- 添加任务恢复机制，失败任务可以手动或自动重试

## 相关文件

- `kat_rec_web/backend/t2r/services/render_queue.py` - 渲染队列锁超时
- `kat_rec_web/backend/t2r/routes/plan.py` - FFmpeg 队列锁和任务等待超时

## 修复日期

2025-01-XX

