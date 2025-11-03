# Sprint 2 任务清单

**Sprint**: Week 3–6  
**目标**: 完成五大核心模块的 UI 与逻辑

---

## 📋 任务列表

### 前端 A：Channel Workbench + Mission Control

#### ✅ Channel Workbench
- [ ] 创建组件目录结构
- [ ] 实现 ChannelCard 组件（卡片视图）
- [ ] 实现 ChannelTable 组件（紧凑表视图）
- [ ] 实现 ViewControls 组件（视图切换、搜索、密度控制）
- [ ] 实现主组件（集成卡片/表格视图）
- [ ] 集成 React Query 数据获取
- [ ] 添加虚拟滚动支持（>20频道）
- [ ] 添加状态切换动画
- [ ] 单元测试

#### ✅ Mission Control
- [ ] 创建组件目录结构
- [ ] 实现 HealthMetrics 组件（成功率、失败数、倒计时）
- [ ] 实现 QueueStatus 组件（队列容量）
- [ ] 实现 TrendChart 组件（7日趋势图，使用 Recharts）
- [ ] 实现主组件（集成所有子组件）
- [ ] 数据聚合逻辑（计算成功率、失败数等）
- [ ] 集成 React Query 数据获取
- [ ] 添加刷新功能
- [ ] 单元测试

---

### 前端 B：Ops Queue + Timeline + Alerts

#### ✅ Ops Queue
- [ ] 创建组件目录结构
- [ ] 实现 QueueTable 组件（使用 TanStack Table）
- [ ] 实现 BatchActions 组件（批量操作菜单）
- [ ] 实现 PrioritySelector 组件（优先级调整）
- [ ] 实现主组件（集成表格和操作）
- [ ] 拖拽排序功能（优先级调整）
- [ ] 批量操作功能（重试、暂停、删除）
- [ ] 状态动画（Framer Motion）
- [ ] 集成 React Query 数据获取
- [ ] 单元测试

#### ✅ Timeline
- [ ] 创建组件目录结构
- [ ] 实现 TimelineView 组件（时间轴可视化）
- [ ] 实现 EpisodeCard 组件（期数卡片）
- [ ] 实现 ConflictDetector 组件（冲突检测）
- [ ] 实现主组件（集成时间轴和冲突检测）
- [ ] 拖拽改期功能
- [ ] 冲突检测逻辑
- [ ] 拥堵预警
- [ ] 集成 React Query 数据获取
- [ ] 单元测试

#### ✅ Alerts Panel
- [ ] 创建组件目录结构
- [ ] 实现 AlertList 组件（告警列表）
- [ ] 实现 AlertBadge 组件（未读徽章）
- [ ] 集成 react-hot-toast（或自建 Toast 组件）
- [ ] 实现主组件（集成列表和徽章）
- [ ] 告警确认功能
- [ ] Toast 通知集成
- [ ] 未读计数逻辑
- [ ] 集成 React Query 数据获取
- [ ] 单元测试

---

### 设计：Figma 高保真样稿

#### ✅ 设计稿交付
- [ ] Mission Control 完整页面设计稿
- [ ] Channel Workbench 卡片视图设计稿
- [ ] Channel Workbench 表格视图设计稿
- [ ] Ops Queue 表格视图设计稿
- [ ] Timeline 时间轴视图设计稿
- [ ] Alerts Panel 告警列表设计稿
- [ ] 组件状态图（loading、error、empty、normal）
- [ ] 交互状态图（hover、active、disabled）
- [ ] 响应式设计（桌面、平板、移动端）

---

### 后端 B：API 补全

#### ✅ Metrics 端点
- [ ] 完善 `/metrics/summary` 端点
  - [ ] 从 schedule_master.json 读取数据
  - [ ] 计算全局状态统计
  - [ ] 计算各阶段耗时统计
  - [ ] 返回趋势数据（7日）
- [ ] 完善 `/metrics/episodes` 端点
  - [ ] 支持状态筛选（query参数）
  - [ ] 支持分页（limit参数）
  - [ ] 从 schedule_master.json 读取数据
- [ ] 实现 `/metrics/events` 端点
  - [ ] 从日志或数据库读取事件
  - [ ] 支持时间筛选（since参数）
  - [ ] 支持数量限制（limit参数）

#### ✅ Library 端点增强
- [ ] 增强 `/api/library/songs` 端点
  - [ ] 支持搜索功能（search参数）
  - [ ] 支持分页（limit参数）
  - [ ] 返回数据格式化
- [ ] 增强 `/api/library/images` 端点
  - [ ] 支持搜索功能（search参数）
  - [ ] 支持分页（limit参数）
  - [ ] 返回数据格式化

---

### 集成与测试

#### ✅ React Query 集成
- [ ] 创建 QueryClient Provider
- [ ] 在 layout 中集成 Provider
- [ ] 配置全局缓存策略
- [ ] 实现数据刷新机制

#### ✅ E2E 测试
- [ ] 设置 Playwright
- [ ] 编写 Channel Workbench E2E 测试
- [ ] 编写 Mission Control E2E 测试
- [ ] 编写 Ops Queue E2E 测试
- [ ] 编写 Timeline E2E 测试
- [ ] 编写 Alerts Panel E2E 测试

---

## 📅 时间安排

| 周次 | 主要任务 | 负责人 |
|------|---------|--------|
| **Week 3** | Channel Workbench + Mission Control 基础实现 | 前端 A |
| **Week 3** | Ops Queue 基础实现 | 前端 B |
| **Week 4** | Timeline + Alerts 基础实现 | 前端 B |
| **Week 4** | API 端点补全 + 设计稿交付 | 后端 B + 设计 |
| **Week 5** | React Query 集成 + 数据同步 | 前端 A + B |
| **Week 5** | 样式调整（对照设计稿） | 前端 A + B + 设计 |
| **Week 6** | E2E 测试 + 优化 + 验收 | 全员 |

---

## ✅ 验收标准

### 功能验收
- [ ] 五个模块能独立加载与交互
- [ ] Mock API 数据同步正常
- [ ] 各模块样式符合设计稿
- [ ] 基础 E2E 测试通过

### 代码质量
- [ ] 所有组件通过 TypeScript 类型检查
- [ ] ESLint 检查无错误
- [ ] 组件有适当的错误处理

### 性能验收
- [ ] 虚拟滚动正常工作（>20频道）
- [ ] 动画效果流畅（60fps）
- [ ] 数据加载时间 < 2s

---

## 📚 参考文档

- [Sprint 2 实施计划](./SPRINT2_IMPLEMENTATION_PLAN.md) - 详细实施步骤
- [产品设计愿景](./WEB_PRODUCT_DESIGN_VISION.md) - 设计规范
- [开发规范](./DEVELOPMENT_STANDARDS.md) - 代码规范

---

**最后更新**: 2025-11-10

