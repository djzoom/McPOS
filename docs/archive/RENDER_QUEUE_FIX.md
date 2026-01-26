# 渲染队列阻塞问题修复

## 问题描述

在渲染队列中点击"渲染"按钮时，渲染流程没有开始。检查代码后发现存在队列嵌套导致的阻塞问题。

## 根本原因

`render_queue.py` 的 `_process_job` 函数在调用 `_execute_stage("render", ...)` 时，没有传递 `_skip_queue=True` 参数。

这导致：
1. `render_queue.py` 的 `_worker` 已经在处理队列（全局渲染队列）
2. 当它调用 `_execute_stage("render", episode_id, emit_events=False)` 时，没有传递 `_skip_queue=True`
3. `_execute_stage` 函数检测到 `stage == "render"` 且 `_skip_queue=False`，会将任务再次放入 `plan.py` 的内部队列（`_queue`）
4. `_execute_stage` 然后等待 `job_done.wait()`，但 `render_queue.py` 的 worker 也在等待这个调用完成
5. 这造成了阻塞或死锁，导致渲染无法启动

## 修复方案

在 `kat_rec_web/backend/t2r/services/render_queue.py` 的第 207 行，将：

```python
await _execute_stage("render", episode_id, emit_events=False)
```

修改为：

```python
await _execute_stage("render", episode_id, emit_events=False, _skip_queue=True)
```

## 修复原理

- `render_queue.py` 本身已经是一个全局队列系统，确保渲染任务按顺序执行
- 当从 `render_queue.py` 调用 `_execute_stage` 时，应该跳过 `plan.py` 的内部队列，直接执行渲染逻辑
- 传递 `_skip_queue=True` 会让 `_execute_stage` 直接调用 `_execute_stage_core`，避免再次进入队列系统

## 相关代码

### 修复位置
- 文件：`kat_rec_web/backend/t2r/services/render_queue.py`
- 行号：207
- 函数：`_process_job`

### 为什么 `channel_automation.py` 不需要修复？

`channel_automation.py` 中的 `_run_remix_stage` 函数调用 `_execute_stage("remix", ...)` 时没有传递 `_skip_queue`，这是**正确的**，因为：

1. `channel_automation.py` 不是队列系统，它按顺序处理作业
2. 如果有多个频道同时运行，`plan.py` 的内部队列可以确保 FFmpeg 操作不会重叠
3. 因此，`channel_automation.py` 应该使用 `plan.py` 的内部队列

## 测试建议

1. 在渲染队列中点击"渲染"按钮
2. 检查后端日志，应该看到：
   - `[render-queue] Calling _execute_stage('render', {episode_id}) with _skip_queue=True`
   - `[render-queue] _execute_stage('render') completed for {episode_id}`
3. 渲染应该能够正常启动并完成

## 修复日期

2025-01-XX

