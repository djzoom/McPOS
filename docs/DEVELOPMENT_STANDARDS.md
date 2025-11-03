# Kat Rec Web 开发规范

**版本**: v1.0  
**适用范围**: 前端与后端开发团队  
**最后更新**: 2025-11-10

---

## 📋 代码规范

### TypeScript 规范

#### 类型定义

- **使用严格模式**：`tsconfig.json` 中 `strict: true`
- **避免 `any`**：尽可能使用具体类型
- **类型导入**：使用 `import type` 导入仅类型

```typescript
// ✅ 正确
import type { Channel } from '@/types/channel'
import { fetchChannel } from '@/services/api'

// ❌ 错误
import { Channel } from '@/types/channel' // 如果只用于类型
```

#### 命名规范

- **组件**：PascalCase (`ChannelCard.tsx`)
- **Hook**：camelCase 以 `use` 开头 (`useChannel.ts`)
- **工具函数**：camelCase (`formatDate.ts`)
- **常量**：UPPER_SNAKE_CASE (`MAX_CHANNELS`)
- **类型/接口**：PascalCase (`interface ChannelData`)

#### 组件结构

```typescript
// 1. 导入（分组）
import { useState } from 'react' // React
import { useQuery } from '@tanstack/react-query' // 第三方库
import { ChannelCard } from '@/components' // 本地组件
import type { Channel } from '@/types' // 类型

// 2. 类型定义
interface ChannelListProps {
  channels: Channel[]
  onSelect?: (channel: Channel) => void
}

// 3. 组件实现
export function ChannelList({ channels, onSelect }: ChannelListProps) {
  // Hooks
  const [selected, setSelected] = useState<Channel | null>(null)
  
  // 事件处理
  const handleSelect = (channel: Channel) => {
    setSelected(channel)
    onSelect?.(channel)
  }
  
  // 渲染
  return (
    <div>
      {channels.map(channel => (
        <ChannelCard key={channel.id} channel={channel} />
      ))}
    </div>
  )
}
```

---

### ESLint 规范

配置文件：`.eslintrc.json`

**关键规则**：
- 使用 Next.js 推荐规则
- 与 Prettier 集成（避免冲突）
- 未使用变量以 `_` 前缀忽略

```typescript
// ✅ 允许未使用的参数
const handler = (_event: Event) => {
  // 参数未使用但需要匹配类型
}
```

---

### Prettier 规范

配置文件：`.prettierrc`

**格式化规则**：
- 单引号
- 无分号
- 2 空格缩进
- 100 字符行宽
- Tailwind CSS 类排序（自动）

```bash
# 格式化所有文件
pnpm format

# 检查格式（CI 使用）
pnpm format:check
```

---

## 📁 文件组织

### 目录结构

```
frontend/
├── app/              # Next.js 路由（App Router）
│   ├── (dashboard)/  # 路由组
│   └── layout.tsx    # 布局组件
│
├── components/        # UI 组件
│   ├── ui/           # ShadCN 基础组件
│   └── [Feature]/    # 功能组件（按功能分组）
│
├── stores/           # Zustand 状态
├── services/         # API 服务层
├── hooks/            # 自定义 Hook
├── utils/            # 工具函数
└── types/            # TypeScript 类型定义
```

### 文件命名

- **组件文件**：PascalCase (`ChannelCard.tsx`)
- **工具文件**：camelCase (`formatDate.ts`)
- **类型文件**：camelCase (`channel.ts`)
- **配置文件**：kebab-case (`.eslintrc.json`)

---

## 🔄 Git 工作流

### 分支策略

- **主分支**：`main`（生产环境）
- **开发分支**：`develop`（集成测试）
- **功能分支**：`feature/模块名`（如 `feature/mission-control`）
- **修复分支**：`fix/问题描述`
- **热修复分支**：`hotfix/问题描述`

### 提交信息规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型（type）**：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具变更

**示例**：
```
feat(mission-control): 添加成功率指标卡片

实现了 Mission Control 中的成功率显示，包括：
- 成功率计算逻辑
- 趋势图表展示
- 刷新功能

Closes #123
```

### 提交前检查

Husky 自动运行：
1. ESLint 检查与自动修复
2. Prettier 格式化
3. TypeScript 类型检查（可选）

---

## 🧪 测试规范

### 单元测试

**工具**：Vitest + React Testing Library

**文件位置**：`__tests__/` 或 `*.test.tsx`

**示例**：
```typescript
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ChannelCard } from '@/components/ChannelCard'

describe('ChannelCard', () => {
  it('renders channel name', () => {
    render(<ChannelCard channel={{ id: '1', name: 'Test' }} />)
    expect(screen.getByText('Test')).toBeInTheDocument()
  })
})
```

### E2E 测试

**工具**：Playwright

**文件位置**：`tests/e2e/`

**示例**：
```typescript
import { test, expect } from '@playwright/test'

test('dashboard loads', async ({ page }) => {
  await page.goto('http://localhost:3000')
  await expect(page.locator('h1')).toContainText('Kat Rec')
})
```

---

## 🎨 样式规范

### Tailwind CSS 使用

**优先使用 Tailwind 工具类**：
```tsx
// ✅ 正确
<div className="flex items-center gap-4 p-6 bg-dark-card rounded-lg">

// ❌ 避免（除非必要）
<div className="custom-class">
```

**CSS 变量用于主题**：
```css
/* ✅ 使用 CSS 变量 */
background-color: var(--bg-primary);

/* ❌ 避免硬编码 */
background-color: #1a1a1a;
```

### 响应式设计

**移动优先**：
```tsx
<div className="
  grid 
  grid-cols-1      // 移动端：1列
  md:grid-cols-2  // 平板：2列
  lg:grid-cols-3  // 桌面：3列
">
```

### 组件样式

**使用 `@layer components`**：
```css
@layer components {
  .card {
    @apply bg-dark-card rounded-lg border border-dark-border p-6;
  }
}
```

---

## 🔌 API 规范

### 请求封装

**统一使用 `apiClient`**：
```typescript
import { apiClient } from '@/services/apiClient'

// ✅ 正确
const data = await apiClient.get<Channel[]>('/api/channels')

// ❌ 避免直接使用 fetch
const response = await fetch('/api/channels')
```

### 错误处理

**统一错误处理**：
```typescript
try {
  const data = await apiClient.get('/api/channels')
  return data
} catch (error) {
  console.error('Failed to fetch channels:', error)
  toast.error('获取频道列表失败')
  throw error
}
```

### Mock 数据

**开发环境使用 Mock**：
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 开发环境可以切换到 Mock 端点
const MOCK_MODE = process.env.NEXT_PUBLIC_USE_MOCK === 'true'
const baseURL = MOCK_MODE ? `${API_URL}/mock` : API_URL
```

---

## 📝 文档规范

### 代码注释

**组件文档**：
```typescript
/**
 * ChannelCard 组件
 * 
 * 显示单个频道的信息卡片，包括状态、下次发片时间等。
 * 
 * @param channel - 频道数据对象
 * @param onSelect - 选择频道时的回调函数（可选）
 * @param density - 显示密度模式（可选）
 */
export function ChannelCard({ 
  channel, 
  onSelect, 
  density = 'comfortable' 
}: ChannelCardProps) {
  // ...
}
```

**复杂逻辑注释**：
```typescript
// 计算成功率：已完成 / (已完成 + 失败)
// 注意：不包含进行中的任务
const successRate = completed / (completed + failed) * 100
```

### README 文件

每个主要模块应该有 README：
- 功能说明
- 使用方法
- 依赖关系
- 示例代码

---

## 🚀 性能规范

### 代码分割

**使用动态导入**：
```typescript
// ✅ 懒加载大型组件
const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
  loading: () => <Skeleton />,
})

// ❌ 避免直接导入
import { HeavyComponent } from './HeavyComponent'
```

### 图片优化

**使用 Next.js Image**：
```tsx
import Image from 'next/image'

// ✅ 正确
<Image src="/logo.png" alt="Logo" width={200} height={200} />

// ❌ 避免
<img src="/logo.png" alt="Logo" />
```

### 状态管理

**合理使用 Zustand 选择器**：
```typescript
// ✅ 只订阅需要的状态
const channel = useChannelStore(state => state.channels.find(ch => ch.id === id))

// ❌ 避免订阅整个 store
const { channels } = useChannelStore() // 会导致不必要的重渲染
```

---

## 🐛 调试规范

### 日志规范

**使用 console 日志等级**：
```typescript
// ✅ 开发调试
console.log('Channel data:', channel) // 信息
console.warn('Deprecated API used') // 警告
console.error('Failed to load:', error) // 错误

// 生产环境使用 Sentry
if (process.env.NODE_ENV === 'production') {
  Sentry.captureException(error)
}
```

### 断点调试

**使用 VS Code 调试**：
`.vscode/launch.json` 配置调试环境

---

## ✅ 代码审查清单

### 提交前自查

- [ ] 代码通过 ESLint 检查
- [ ] 代码通过 Prettier 格式化
- [ ] TypeScript 类型检查通过
- [ ] 单元测试通过（如有）
- [ ] 提交信息符合规范
- [ ] 无 console.log（提交前删除调试日志）
- [ ] 无硬编码配置（使用环境变量）

### PR 审查重点

- **功能完整性**：功能是否完整实现
- **代码质量**：是否遵循规范
- **性能影响**：是否有性能问题
- **测试覆盖**：是否有足够测试
- **文档更新**：是否需要更新文档

---

## 📚 参考资源

- [Next.js 文档](https://nextjs.org/docs)
- [TypeScript 手册](https://www.typescriptlang.org/docs/)
- [Tailwind CSS 文档](https://tailwindcss.com/docs)
- [React Query 文档](https://tanstack.com/query/latest)
- [Zustand 文档](https://zustand-demo.pmnd.rs/)

---

**文档维护**: 本文档应随团队实践持续更新。  
**问题反馈**: 如有规范疑问，请联系技术负责人。

