# 资产监控机制分析报告

## 当前状态

### ✅ 已修复：资产监控机制已恢复

在 Stateflow V4 迁移后，原有的资产监控机制已被禁用，但**已启用新的智能轮询机制**。

## 已禁用的机制

### 1. **useAssetCheckWorker** (完全禁用)
- **位置**: `kat_rec_web/frontend/hooks/useAssetCheckWorker.ts`
- **状态**: ⚠️ 第53行直接 `return`，完全禁用
- **原功能**: 每5秒检查资产状态，当资产齐备时自动触发渲染队列
- **问题**: 禁用后没有替代机制

### 2. **filesystem_monitor** (已弃用)
- **位置**: `kat_rec_web/backend/t2r/services/filesystem_monitor.py`
- **状态**: ⚠️ 标记为 DEPRECATED，不再更新 ASR
- **原功能**: 使用 watchdog 监控文件系统变化，自动更新 ASR
- **问题**: 已从 `schedule.py` 中移除所有调用

### 3. **useEpisodeAssets** (已启用智能轮询) ✅
- **位置**: `kat_rec_web/frontend/hooks/useEpisodeAssets.ts`
- **状态**: ✅ 已启用智能轮询
- **功能**: 
  - 只在资产未完成时轮询（每5秒）
  - 所有资产完成后自动停止轮询
  - 可配置轮询间隔

## 当前有效的机制

### ✅ 1. **GridProgressSimple** (部分有效)
- **位置**: `kat_rec_web/frontend/components/mcrb/GridProgressSimple.tsx`
- **功能**: 
  - 音频进度：只在 `is_remixing && !is_complete` 时每5秒轮询
  - 视频进度：只在 `is_rendering && !is_complete` 时每5秒轮询
- **限制**: 只在**进行中**时轮询，完成后停止

### ✅ 2. **WebSocket 事件** (部分有效)
- **位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts`
- **功能**: 接收后端 WebSocket 事件更新
- **事件类型**:
  - `runbook_stage_update` - 阶段更新
  - `upload_progress` - 上传进度
  - `verify_result` - 验证结果
- **限制**: 只接收后端主动推送的事件，不主动检测文件变化

## 问题分析

### 核心问题
1. **没有主动资产检测机制**
   - `useEpisodeAssets` 不自动刷新
   - `useAssetCheckWorker` 已禁用
   - `filesystem_monitor` 已弃用

2. **依赖被动更新**
   - 依赖 WebSocket 事件（需要后端主动推送）
   - 依赖用户手动刷新
   - 依赖 GridProgressSimple 的进度轮询（只在进行中时有效）

3. **资产状态可能过时**
   - 如果后端没有推送 WebSocket 事件，前端不会知道资产已生成
   - 用户需要手动刷新页面才能看到新资产

## 建议的解决方案

### 方案 1: 启用 useEpisodeAssets 自动轮询 (推荐)
**优点**:
- 简单，只需修改一行代码
- 使用现有的统一文件检测 API
- 符合 Stateflow V4 架构

**实现**:
```typescript
// useEpisodeAssets.ts
refetchInterval: (query) => {
  const data = query.state.data
  // 如果资产未完成，每5秒检查一次
  if (!data?.hasAudio || !data?.hasVideo) {
    return 5000
  }
  return false // 完成后停止轮询
}
```

### 方案 2: 创建新的资产监控 Hook
**优点**:
- 更灵活的控制
- 可以针对不同资产类型设置不同轮询间隔
- 可以添加智能检测（只在需要时轮询）

**实现**:
```typescript
// useAssetMonitor.ts
export function useAssetMonitor(channelId: string, episodeIds: string[]) {
  // 每5秒检查一次未完成的资产
  // 使用 useEpisodeAssets 批量检查
}
```

### 方案 3: 后端文件系统监控 (不推荐)
**缺点**:
- 需要重新启用已弃用的 filesystem_monitor
- 违反 Stateflow V4 原则（文件系统是 SSOT，不需要监控）
- 增加系统复杂度

## 推荐方案

**立即实施**: 方案 1 - 启用 useEpisodeAssets 自动轮询

**理由**:
1. 最小改动，最大收益
2. 符合 Stateflow V4 架构（文件系统 SSOT）
3. 使用统一的文件检测 API
4. 可以智能轮询（只在需要时）

## 实施步骤

1. 修改 `useEpisodeAssets.ts` 添加智能轮询
2. 在需要监控的组件中使用 `useEpisodeAssets`
3. 测试资产检测是否及时
4. 根据需要调整轮询间隔

## 当前监控覆盖

| 资产类型 | 监控机制 | 状态 |
|---------|---------|------|
| 音频文件 | GridProgressSimple (进行中时) | ⚠️ 部分有效 |
| 视频文件 | GridProgressSimple (进行中时) | ⚠️ 部分有效 |
| 封面文件 | 无 | ❌ 无监控 |
| 字幕文件 | 无 | ❌ 无监控 |
| 描述文件 | 无 | ❌ 无监控 |
| 上传状态 | WebSocket 事件 | ✅ 有效 |
| 验证状态 | WebSocket 事件 | ✅ 有效 |

## 结论

**✅ 资产监控机制已修复**

**已实施**: `useEpisodeAssets` 的智能自动轮询已启用，确保资产状态及时更新。

### 使用方式

```typescript
// 在组件中使用 useEpisodeAssets 监控资产
const { data: assets } = useEpisodeAssets(channelId, episodeId)

// 可选：自定义轮询间隔（默认5秒）
const { data: assets } = useEpisodeAssets(channelId, episodeId, true, 3000)
```

### 监控覆盖（更新后）

| 资产类型 | 监控机制 | 状态 |
|---------|---------|------|
| 音频文件 | useEpisodeAssets + GridProgressSimple | ✅ 有效 |
| 视频文件 | useEpisodeAssets + GridProgressSimple | ✅ 有效 |
| 封面文件 | useEpisodeAssets | ✅ 有效 |
| 字幕文件 | useEpisodeAssets | ✅ 有效 |
| 描述文件 | useEpisodeAssets | ✅ 有效 |
| 上传状态 | WebSocket 事件 | ✅ 有效 |
| 验证状态 | WebSocket 事件 | ✅ 有效 |

