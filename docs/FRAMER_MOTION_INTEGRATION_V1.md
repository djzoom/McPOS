# Framer Motion Integration V1

## 概述

本文档描述了 Framer Motion 在 Kat Rec 前端系统中的集成方式。Framer Motion 作为 Tailwind CSS 动画的补充，提供更流畅的进入/退出动画和微交互，同时保持 Tailwind 的颜色和渐变动画。

---

## 集成位置

### 1. GridProgressIndicator V3

**文件**: `frontend/components/mcrb/GridProgressIndicatorV3.tsx`

**功能**:
- Staggered children transition：Asset → Upload → Verify 管道线按顺序动画
- 容器级别的淡入动画
- 支持 reduced-motion

**实现**:
```typescript
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: STAGGER_DELAY,
      delayChildren: 0,
    },
  },
}
```

---

### 2. ProgressLineV3

**文件**: `frontend/components/mcrb/ProgressLineV3.tsx`

**功能**:
- 状态切换时的进入/退出动画
- 使用 `scaleX` 实现从左到右的展开效果
- Tailwind 类控制颜色和渐变，Motion 控制 transform/opacity

**实现**:
- 每个状态映射到对应的 motion variant
- `transformOrigin: 'left'` 确保从左侧展开
- 支持 reduced-motion

---

### 3. SkeletonLineV3

**文件**: `frontend/components/mcrb/SkeletonLineV3.tsx`

**功能**:
- 淡入/淡出动画，防止状态切换时的硬弹出
- 当状态从 "undefined" 变为 "available" 时平滑过渡

**实现**:
```typescript
initial={{ opacity: 0 }}
animate={{ opacity: 1 }}
exit={{ opacity: 0 }}
```

---

### 4. FileMatrixV3

**文件**: `frontend/components/mcrb/FileMatrixV3.tsx`

**功能**:
- 行级别的淡入/滑入动画
- Staggered children 实现顺序显示
- 展开/折叠动画（在 GridProgressIndicatorV3 中处理）

**实现**:
- 容器使用 staggered children
- 每行使用 `x: -8` 到 `x: 0` 的滑入动画

---

### 5. OverviewGrid

**文件**: `frontend/components/mcrb/OverviewGrid.tsx`

**功能**:
- Episode cell 的微交互
- `whileHover={{ scale: 1.02 }}` - 悬停时轻微放大
- `whileTap={{ scale: 0.98 }}` - 点击时轻微缩小
- 无布局偏移

**实现**:
```typescript
<motion.div
  whileHover={{ scale: 1.02 }}
  whileTap={{ scale: 0.98 }}
  style={{ willChange: 'transform' }}
>
```

---

### 6. TaskPanel

**文件**: `frontend/components/mcrb/TaskPanel.tsx`

**功能**:
- 从右侧滑入动画
- 使用 AnimatePresence 处理挂载/卸载
- 淡入/淡出效果

**实现**:
```typescript
initial={{ x: 80, opacity: 0 }}
animate={{ x: 0, opacity: 1 }}
exit={{ x: 80, opacity: 0 }}
```

---

## 规范化的 Variant 名称

### Asset Pipeline Variants

| 状态 | Variant Key | 动画效果 |
|------|-------------|----------|
| INIT | `init` | scaleX: 0 → 1, opacity: 0 → 1 |
| REMIX | `remix` | scaleX: 0 → 1, opacity: 0 → 1 |
| COVER | `cover` | scaleX: 0 → 1, opacity: 0 → 1 |
| TEXT | `text` | scaleX: 0 → 1, opacity: 0 → 1 |
| RENDER | `render` | scaleX: 0 → 1, opacity: 0 → 1 |
| DONE | `done` | scaleX: 0 → 1, opacity: 0 → 1 |
| FAILED | `failed` | scaleX: 0 → 1, opacity: 0 → 1 (快速) |

### Upload Pipeline Variants

| 状态 | Variant Key | 动画效果 |
|------|-------------|----------|
| pending | `pending` | scaleX: 0 → 1, opacity: 0 → 1 |
| queued | `queued` | scaleX: 0 → 1, opacity: 0 → 1 |
| uploading | `uploading` | scaleX: 0 → 1, opacity: 0 → 1 |
| uploaded | `uploaded` | scaleX: 0 → 1, opacity: 0 → 1 |
| failed | `failed` | scaleX: 0 → 1, opacity: 0 → 1 (快速) |

### Verify Pipeline Variants

| 状态 | Variant Key | 动画效果 |
|------|-------------|----------|
| verifying | `verifying` | scaleX: 0 → 1, opacity: 0 → 1 |
| verified | `verified` | scaleX: 0 → 1, opacity: 0 → 1 |
| failed | `failed` | scaleX: 0 → 1, opacity: 0 → 1 (快速) |

---

## 性能与 Reduced-Motion 指南

### Reduced-Motion 支持

所有组件都使用 `useReducedMotion()` hook 来检测用户的偏好：

```typescript
const shouldReduceMotion = useReducedMotion()

// 在动画中使用
initial={shouldReduceMotion ? false : variant.initial}
animate={shouldReduceMotion ? {} : variant.animate}
```

当用户偏好减少动画时：
- 所有 Framer Motion 动画被禁用
- 只保留 Tailwind 颜色和静态状态
- 无闪烁或快速移动

### 性能优化

1. **使用 `willChange`**:
   ```typescript
   style={{ willChange: 'transform, opacity' }}
   ```

2. **避免动画 width**:
   - 只使用 `transform` 和 `opacity`
   - 高度动画使用 `height: 'auto'` 配合 `overflow: hidden`

3. **GPU 加速**:
   - 所有动画使用 `transform` 和 `opacity`
   - 这些属性由 GPU 加速，不会触发重排

4. **Stagger 延迟**:
   - 使用 `STAGGER_DELAY` (0.05s) 避免同时触发过多动画

---

## 如何添加新的 Motion

### 步骤 1: 定义 Variant

在 `frontend/lib/motionVariants.ts` 中添加新的 variant：

```typescript
export const newVariants: Record<'state1' | 'state2', Variants> = {
  state1: {
    initial: { opacity: 0, scaleX: 0 },
    animate: { opacity: 1, scaleX: 1 },
    exit: { opacity: 0, scaleX: 0 },
    transition: TRANSITIONS.standard,
  },
  // ...
}
```

### 步骤 2: 在组件中使用

```typescript
import { getNewVariant } from '@/lib/motionVariants'

const variant = getNewVariant(state)
return (
  <motion.div
    variants={variant}
    initial="initial"
    animate="animate"
    exit="exit"
  >
    {/* 内容 */}
  </motion.div>
)
```

### 步骤 3: 添加 Reduced-Motion 支持

```typescript
const shouldReduceMotion = useReducedMotion()

initial={shouldReduceMotion ? false : variant.initial}
animate={shouldReduceMotion ? {} : variant.animate}
```

### 规则

1. **不触碰后端**: 所有动画都是纯前端实现
2. **不创建新状态**: 只使用现有的 V3 canonical 状态集
3. **保持 Tailwind**: 颜色和渐变仍由 Tailwind 类控制
4. **只动画 transform/opacity**: 不动画 width、height（除了受控的 height: auto）

---

## 共享配置

### motion.ts

**位置**: `frontend/lib/motion.ts`

**导出**:
- `DEFAULT_EASE`: 默认缓动函数
- `DEFAULT_DURATION`: 默认动画时长
- `SPRING_CONFIG`: Spring 动画配置
- `STAGGER_DELAY`: Stagger 延迟
- `TRANSITIONS`: 预定义的过渡配置

### motionVariants.ts

**位置**: `frontend/lib/motionVariants.ts`

**导出**:
- `assetVariants`: Asset 管道 variants
- `uploadVariants`: Upload 管道 variants
- `verifyVariants`: Verify 管道 variants
- Helper 函数: `getAssetVariant`, `getUploadVariant`, `getVerifyVariant`

---

## 故障排除

### 动画不工作

1. 检查 `useReducedMotion()` 是否返回 `true`
2. 确认 variant 已正确定义
3. 检查浏览器控制台是否有错误

### 性能问题

1. 确认使用了 `willChange: 'transform, opacity'`
2. 检查是否有过多的同时动画
3. 使用 React DevTools Profiler 分析性能

### 布局偏移

1. 确保动画只使用 `transform` 和 `opacity`
2. 避免动画 `width` 或 `height`（除了受控的 `height: auto`）
3. 使用固定尺寸容器

---

## 版本历史

- **V1.0.0**: 初始集成
  - GridProgressIndicator V3 集成
  - ProgressLineV3 集成
  - SkeletonLineV3 集成
  - FileMatrixV3 集成
  - OverviewGrid 微交互
  - TaskPanel 滑入动画
  - Reduced-motion 支持

---

**最后更新**: 2025-01-XX  
**维护者**: Frontend Team

