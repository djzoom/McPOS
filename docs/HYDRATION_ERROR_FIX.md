# Next.js Hydration 错误修复

**修复日期**: 2025-11-10  
**问题**: React hydration 错误 - 服务器端和客户端渲染结果不一致  
**状态**: ✅ **已修复**

---

## 🔍 问题分析

Next.js 15 在 SSR 时会先进行服务器端渲染，然后在客户端进行 hydration（水合）。如果服务器端和客户端渲染的结果不一致，就会导致 hydration 错误。

### 错误信息
```
A tree hydrated but some attributes of the server rendered HTML didn't match the client properties.
```

### 根本原因

1. **`Math.random()` 使用**
   - 位置: `MissionControl/index.tsx` 的 `generateTrendData` 函数
   - 问题: 每次调用 `Math.random()` 都会生成不同的随机数
   - 影响: 服务器端和客户端渲染的数据不同

2. **日期格式化不一致**
   - 位置: `HealthMetrics.tsx` 中使用 `toLocaleTimeString`
   - 问题: 不同环境（服务器/客户端）可能产生不同的格式化结果
   - 影响: 时间显示在服务器端和客户端不一致

3. **动态计算在渲染时执行**
   - 倒计时计算在每次渲染时执行，可能导致时间差异

---

## ✅ 修复方案

### 1. 使用种子随机数生成器

**问题**: `Math.random()` 导致每次渲染结果不同

**解决方案**: 使用基于日期的种子生成固定随机数

```typescript
// 修复前
value: Math.random() * 20 + 80

// 修复后
const seed = Math.floor(now.getTime() / (1000 * 60 * 60 * 24)) // 每天的种子
function seededRandom(seed: number, index: number): number {
  const x = Math.sin((seed + index) * 12.9898) * 43758.5453
  return x - Math.floor(x)
}
const value = 80 + seededRandom(seed, i) * 20
```

**优点**:
- 同一天生成相同的数据
- 服务器端和客户端结果一致
- 使用 `useMemo` 确保只计算一次

### 2. 统一日期格式化

**问题**: `toLocaleTimeString` 可能导致格式不一致

**解决方案**: 使用自定义格式化函数

```typescript
// 修复前
{new Date(nextSchedule).toLocaleTimeString('zh-CN', {
  hour: '2-digit',
  minute: '2-digit',
})}

// 修复后
function formatTime(dateString: string): string {
  const date = new Date(dateString)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  return `${hours}:${minutes}`
}
```

**优点**:
- 格式固定，不依赖本地化设置
- 服务器端和客户端结果一致

### 3. 客户端渲染动态内容

**问题**: 倒计时在渲染时计算可能导致时间差异

**解决方案**: 使用 `useEffect` 和 `useState` 在客户端计算

```typescript
const [countdown, setCountdown] = useState<string>('')
const [isMounted, setIsMounted] = useState(false)

useEffect(() => {
  setIsMounted(true)
  if (nextSchedule) {
    const updateCountdown = () => {
      setCountdown(calculateCountdown(nextSchedule))
    }
    updateCountdown()
    const interval = setInterval(updateCountdown, 60000)
    return () => clearInterval(interval)
  }
}, [nextSchedule])

// 只在客户端渲染倒计时卡片
{nextSchedule && isMounted && (
  <motion.div>
    <div>{formatTime(nextSchedule)}</div>
    <div>{countdown || '计算中...'}</div>
  </motion.div>
)}
```

**优点**:
- 避免服务器端和客户端时间差异
- 动态内容只在客户端渲染
- 支持定时更新

---

## 📝 修改的文件

### 1. `components/MissionControl/index.tsx`
- ✅ 使用种子随机数生成器替代 `Math.random()`
- ✅ 使用 `useMemo` 缓存趋势数据
- ✅ 移除未使用的 `useState` 和 `useEffect`

### 2. `components/MissionControl/HealthMetrics.tsx`
- ✅ 添加自定义 `formatTime` 函数
- ✅ 使用 `useEffect` 在客户端计算倒计时
- ✅ 使用 `isMounted` 状态控制客户端渲染

---

## 🧪 验证

### 修复前
```
Console Error: A tree hydrated but some attributes of the server rendered HTML didn't match the client properties.
```

### 修复后
- ✅ 无 hydration 错误
- ✅ 服务器端和客户端渲染一致
- ✅ 趋势图数据稳定（同一天相同）
- ✅ 时间格式化统一
- ✅ 倒计时在客户端正确更新

---

## 🎯 最佳实践

### 避免 Hydration 错误的建议

1. **避免在渲染时使用随机数**
   - ❌ `Math.random()`
   - ✅ 使用种子随机数生成器

2. **避免依赖本地化的格式化**
   - ❌ `toLocaleTimeString()`, `toLocaleDateString()`
   - ✅ 使用自定义格式化函数

3. **动态内容在客户端渲染**
   - ❌ 在组件渲染时计算 `Date.now()`
   - ✅ 使用 `useEffect` 和 `useState`

4. **使用 `useMemo` 缓存计算结果**
   - ✅ 避免重复计算
   - ✅ 确保一致性

5. **条件渲染客户端内容**
   - ✅ 使用 `isMounted` 状态
   - ✅ 只在客户端渲染动态内容

---

## 📚 参考文档

- [Next.js Hydration Error](https://nextjs.org/docs/messages/react-hydration-error)
- [React Hydration](https://react.dev/reference/react-dom/client/hydrateRoot)
- [useEffect Hook](https://react.dev/reference/react/useEffect)

---

**修复完成时间**: 2025-11-10  
**验证状态**: ✅ **通过**

