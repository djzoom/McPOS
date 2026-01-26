# 前端状态更新监控方案

## 当前缓解措施分析

### 1. 时间戳检查（Forward-Only）✅

**位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts` (lines 461-469)

**实现**:
```typescript
const lastStageTimestamp = currentEvent?.gridProgress?.lastStageTimestamp || 0
const isNewerUpdate = eventTimestamp > lastStageTimestamp

// Only process if this is a newer update (forward-only animation)
if (!isNewerUpdate) {
  logger.debug(`[useWebSocket] Ignoring stale stage update for ${episodeId}: eventTimestamp=${eventTimestamp}, lastStageTimestamp=${lastStageTimestamp}`)
  return // Skip processing this update
}
```

**效果**: 
- ✅ 防止旧事件覆盖新事件
- ✅ 基于时间戳的简单验证
- ⚠️ 仅检查 `gridProgress.lastStageTimestamp`，不检查其他字段的时间戳

### 2. 批量更新机制 ✅

**位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts` (lines 74-200)

**实现**:
- 使用 `pendingUpdatesRef` 收集多个 `patchEvent` 调用
- 使用 `requestAnimationFrame` 和 `setTimeout` 批量处理
- 合并多个更新到一个 `patchEvent` 调用

**效果**:
- ✅ 减少 re-render 次数
- ✅ 提高性能
- ⚠️ 可能掩盖并发更新问题
- ⚠️ 如果多个更新同时到达，可能丢失中间状态

### 3. 状态历史记录 ✅

**位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts` (lines 486-500)

**实现**:
- 维护 `stageHistory` 数组（最多 10 条）
- 只添加新阶段或更高进度的更新
- 基于时间戳和进度值判断

**效果**:
- ✅ 保留状态变更历史
- ✅ 可用于调试和回滚
- ⚠️ 历史记录可能不完整（如果事件乱序到达）

### 4. 状态合并逻辑 ✅

**位置**: `kat_rec_web/frontend/stores/scheduleStore.ts` (lines 135-150)

**实现**:
- `mergeEventData` 函数合并更新
- 对于 `gridProgress`，保留最新的 `lastStageTimestamp`
- 合并 `stageHistory` 数组

**效果**:
- ✅ 正确处理部分更新
- ⚠️ 合并逻辑可能不够严格

## 潜在风险点

### 1. 时间戳精度问题 ⚠️

**风险**:
- 如果两个事件在同一毫秒内到达，时间戳可能相同
- 可能导致事件被错误地忽略或覆盖

**影响**: 低（但可能在高并发情况下发生）

### 2. 批处理延迟 ⚠️

**风险**:
- 批处理延迟（50ms）可能导致状态更新不及时
- 如果多个更新在批处理期间到达，可能丢失中间状态

**影响**: 中（可能导致 UI 闪烁或不一致）

### 3. 并发更新冲突 ⚠️

**风险**:
- 多个 WebSocket 事件同时更新同一 episode 的状态
- `patchEvent` 函数不是原子的，可能导致状态不一致

**影响**: 中（可能导致 UI 显示错误的状态）

### 4. 事件乱序到达 ⚠️

**风险**:
- WebSocket 事件可能乱序到达
- 即使有时间戳检查，如果事件时间戳相同或接近，可能无法正确排序

**影响**: 低（但可能在高并发情况下发生）

### 5. 状态合并冲突 ⚠️

**风险**:
- `mergeEventData` 可能无法正确处理冲突的更新
- 例如：同时更新 `assets.audio` 和 `assets.video`，可能丢失其中一个

**影响**: 中（可能导致资产信息丢失）

## 监控方案

### 1. 添加状态更新日志

**位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**实现**:
```typescript
// 在 batchedPatchEvent 中添加日志
const batchedPatchEvent = (episodeId: string, updates: Partial<ScheduleEvent>, options?: { immediate?: boolean; stage?: string }) => {
  // ... existing code ...
  
  // ✅ 添加监控日志
  if (process.env.NODE_ENV === 'development' || window.location.search.includes('debug=true')) {
    console.debug('[StateUpdate] Batched update:', {
      episodeId,
      updates: Object.keys(updates),
      timestamp: Date.now(),
      pendingCount: pendingUpdatesRef.current.size,
    })
  }
  
  // ... existing code ...
}
```

### 2. 添加时间戳冲突检测

**位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**实现**:
```typescript
// 在时间戳检查后添加警告
if (!isNewerUpdate) {
  logger.debug(`[useWebSocket] Ignoring stale stage update for ${episodeId}: eventTimestamp=${eventTimestamp}, lastStageTimestamp=${lastStageTimestamp}`)
  
  // ✅ 添加监控：检测时间戳冲突
  if (Math.abs(eventTimestamp - lastStageTimestamp) < 100) {
    console.warn('[StateUpdate] Potential timestamp conflict:', {
      episodeId,
      eventTimestamp,
      lastStageTimestamp,
      diff: Math.abs(eventTimestamp - lastStageTimestamp),
    })
  }
  
  return
}
```

### 3. 添加状态一致性检查

**位置**: `kat_rec_web/frontend/stores/scheduleStore.ts`

**实现**:
```typescript
// 在 patchEvent 中添加一致性检查
patchEvent: (eventId, updates) =>
  set((state) => {
    // ... existing code ...
    
    // ✅ 添加监控：检查状态一致性
    if (process.env.NODE_ENV === 'development') {
      const beforeState = state.eventsById[eventId]
      const afterState = updatedEvent
      
      // 检查关键字段是否一致
      if (beforeState && afterState) {
        const inconsistencies: string[] = []
        
        // 检查 assets 是否丢失
        if (beforeState.assets && !afterState.assets) {
          inconsistencies.push('assets lost')
        }
        
        // 检查 gridProgress 是否倒退
        const beforeProgress = beforeState.gridProgress?.lastStageTimestamp || 0
        const afterProgress = afterState.gridProgress?.lastStageTimestamp || 0
        if (afterProgress < beforeProgress) {
          inconsistencies.push(`gridProgress timestamp regressed: ${beforeProgress} -> ${afterProgress}`)
        }
        
        if (inconsistencies.length > 0) {
          console.warn('[StateUpdate] State inconsistency detected:', {
            eventId,
            inconsistencies,
            before: beforeState,
            after: afterState,
          })
        }
      }
    }
    
    // ... existing code ...
  }),
```

### 4. 添加性能监控

**位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**实现**:
```typescript
// 在批处理函数中添加性能监控
const processBatch = () => {
  const startTime = performance.now()
  
  // ... existing batch processing code ...
  
  const endTime = performance.now()
  const duration = endTime - startTime
  
  // ✅ 添加监控：记录批处理性能
  if (duration > 100) { // 如果批处理超过 100ms，记录警告
    console.warn('[StateUpdate] Slow batch processing:', {
      duration,
      batchSize: pendingUpdatesRef.current.size,
    })
  }
}
```

## 改进建议

### 1. 添加版本号/序列号机制 🔄

**建议**: 为每个状态更新添加版本号或序列号

**实现**:
```typescript
interface ScheduleEvent {
  // ... existing fields ...
  version?: number // 版本号，每次更新递增
  sequence?: number // 序列号，从后端发送
}

// 在 useWebSocket.ts 中
const isNewerUpdate = eventTimestamp > lastStageTimestamp || 
                     (eventTimestamp === lastStageTimestamp && 
                      (data.sequence || 0) > (currentEvent?.version || 0))
```

**好处**:
- 更准确地判断更新顺序
- 即使时间戳相同，也能正确排序

### 2. 使用乐观锁机制 🔄

**建议**: 在更新状态前检查版本号

**实现**:
```typescript
patchEvent: (eventId, updates, expectedVersion?: number) =>
  set((state) => {
    const currentEvent = state.eventsById[eventId]
    
    // ✅ 乐观锁检查
    if (expectedVersion !== undefined && currentEvent?.version !== expectedVersion) {
      console.warn('[StateUpdate] Version conflict:', {
        eventId,
        expected: expectedVersion,
        actual: currentEvent?.version,
      })
      return state // 不应用更新
    }
    
    // ... existing update logic ...
  }),
```

**好处**:
- 防止并发更新冲突
- 确保状态一致性

### 3. 添加状态快照机制 🔄

**建议**: 定期保存状态快照，用于调试和恢复

**实现**:
```typescript
// 在 scheduleStore.ts 中添加
const stateSnapshots: Array<{ timestamp: number; state: ScheduleStore }> = []

// 每 10 秒保存一次快照（仅保留最近 10 个）
setInterval(() => {
  const currentState = useScheduleStore.getState()
  stateSnapshots.push({
    timestamp: Date.now(),
    state: JSON.parse(JSON.stringify(currentState)), // 深拷贝
  })
  
  if (stateSnapshots.length > 10) {
    stateSnapshots.shift()
  }
}, 10000)
```

**好处**:
- 可以回滚到之前的状态
- 便于调试状态问题

### 4. 添加事件队列机制 🔄

**建议**: 使用事件队列确保更新顺序

**实现**:
```typescript
// 为每个 episode 维护一个事件队列
const eventQueues = new Map<string, Array<{ timestamp: number; updates: Partial<ScheduleEvent> }>>()

// 按时间戳排序处理事件
const processEventQueue = (episodeId: string) => {
  const queue = eventQueues.get(episodeId) || []
  queue.sort((a, b) => a.timestamp - b.timestamp)
  
  queue.forEach(({ updates }) => {
    batchedPatchEvent(episodeId, updates)
  })
  
  eventQueues.set(episodeId, [])
}
```

**好处**:
- 确保事件按顺序处理
- 避免乱序更新导致的状态不一致

### 5. 添加状态验证函数 🔄

**建议**: 添加状态验证函数，检查状态是否有效

**实现**:
```typescript
const validateEventState = (event: ScheduleEvent): { valid: boolean; errors: string[] } => {
  const errors: string[] = []
  
  // 检查必需字段
  if (!event.id) errors.push('Missing id')
  if (!event.channelId) errors.push('Missing channelId')
  
  // 检查时间戳一致性
  if (event.gridProgress?.lastStageTimestamp && 
      event.gridProgress.stageHistory.length > 0) {
    const lastHistory = event.gridProgress.stageHistory[event.gridProgress.stageHistory.length - 1]
    if (lastHistory.timestamp > event.gridProgress.lastStageTimestamp) {
      errors.push('History timestamp exceeds lastStageTimestamp')
    }
  }
  
  // 检查资产完整性
  if (event.assets?.video && !event.assets?.render_complete_flag) {
    errors.push('Video exists but render_complete_flag missing')
  }
  
  return { valid: errors.length === 0, errors }
}
```

**好处**:
- 及早发现状态不一致
- 提供详细的错误信息

## 实施优先级

### 高优先级（立即实施）
1. ✅ 添加状态更新日志（开发环境）
2. ✅ 添加时间戳冲突检测
3. ✅ 添加状态一致性检查（开发环境）

### 中优先级（近期实施）
1. 🔄 添加版本号/序列号机制
2. 🔄 添加状态验证函数
3. 🔄 添加性能监控

### 低优先级（长期改进）
1. 🔄 使用乐观锁机制
2. 🔄 添加状态快照机制
3. 🔄 添加事件队列机制

## 监控指标

### 关键指标
1. **状态更新频率**: 每个 episode 每秒的更新次数
2. **批处理延迟**: 从事件到达到应用更新的延迟
3. **时间戳冲突率**: 时间戳相同或接近的事件比例
4. **状态不一致率**: 检测到的状态不一致次数
5. **批处理大小**: 每次批处理的事件数量

### 告警阈值
- 状态更新频率 > 10/秒: 警告
- 批处理延迟 > 200ms: 警告
- 时间戳冲突率 > 5%: 警告
- 状态不一致率 > 1%: 严重警告

## 总结

当前的前端状态更新机制已经有较好的缓解措施（时间戳检查、批量更新、状态历史），但仍存在潜在的竞态条件风险。通过添加监控日志、时间戳冲突检测和状态一致性检查，可以及早发现问题。长期来看，建议实施版本号机制、乐观锁和事件队列，以进一步提高状态更新的可靠性和一致性。

