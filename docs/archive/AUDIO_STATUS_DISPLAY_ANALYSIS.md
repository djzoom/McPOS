# 音频状态显示分析

## 当前实现

### TaskPanel（抽屉）中的状态显示

**位置**：`kat_rec_web/frontend/components/mcrb/TaskPanel.tsx` 第 326-327 行

```typescript
{hasAudio(event) ? (
  <div className="text-xs text-green-400">✓ 已生成 {event.assets.timeline_csv ? '(含时间轴)' : ''}</div>
) : (
  <div className="text-xs text-dark-text-muted">未生成</div>
)}
```

**实现逻辑**：
1. 使用 `hasAudio(event)` 判断是否显示"✓ 已生成"
2. `hasAudio` 函数（`kat_rec_web/frontend/utils/assetUtils.ts` 第 19-21 行）：
   ```typescript
   export function hasAudio(event: ScheduleEvent): boolean {
     return event.audio_exists ?? !!event.assets.audio
   }
   ```
3. 如果 `hasAudio` 返回 `true`，显示"✓ 已生成"
4. 如果 `event.assets.timeline_csv` 存在，额外显示"(含时间轴)"

### 问题分析

**当前行为**：
- `hasAudio(event)` 只检查 `audio` 路径是否存在
- 当 `audio` 文件生成但 `timeline_csv` 还没生成时：
  - `hasAudio(event)` 返回 `true`
  - 显示"✓ 已生成"（**不准确**，因为音频合成还未完成）
- 只有当 `timeline_csv` 也存在时：
  - 显示"✓ 已生成 (含时间轴)"（**准确**，表示音频合成已完成）

**问题根源**：
- `hasAudio` 函数只检查音频文件是否存在，不检查 `timeline_csv`
- 这与 `calculateStageStatus` 中的 `isAudioMixed` 函数不一致

### GridProgressIndicator 的状态计算

**位置**：`kat_rec_web/frontend/stores/scheduleStore.ts` 第 821-844 行

```typescript
const isAudioMixed = (
  audioPath: string | null | undefined,
  timelineCsv?: string | null | undefined
): boolean => {
  if (!audioPath) return false
  
  // ✅ 严格要求：必须有 timeline_csv 才认为完成
  if (
    timelineCsv &&
    (timelineCsv.includes('_full_mix_timeline.csv') ||
      timelineCsv.endsWith('_full_mix_timeline.csv'))
  ) {
    return (
      audioPath.includes('_full_mix.mp3') || 
      audioPath.endsWith('_full_mix.mp3')
    )
  }
  
  return false
}
```

**GridProgressIndicator 使用**：
- `calculateStageStatus` 函数使用 `isAudioMixed` 来判断音频是否完成
- 严格要求必须有 `timeline_csv` 才认为完成
- 这与 TaskPanel 的显示逻辑不一致

## 改进建议

### 方案 1：统一使用 `isAudioMixed` 逻辑

**修改 `hasAudio` 函数**，使其与 `isAudioMixed` 保持一致：

```typescript
// 在 assetUtils.ts 中
export function hasAudio(event: ScheduleEvent): boolean {
  // 使用与 calculateStageStatus 相同的逻辑
  const audioPath = event.assets.audio
  const timelineCsv = event.assets.timeline_csv
  
  if (!audioPath) return false
  
  // 严格要求：必须有 timeline_csv 才认为完成
  if (
    timelineCsv &&
    (timelineCsv.includes('_full_mix_timeline.csv') ||
      timelineCsv.endsWith('_full_mix_timeline.csv'))
  ) {
    return (
      audioPath.includes('_full_mix.mp3') || 
      audioPath.endsWith('_full_mix.mp3')
    )
  }
  
  return false
}
```

**优点**：
- 与 GridProgressIndicator 的状态计算保持一致
- TaskPanel 显示的状态更准确
- 可以移除"(含时间轴)"的额外显示，因为 `hasAudio` 本身就要求 `timeline_csv`

**缺点**：
- 需要检查所有使用 `hasAudio` 的地方，确保不会破坏其他功能

### 方案 2：添加新的状态函数

**创建新的函数**来区分"音频已开始"和"音频已完成"：

```typescript
// 在 assetUtils.ts 中
export function hasAudioStarted(event: ScheduleEvent): boolean {
  return event.audio_exists ?? !!event.assets.audio
}

export function hasAudioCompleted(event: ScheduleEvent): boolean {
  const audioPath = event.assets.audio
  const timelineCsv = event.assets.timeline_csv
  
  if (!audioPath) return false
  
  if (
    timelineCsv &&
    (timelineCsv.includes('_full_mix_timeline.csv') ||
      timelineCsv.endsWith('_full_mix_timeline.csv'))
  ) {
    return (
      audioPath.includes('_full_mix.mp3') || 
      audioPath.endsWith('_full_mix.mp3')
    )
  }
  
  return false
}
```

**在 TaskPanel 中使用**：

```typescript
{hasAudioCompleted(event) ? (
  <div className="text-xs text-green-400">✓ 已生成 (含时间轴)</div>
) : hasAudioStarted(event) ? (
  <div className="text-xs text-yellow-400">⏳ 生成中...</div>
) : (
  <div className="text-xs text-dark-text-muted">未生成</div>
)}
```

**优点**：
- 可以区分"已开始"和"已完成"两种状态
- 不影响现有的 `hasAudio` 函数
- 提供更细粒度的状态显示

**缺点**：
- 需要修改 TaskPanel 的显示逻辑
- 需要决定是否在其他地方也使用这些新函数

### 方案 3：使用 `calculateStageStatus` 的结果

**在 TaskPanel 中直接使用 `calculateStageStatus` 的结果**：

```typescript
// TaskPanel 中已经有 stages 变量
const stages = useScheduleStore(
  useMemo(
    () => createStageStatusSelector(eventId, runbookState),
    [eventId, runbookState]
  ),
  areStageStatusesEqual
)

// 使用 stages.preparation.done 来判断音频是否完成
// 或者检查 stages.preparation 的详细状态
```

**优点**：
- 与 GridProgressIndicator 完全一致
- 不需要修改 `hasAudio` 函数
- 状态计算逻辑统一

**缺点**：
- 需要理解 `stages.preparation` 的详细结构
- 可能需要调整显示逻辑

## 推荐方案

**推荐使用方案 1**，因为：
1. 最简单直接
2. 与 GridProgressIndicator 的状态计算保持一致
3. 可以移除"(含时间轴)"的额外显示，因为 `hasAudio` 本身就要求 `timeline_csv`
4. 状态显示更准确

## 对齐 GridProgressIndicator

**当前状态**：
- GridProgressIndicator 使用 `calculateStageStatus` → `isAudioMixed`（严格要求 `timeline_csv`）
- TaskPanel 使用 `hasAudio`（只检查 `audio` 路径）

**对齐后**：
- 两者都使用相同的逻辑（严格要求 `timeline_csv`）
- 状态显示一致
- 用户体验更好

## 其他状态的感知

**可以应用相同的模式**：
1. **视频渲染**：检查 `render_complete_flag` 而不只是 `video_path`
2. **封面生成**：可能需要检查封面文件的完整性
3. **描述/字幕**：可能需要检查文件内容是否完整

**建议**：
- 为每个资产创建类似的严格检查函数
- 在 TaskPanel 和 GridProgressIndicator 中使用相同的逻辑
- 确保状态显示的一致性

