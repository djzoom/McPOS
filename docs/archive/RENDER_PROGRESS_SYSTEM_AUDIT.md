# 渲染进度系统全面审计报告

**日期**: 2025-01-XX  
**目的**: Stateflow V4 Phase 3.1 - 渲染进度系统统一化准备  
**状态**: 仅审计，无代码修改

---

## 执行摘要

当前渲染进度系统存在**多个状态源和重复逻辑**，需要统一到单一后端 API (`/api/t2r/episodes/{episode_id}/progress/video`) 和单一前端 hook (`useVideoProgress()`)。

**主要发现**:
- 后端有 3+ 个不同的渲染进度检测逻辑
- 前端有 4+ 个不同的渲染状态判断路径
- 存在文件系统检查、ASR 查询、WebSocket 事件、队列状态等多种状态源
- 大量启发式检测逻辑（文件大小、mtime、进度估算）

---

## 1. 后端渲染进度相关模块

### 1.1 API 端点

#### ❌ **`/api/t2r/episodes/{episode_id}/video-progress`** (端点缺失)
- **位置**: 前端调用此端点 (`t2rApi.ts:846`)
- **实现**: ❌ **未找到对应的后端路由**
- **路由注册**: 检查了 `main.py` 和所有路由文件，**此端点不存在**
- **状态**: ⚠️ **端点不存在但前端在调用**
- **问题**: 
  - 前端调用但后端路由缺失，可能导致 404
  - 需要创建路由并连接到 `render_progress_service.py`
- **建议**: 在 `episode_flow.py` 中添加路由或创建新的 `video_progress.py` 路由文件

#### ✅ **`render_progress_service.py`** (新创建，未使用)
- **位置**: `kat_rec_web/backend/t2r/services/render_progress_service.py`
- **函数**: `get_video_progress(channel_id, episode_id)`
- **状态**: ✅ **已创建但未注册路由**
- **逻辑**:
  - 检查 `render_complete_flag` → `is_rendering=False, progress=1.0`
  - 检查 MP4 + mtime (<30s) → `is_rendering=True`
  - 检查 MP4 + mtime (>30s) → `progress=1.0` (假设完成)
  - 检查 timeline CSV → `is_rendering=True`
- **问题**: 已创建但未接入路由系统

### 1.2 文件检测模块

#### ✅ **`file_detect.py::detect_video()`** (Stateflow V4)
- **位置**: `kat_rec_web/backend/t2r/utils/file_detect.py:64`
- **功能**: 检测视频文件 + render_complete_flag
- **返回**: `(has_video: bool, video_path: Optional[str], has_render_flag: bool)`
- **状态**: ✅ **当前使用中** (被 `episode_flow.py` 和 `state_snapshot.py` 使用)
- **问题**: 只返回布尔值，不返回进度信息

### 1.3 视频完成检查器

#### ✅ **`video_completion_checker.py`** (多方法检测)
- **位置**: `kat_rec_web/backend/t2r/utils/video_completion_checker.py`
- **函数**:
  1. `is_video_complete_by_ffprobe()` - 使用 ffprobe 验证
  2. `is_video_size_stable()` - 检查文件大小稳定性
  3. `has_render_complete_flag()` - 检查 flag 文件
  4. `check_video_completion()` - 综合检查（优先级：ffprobe > size_stability > flag）
- **状态**: ✅ **存在但使用情况不明**
- **问题**: 多个检测方法，优先级不统一

### 1.4 渲染验证器

#### ✅ **`render_validator.py`** (FFprobe 验证)
- **位置**: `kat_rec_web/backend/t2r/services/render_validator.py`
- **功能**: 使用 ffprobe 验证视频文件完整性
- **状态**: ⚠️ **存在但使用情况不明**
- **问题**: 与 `video_completion_checker.py` 功能重复

### 1.5 渲染队列

#### ✅ **`render_queue.py`** (队列状态管理)
- **位置**: `kat_rec_web/backend/t2r/services/render_queue.py`
- **关键函数**:
  - `enqueue_render_job()` - 入队渲染任务
  - `_worker()` - 队列工作线程
  - `_process_job()` - 处理单个渲染任务
  - `_is_job_present_locked()` - 检查任务是否在队列中
- **状态检测**:
  - 第 654-661 行: 检查 `render_complete_flag` + 视频文件判断是否已完成
  - 第 429 行: 检查 YouTube 资产是否齐备
- **状态**: ✅ **当前使用中**
- **问题**: 
  - 队列状态被用作完成判断（第 654 行标记了 TODO）
  - 队列状态不是 SSOT，应该用文件系统检查

### 1.6 渲染队列同步

#### ✅ **`render_queue_sync.py`** (同步服务)
- **位置**: `kat_rec_web/backend/t2r/services/render_queue_sync.py`
- **功能**: 从文件系统同步资产状态到 schedule_master.json
- **使用**: ASR (`asset_service.scan_and_update_episode_assets()`)
- **状态**: ⚠️ **使用 ASR，违反 Stateflow V4 原则**
- **问题**: 依赖 ASR 而不是直接文件系统检查

#### ✅ **`render_queue_sync.py`** (路由)
- **位置**: `kat_rec_web/backend/t2r/routes/render_queue_sync.py`
- **端点**:
  - `/render-queue-sync/ready-for-render` - 获取准备渲染的期数
  - `/render-queue-sync/completed-renders` - 获取已完成渲染的期数
- **状态**: ✅ **当前使用中**
- **问题**: 依赖 ASR 判断完成状态

### 1.7 状态快照

#### ✅ **`state_snapshot.py`** (状态快照 API)
- **位置**: `kat_rec_web/backend/t2r/routes/state_snapshot.py`
- **功能**: 提供完整状态快照
- **渲染状态判断** (第 97 行):
  ```python
  render_status = "complete" if assets.get("hasVideo") else ("in_progress" if assets.get("videoPath") else "pending")
  ```
- **状态**: ✅ **当前使用中**
- **问题**: 
  - 只检查 `hasVideo`，不检查 `render_complete_flag`
  - 逻辑过于简单，可能误判

### 1.8 计划执行

#### ✅ **`plan.py`** (Runbook 执行)
- **位置**: `kat_rec_web/backend/t2r/routes/plan.py`
- **功能**: 执行 runbook 阶段，包括渲染
- **WebSocket 事件**: 发送 `runbook_stage_update` 事件
- **进度更新**: 第 207 行计算进度 `progress = int(((idx + 1) / total_stages) * 100)`
- **状态**: ✅ **当前使用中**
- **问题**: 
  - WebSocket 事件包含进度信息，前端可能直接使用作为状态源
  - 进度计算基于阶段数量，不是实际渲染进度

### 1.9 EpisodeFlow 适配器

#### ✅ **`episode_flow_adapters.py`** (EpisodeFlow 集成)
- **位置**: `kat_rec_web/backend/t2r/services/episode_flow_adapters.py`
- **功能**: EpisodeFlow 协议的适配器实现
- **渲染执行**: 第 257-262 行调用 `_execute_stage_core("render")`
- **视频文件查找**: 第 264-280 行查找生成的视频文件
- **状态**: ✅ **当前使用中**
- **问题**: 渲染完成后查找视频文件，但不检查 `render_complete_flag`

---

## 2. 前端渲染进度相关模块

### 2.1 API 服务

#### ✅ **`t2rApi.ts::getVideoRenderProgress()`**
- **位置**: `kat_rec_web/frontend/services/t2rApi.ts:842`
- **端点**: `/api/t2r/episodes/${episode_id}/video-progress`
- **状态**: ✅ **当前使用中**
- **问题**: 调用不存在的后端端点（可能返回 404）

### 2.2 进度组件

#### ✅ **`GridProgressSimple.tsx`** (主要 UI 组件)
- **位置**: `kat_rec_web/frontend/components/mcrb/GridProgressSimple.tsx`
- **视频进度获取** (第 61-74 行):
  - 使用 `useQuery` 调用 `getVideoRenderProgress()`
  - 轮询逻辑: 只在 `is_rendering && !is_complete` 时每 5 秒轮询
- **完成判断** (第 79-126 行):
  - Priority 1: `videoProgress?.is_complete`
  - Priority 2: `video_path + render_complete_flag`
  - Priority 3: 文件大小 > 100MB + 不在渲染中
  - Priority 4: `event.assets` (可能过时)
- **状态**: ✅ **当前使用中**
- **问题**: 
  - 多层 fallback 逻辑复杂
  - 依赖可能不存在的 API
  - 使用启发式检测（文件大小）

### 2.3 渲染队列面板

#### ✅ **`RenderQueuePanel.tsx`** (队列显示)
- **位置**: `kat_rec_web/frontend/components/mcrb/RenderQueuePanel.tsx`
- **完成判断** (第 66-68 行):
  ```typescript
  const hasVideo = !!(assets?.video || assets?.video_path)
  const hasRenderFlag = !!assets?.render_complete_flag
  const isRenderDone = hasVideo && hasRenderFlag
  ```
- **状态**: ✅ **当前使用中**
- **问题**: 直接检查 `event.assets`，可能过时

### 2.4 WebSocket 处理

#### ✅ **`useWebSocket.ts`** (WebSocket 事件处理)
- **位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts`
- **渲染完成处理** (第 583-601 行):
  - 监听 `runbook_stage_update` 事件
  - 当 `stage.includes('render') && progress === 100` 时更新 `event.assets`
  - 标记: TODO(Stateflow V4): 应作为通知，需重新获取 REST 端点
- **状态**: ✅ **当前使用中**
- **问题**: 
  - 直接使用 WebSocket 事件作为状态源
  - 应该只作为通知，然后重新获取 REST API

### 2.5 Schedule Store

#### ✅ **`scheduleStore.ts`** (状态存储)
- **位置**: `kat_rec_web/frontend/stores/scheduleStore.ts`
- **函数**: `calculateStageStatus()` (已弃用，返回空状态)
- **状态**: ⚠️ **已禁用但可能仍有引用**
- **问题**: 已标记为弃用，但可能仍有组件在使用

### 2.6 资产工具

#### ✅ **`assetUtils.ts::hasVideo()`**
- **位置**: `kat_rec_web/frontend/utils/assetUtils.ts:93`
- **功能**: 检查事件是否有视频
- **状态**: ✅ **当前使用中**
- **问题**: 只检查视频存在，不检查 flag

---

## 3. 状态源地图

### 3.1 后端状态源

| 状态源 | 位置 | 检测方法 | 是否使用 | 应保留/重构/删除 | 优先级 |
|--------|------|---------|---------|-----------------|--------|
| `render_progress_service.py` | `services/render_progress_service.py` | 文件系统 + mtime + flag | ❌ 未使用 | ✅ **保留并统一** | **P0** |
| `file_detect.py::detect_video()` | `utils/file_detect.py:64` | 文件系统检查 | ✅ 使用中 | ✅ **保留** (作为基础) | P1 |
| `video_completion_checker.py` | `utils/video_completion_checker.py` | ffprobe + size_stability + flag | ⚠️ 使用情况不明 | ⚠️ **评估后决定** | P2 |
| `render_validator.py` | `services/render_validator.py` | ffprobe 验证 | ⚠️ 使用情况不明 | ⚠️ **评估后决定** | P2 |
| `render_queue.py::_is_job_present_locked()` | `services/render_queue.py:654` | 文件系统检查 (flag + video) | ✅ 使用中 | ⚠️ **重构** (队列不应判断完成) | P1 |
| `render_queue_sync.py` | `services/render_queue_sync.py` | ASR 查询 | ✅ 使用中 | ❌ **删除/重构** (违反 V4) | P0 |
| `state_snapshot.py` | `routes/state_snapshot.py:97` | `hasVideo` 简单检查 | ✅ 使用中 | ⚠️ **重构** (需检查 flag) | P1 |
| `plan.py` WebSocket 事件 | `routes/plan.py` | Runbook 阶段更新 | ✅ 使用中 | ✅ **保留** (作为通知) | P1 |

### 3.2 前端状态源

| 状态源 | 位置 | 检测方法 | 是否使用 | 应保留/重构/删除 | 优先级 |
|--------|------|---------|---------|-----------------|--------|
| `getVideoRenderProgress()` API | `services/t2rApi.ts:842` | REST API 调用 | ✅ 使用中 | ⚠️ **修复** (端点不存在) | **P0** |
| `GridProgressSimple` 多层判断 | `components/mcrb/GridProgressSimple.tsx:79` | API + 启发式 + event.assets | ✅ 使用中 | ❌ **重构** (应只用统一 API) | **P0** |
| `RenderQueuePanel` 直接检查 | `components/mcrb/RenderQueuePanel.tsx:66` | `event.assets` 直接检查 | ✅ 使用中 | ❌ **重构** (应使用统一 hook) | P1 |
| `useWebSocket` 事件处理 | `hooks/useWebSocket.ts:583` | WebSocket 事件 | ✅ 使用中 | ⚠️ **重构** (应只作为通知) | P1 |
| `assetUtils::hasVideo()` | `utils/assetUtils.ts:93` | 简单检查 | ✅ 使用中 | ⚠️ **保留** (工具函数) | P2 |
| `calculateStageStatus()` | `stores/scheduleStore.ts:930` | 已弃用 | ❌ 已禁用 | ❌ **删除** | P3 |

---

## 4. 冲突和重复

### 4.1 后端冲突

#### ❌ **冲突 1: 视频完成判断逻辑重复**
- **位置 1**: `render_progress_service.py` - 使用 mtime + flag
- **位置 2**: `video_completion_checker.py` - 使用 ffprobe + size_stability + flag
- **位置 3**: `render_queue.py` - 使用 flag + video 文件存在
- **问题**: 三种不同的判断逻辑，优先级不一致
- **建议**: 统一到 `render_progress_service.py`

#### ❌ **冲突 2: 状态源不统一**
- **ASR**: `render_queue_sync.py` 使用 ASR 查询完成状态
- **文件系统**: `file_detect.py` 使用直接文件检查
- **队列状态**: `render_queue.py` 使用队列状态判断完成
- **问题**: 三个不同的状态源，可能不一致
- **建议**: 统一到文件系统检查

#### ❌ **冲突 3: API 端点缺失**
- **前端调用**: `/api/t2r/episodes/{episode_id}/video-progress`
- **后端实现**: ❌ **不存在**
- **问题**: 前端调用不存在的端点
- **建议**: 创建路由并连接到 `render_progress_service.py`

### 4.2 前端冲突

#### ❌ **冲突 1: 多层 fallback 逻辑**
- **GridProgressSimple**: 4 层优先级判断（API → API 字段 → 启发式 → event.assets）
- **问题**: 逻辑复杂，难以维护，可能产生不一致
- **建议**: 统一到单一 API 调用

#### ❌ **冲突 2: 直接使用 WebSocket 事件作为状态**
- **useWebSocket**: 直接更新 `event.assets` 基于 WebSocket 事件
- **问题**: WebSocket 事件可能丢失或延迟，不应作为 SSOT
- **建议**: WebSocket 只作为通知，然后重新获取 REST API

#### ❌ **冲突 3: 多个组件重复判断逻辑**
- **GridProgressSimple**: 复杂的完成判断
- **RenderQueuePanel**: 简单的完成判断
- **问题**: 两个组件判断逻辑不一致
- **建议**: 统一使用 `useVideoProgress()` hook

---

## 5. 依赖关系图

### 5.1 后端依赖

```
render_progress_service.py (新，未使用)
  └─> file_detect.py::detect_video() ✅
  └─> 文件系统检查 (mtime, size) ✅

file_detect.py::detect_video() ✅
  └─> 文件系统检查 (直接)

video_completion_checker.py ⚠️
  └─> ffprobe (外部工具)
  └─> 文件系统检查 (size stability)
  └─> render_complete_flag 检查

render_queue.py ✅
  └─> 文件系统检查 (flag + video) ⚠️ TODO标记
  └─> WebSocket 事件发送 ✅

render_queue_sync.py ⚠️
  └─> ASR (asset_service) ❌ 违反 V4
  └─> video_completion_checker.py ⚠️

state_snapshot.py ✅
  └─> file_detect.py::detect_all_assets() ✅
  └─> 简单 hasVideo 检查 ⚠️ 不完整
```

### 5.2 前端依赖

```
GridProgressSimple.tsx ✅
  └─> getVideoRenderProgress() API ⚠️ 端点不存在
  └─> event.assets (fallback) ⚠️ 可能过时
  └─> 启发式检测 (文件大小 > 100MB) ⚠️

RenderQueuePanel.tsx ✅
  └─> event.assets (直接检查) ⚠️ 可能过时
  └─> calculateStageStatus() ⚠️ 已弃用

useWebSocket.ts ✅
  └─> WebSocket 事件 (直接更新 state) ⚠️ 应只作为通知
```

---

## 6. 使用情况统计

### 6.1 后端模块使用情况

| 模块 | 被引用次数 | 主要使用者 | 状态 |
|------|-----------|-----------|------|
| `render_progress_service.py` | 0 | 无 | ❌ 未使用 |
| `file_detect.py::detect_video()` | 2+ | `episode_flow.py`, `state_snapshot.py` | ✅ 使用中 |
| `video_completion_checker.py` | 1+ | `render_queue_sync.py` | ⚠️ 部分使用 |
| `render_validator.py` | 0+ | 未知 | ⚠️ 使用情况不明 |
| `render_queue.py` | 5+ | `automation.py`, `render_queue_sync.py` | ✅ 使用中 |
| `render_queue_sync.py` | 1+ | `render_queue_sync.py` (路由) | ✅ 使用中 |

### 6.2 前端模块使用情况

| 模块 | 被引用次数 | 主要使用者 | 状态 |
|------|-----------|-----------|------|
| `getVideoRenderProgress()` | 1 | `GridProgressSimple.tsx` | ✅ 使用中 |
| `GridProgressSimple` | 1+ | `OverviewGrid.tsx` | ✅ 使用中 |
| `RenderQueuePanel` | 1+ | `OverviewGrid.tsx` | ✅ 使用中 |
| `useWebSocket` | 1+ | 全局 | ✅ 使用中 |
| `calculateStageStatus()` | 2+ | `RenderQueuePanel`, `OverviewGrid` | ⚠️ 已弃用但仍使用 |

---

## 7. 问题总结

### 7.1 关键问题 (P0)

1. **❌ 后端 API 端点缺失**
   - 前端调用 `/api/t2r/episodes/{episode_id}/video-progress`
   - 后端没有对应的路由
   - **影响**: 前端可能收到 404 错误

2. **❌ 新服务未接入**
   - `render_progress_service.py` 已创建但未注册路由
   - **影响**: 新统一服务无法使用

3. **❌ ASR 依赖违反 V4 原则**
   - `render_queue_sync.py` 使用 ASR 查询完成状态
   - **影响**: 违反 Stateflow V4 原则（文件系统是 SSOT）

### 7.2 重要问题 (P1)

4. **⚠️ 队列状态用作完成判断**
   - `render_queue.py` 使用队列状态判断是否已完成
   - **影响**: 队列状态不是 SSOT，可能不一致

5. **⚠️ 前端多层 fallback 逻辑复杂**
   - `GridProgressSimple` 有 4 层优先级判断
   - **影响**: 难以维护，可能产生不一致

6. **⚠️ WebSocket 事件直接用作状态**
   - `useWebSocket` 直接更新 state 基于 WebSocket 事件
   - **影响**: 事件可能丢失，不应作为 SSOT

7. **⚠️ 状态快照逻辑不完整**
   - `state_snapshot.py` 只检查 `hasVideo`，不检查 flag
   - **影响**: 可能误判完成状态

### 7.3 次要问题 (P2)

8. **⚠️ 视频完成检查器功能重复**
   - `video_completion_checker.py` 和 `render_validator.py` 功能重复
   - **影响**: 代码重复，维护成本高

9. **⚠️ 多个组件重复判断逻辑**
   - `GridProgressSimple` 和 `RenderQueuePanel` 判断逻辑不一致
   - **影响**: 可能显示不一致的状态

---

## 8. 建议的统一方案

### 8.1 后端统一方案

**目标**: 单一状态源 - `/api/t2r/episodes/{episode_id}/progress/video`

1. **创建路由** (P0):
   - 在 `episode_flow.py` 或新建 `video_progress.py` 中添加路由
   - 连接到 `render_progress_service.py::get_video_progress()`

2. **统一逻辑** (P0):
   - 使用 `render_progress_service.py` 作为唯一实现
   - 移除或重构其他检测逻辑

3. **移除 ASR 依赖** (P0):
   - 重构 `render_queue_sync.py` 使用文件系统检查
   - 移除 ASR 查询

4. **修复队列判断** (P1):
   - `render_queue.py` 中的完成判断改为调用统一 API
   - 或使用 `file_detect.py` 直接检查

### 8.2 前端统一方案

**目标**: 单一 hook - `useVideoProgress()`

1. **创建统一 hook** (P0):
   - 创建 `useVideoProgress.ts`
   - 调用统一 API `/api/t2r/episodes/{episode_id}/progress/video`

2. **重构 GridProgressSimple** (P0):
   - 移除所有 fallback 逻辑
   - 只使用 `useVideoProgress()` hook

3. **重构 RenderQueuePanel** (P1):
   - 移除直接 `event.assets` 检查
   - 使用 `useVideoProgress()` hook

4. **修复 WebSocket 处理** (P1):
   - WebSocket 事件只作为通知
   - 触发 `useVideoProgress()` 重新获取

---

## 9. 迁移风险评估

### 9.1 高风险区域

1. **GridProgressSimple** - 复杂的多层逻辑，重构可能影响 UI 显示
2. **RenderQueuePanel** - 直接使用 `event.assets`，可能多处引用
3. **render_queue_sync.py** - 使用 ASR，重构需要仔细测试

### 9.2 低风险区域

1. **render_progress_service.py** - 新创建，未使用，可以安全修改
2. **video_completion_checker.py** - 使用情况不明，可以评估后决定

---

## 10. 下一步行动

### Phase 3.1 执行步骤 (按优先级)

1. **P0 - 创建统一后端 API**:
   - 创建 `/api/t2r/episodes/{episode_id}/progress/video` 路由
   - 连接到 `render_progress_service.py`

2. **P0 - 创建统一前端 hook**:
   - 创建 `useVideoProgress.ts`
   - 实现智能轮询逻辑

3. **P0 - 重构 GridProgressSimple**:
   - 移除所有 fallback 逻辑
   - 只使用 `useVideoProgress()`

4. **P1 - 修复其他组件**:
   - 重构 `RenderQueuePanel`
   - 修复 `useWebSocket` 事件处理
   - 修复 `state_snapshot.py` 逻辑

5. **P1 - 移除 ASR 依赖**:
   - 重构 `render_queue_sync.py`
   - 移除 ASR 查询

6. **P2 - 清理重复代码**:
   - 评估 `video_completion_checker.py` 和 `render_validator.py`
   - 决定保留或删除

---

## 11. WebSocket 事件清单

### 11.1 渲染相关 WebSocket 事件

| 事件类型 | 发送位置 | 数据内容 | 状态 |
|---------|---------|---------|------|
| `runbook_stage_update` | `plan.py`, `render_queue.py` | `stage`, `progress`, `episode_id` | ✅ 使用中 |
| `runbook_error` | `plan.py`, `render_queue.py` | `error`, `stage`, `episode_id` | ✅ 使用中 |
| `render_start` | ❌ 未找到 | - | ❌ 不存在 |
| `render_complete` | ❌ 未找到 | - | ❌ 不存在 |

**详细 WebSocket 事件发送位置**:

1. **`render_queue.py`** (多处):
   - 第 174 行: `RENDER_QUEUE` + `PENDING` (入队时)
   - 第 269 行: `RENDER_QUEUE` + `IN_PROGRESS` (出队时)
   - 第 392 行: `RENDER_ACTIVE` + `IN_PROGRESS` (开始渲染)
   - 第 403 行: `RENDER_DONE` + `DONE`, `progress=100` (渲染完成)
   - 第 415 行: `RENDER_QUEUE` + `DONE` (从队列移除)

2. **`plan.py`**:
   - 第 221 行: `runbook_stage_update` (阶段开始)
   - 第 304 行: `runbook_stage_update` (完成)

**问题**: 
- 文档建议发送 `render_start` 和 `render_complete` 事件，但代码中未找到
- 当前只有通用的 `runbook_stage_update` 事件，使用 `RENDER_ACTIVE`, `RENDER_DONE` 等 stage 值
- WebSocket 事件包含 `progress` 字段，前端可能直接使用作为状态源

---

## 附录: 文件清单

### 后端文件 (24+ 个)

1. ✅ `services/render_progress_service.py` - 新统一服务 (未使用)
2. ✅ `utils/file_detect.py` - 文件检测 (使用中)
3. ✅ `utils/video_completion_checker.py` - 完成检查器 (部分使用)
4. ✅ `services/render_validator.py` - 验证器 (使用情况不明)
5. ✅ `services/render_queue.py` - 渲染队列 (使用中)
6. ✅ `services/render_queue_sync.py` - 队列同步 (使用中)
7. ✅ `routes/render_queue_sync.py` - 队列同步路由 (使用中)
8. ✅ `routes/state_snapshot.py` - 状态快照 (使用中)
9. ✅ `routes/plan.py` - 计划执行 (使用中)
10. ❌ `routes/episodes.py` - **未找到 video-progress 路由** (端点缺失)
11. ⚠️ `routes/episode_flow.py` - 只有 `/episode/{episode_id}/assets`，没有 progress 端点
12. ⚠️ `services/episode_flow_helper.py` - EpisodeFlow 集成，可能涉及渲染
13. ⚠️ `services/episode_flow_adapters.py` - EpisodeFlow 适配器，可能涉及渲染

### 前端文件 (21 个)

1. ✅ `services/t2rApi.ts` - API 服务 (使用中)
2. ✅ `components/mcrb/GridProgressSimple.tsx` - 主要 UI (使用中)
3. ✅ `components/mcrb/RenderQueuePanel.tsx` - 队列面板 (使用中)
4. ✅ `hooks/useWebSocket.ts` - WebSocket 处理 (使用中)
5. ✅ `stores/scheduleStore.ts` - 状态存储 (部分使用)
6. ✅ `utils/assetUtils.ts` - 工具函数 (使用中)

---

**审计完成时间**: 2025-01-XX  
**审计人员**: AI Assistant  
**下一步**: 等待 Phase 3.1 执行指令

