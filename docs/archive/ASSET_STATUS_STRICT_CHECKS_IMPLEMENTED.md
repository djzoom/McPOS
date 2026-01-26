# 资产状态严格检查实现

## 概述

实现了所有资产状态的严格检查逻辑，确保与完成检测逻辑保持一致。修复了之前"已生成"状态显示不准确的问题。

## 修复内容

### 1. 音频状态检查 (`hasAudio`)

**文件**: `kat_rec_web/frontend/utils/assetUtils.ts`

**修复前**:
```typescript
export function hasAudio(event: ScheduleEvent): boolean {
  return event.audio_exists ?? !!event.assets.audio
}
```

**修复后**:
```typescript
export function hasAudio(event: ScheduleEvent): boolean {
  const audioPath = event.assets.audio
  const timelineCsv = event.assets.timeline_csv
  
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

**新增辅助函数**:
```typescript
export function hasAudioStarted(event: ScheduleEvent): boolean {
  return event.audio_exists ?? !!event.assets.audio
}
```

**改进点**:
- 与 `scheduleStore.ts` 中的 `isAudioMixed` 逻辑完全一致
- 严格要求 `timeline_csv` 存在才认为完成
- 添加 `hasAudioStarted` 用于显示"生成中"状态

### 2. 视频状态检查 (`hasVideo`)

**文件**: `kat_rec_web/frontend/utils/assetUtils.ts`

**新增函数**:
```typescript
export function hasVideo(event: ScheduleEvent): boolean {
  // ✅ 严格要求：必须有 render_complete_flag 才认为完成
  return !!(
    (event.assets.video || event.assets.video_path) &&
    event.assets.render_complete_flag
  )
}

export function hasVideoStarted(event: ScheduleEvent): boolean {
  return !!(event.assets.video || event.assets.video_path)
}
```

**改进点**:
- 与 `scheduleStore.ts` 中的 `renderDone` 逻辑完全一致
- 严格要求 `render_complete_flag` 存在才认为完成
- 添加 `hasVideoStarted` 用于显示"渲染中"状态

### 3. 封面、描述、字幕状态检查

**文件**: `kat_rec_web/frontend/utils/assetUtils.ts`

**当前实现**:
- `hasCover`: 检查 `cover_exists` 标志或 `cover` 路径
- `hasDescription`: 检查 `description_exists` 标志或 `description` 路径
- `hasCaptions`: 检查 `captions_exists` 标志或 `captions` 路径

**说明**:
- 这些资产通常是文本文件或图片文件，生成过程是原子的
- 文件路径存在通常意味着文件已完整生成
- 如果需要更严格的检查，可以在后端添加类似的标志文件

### 4. TaskPanel 状态显示更新

**文件**: `kat_rec_web/frontend/components/mcrb/TaskPanel.tsx`

**音频状态显示**:
```typescript
{hasAudio(event) ? (
  <div className="text-xs text-green-400">✓ 已生成 (含时间轴)</div>
) : hasAudioStarted(event) ? (
  <div className="text-xs text-yellow-400">⏳ 生成中...</div>
) : (
  <div className="text-xs text-dark-text-muted">未生成</div>
)}
```

**视频状态显示** (新增):
```typescript
{hasVideo(event) ? (
  <div className="text-xs text-green-400">✓ 已生成 (已验证)</div>
) : hasVideoStarted(event) ? (
  <div className="text-xs text-yellow-400">⏳ 渲染中...</div>
) : (
  <div className="text-xs text-dark-text-muted">未生成</div>
)}
```

**改进点**:
- 移除了"(含时间轴)"的条件显示，因为 `hasAudio` 本身就要求 `timeline_csv`
- 添加了"生成中"状态，区分"已开始"和"已完成"
- 新增了视频状态显示，与音频状态显示保持一致

## 对齐 GridProgressIndicator

### 状态计算一致性

所有资产状态检查函数现在与 `calculateStageStatus` 中的逻辑完全一致：

1. **音频**: `hasAudio` ↔ `isAudioMixed` (都要求 `timeline_csv`)
2. **视频**: `hasVideo` ↔ `renderDone` (都要求 `render_complete_flag`)
3. **封面/描述/字幕**: 使用 `*_exists` 标志或路径检查

### 状态显示一致性

- **TaskPanel**: 使用 `hasAudio`, `hasVideo` 等函数
- **GridProgressIndicator**: 使用 `calculateStageStatus` 的结果
- **两者现在完全一致**

## 测试建议

1. **音频状态测试**:
   - 当 `audio` 文件存在但 `timeline_csv` 不存在时，应显示"⏳ 生成中..."
   - 当两者都存在时，应显示"✓ 已生成 (含时间轴)"

2. **视频状态测试**:
   - 当 `video` 文件存在但 `render_complete_flag` 不存在时，应显示"⏳ 渲染中..."
   - 当两者都存在时，应显示"✓ 已生成 (已验证)"

3. **GridProgressIndicator 对齐测试**:
   - TaskPanel 中的状态应与 GridProgressIndicator 中的状态一致
   - 准备阶段的完成状态应与音频状态一致
   - 渲染阶段的完成状态应与视频状态一致

## 相关文件

- `kat_rec_web/frontend/utils/assetUtils.ts` - 资产状态检查函数
- `kat_rec_web/frontend/components/mcrb/TaskPanel.tsx` - 抽屉状态显示
- `kat_rec_web/frontend/stores/scheduleStore.ts` - 阶段状态计算
- `kat_rec_web/frontend/utils/progressCalculators.ts` - 进度计算（使用资产检查函数）

## 修复日期

2025-01-XX

