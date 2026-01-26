# "+2" 显示问题修复

## 问题描述

在排播总览界面中，某些日期单元格显示 "+2"，但检查文件夹并没有多余的文件产生。这是未及时清除的字段数据导致的。

## 根本原因

在 `scheduleStore.ts` 的 `hydrate` 函数中，当从后端加载事件数据时，代码会：

1. 添加/更新后端返回的新事件
2. **保留所有不在新数据中的现有事件**（第400-405行）

这导致：
- 如果后端删除了某些事件，前端仍然保留它们
- 当构建 `eventsByChannelAndDate` 时，这些已删除的事件仍然被计算在内
- 导致显示 "+2" 或更大的数字，即使实际上只有一个事件

## 修复方案

移除了 `hydrate` 函数中保留不在新数据中的现有事件的逻辑（第400-405行）。

**修复前：**
```typescript
// Then, add existing events that weren't in new data (preserve WebSocket-only updates)
existingEvents.forEach((existingEvent) => {
  if (!processedIds.has(existingEvent.id)) {
    merged.push(existingEvent)
  }
})
```

**修复后：**
```typescript
// IMPORTANT: Do NOT preserve existing events that aren't in new data
// This ensures deleted events are removed from the store
// If backend deleted an event, it won't be in newEvents, so we should remove it
// This fixes the "+2" display issue where deleted events were still showing
```

## 修复原理

- 当后端返回事件列表时，只保留后端返回的事件
- 如果后端删除了某个事件，它不会出现在返回列表中，前端也会移除它
- `buildEventIndexes` 函数会基于更新后的事件列表重新构建索引，确保 `eventsById` 和 `eventChannelIndex` 也同步更新

## 为什么之前要保留这些事件？

之前的代码注释说"preserve WebSocket-only updates"，这是为了保留通过 WebSocket 更新但后端 API 可能还没有返回的事件。但是：

1. 如果事件正在生成中，WebSocket 会通过 `patchEvent` 或 `upsertEvents` 来更新它们
2. 如果事件已被删除，应该从 store 中移除，而不是保留
3. 用户报告文件夹中没有多余的文件，说明这些事件确实应该被删除

## 相关代码

- 文件：`kat_rec_web/frontend/stores/scheduleStore.ts`
- 函数：`hydrate`
- 行号：400-405（已移除）

## 测试建议

1. 删除某个事件（通过后端或前端操作）
2. 刷新页面或等待 React Query 自动刷新
3. 检查排播总览界面，应该不再显示 "+2" 或更大的数字
4. 确认单元格中只显示实际存在的事件数量

## 修复日期

2025-01-XX

