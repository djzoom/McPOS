# Kat Records Web 仪表板 - 交互设计与数据规范文档

## 📋 文档概述

本文档面向产品经理、交互设计师和UI设计师，详细说明Kat Records Web控制中心的交互逻辑、页面结构、数据元素及其来源。

**文档版本**: v1.0  
**更新日期**: 2025-11-10  
**适用系统**: Kat Rec Web Control Center

---

## 🏗️ 系统架构概览

### 双前端架构

系统目前存在两个前端实现：

1. **Next.js React前端** (`kat_rec_web/frontend/`) - **主要发展方向**
   - 现代化React组件架构
   - TypeScript + Tailwind CSS
   - 当前版本：Next.js 14 + React 18
   - 目标版本：Next.js 15 + React 19（详见[前端架构方案](./WEB_FRONTEND_ARCHITECTURE.md)）
   - 端口：3000（开发环境）

2. **HTML静态仪表板** (`web/dashboard/`) - **过渡方案**
   - 轻量级单页应用
   - 纯JavaScript + FastAPI后端
   - 端口：8000（FastAPI服务）
   - 注：此版本将逐步迁移至Next.js架构

### 后端服务

- **FastAPI后端** (`kat_rec_web/backend/`)
   - RESTful API服务
   - 端口：8000
   - 服务端点：`/api/*`
   - 计划支持：WebSocket实时推送（`/ws/*`）

### 架构演进路线

详见：[前端架构方案文档](./WEB_FRONTEND_ARCHITECTURE.md)

---

## 📊 仪表板主页面结构

### 页面布局（Next.js版本）

```
┌─────────────────────────────────────────────────────────┐
│  Kat Rec Web Control Center                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                   │
│  │ Channel Card │  │ Upload Status│                   │
│  └──────────────┘  └──────────────┘                   │
│                                                         │
│  ┌──────────────────────────────────────────────┐     │
│  │         Library Management Tabs              │     │
│  │  [Songs] [Images]                             │     │
│  │  ┌────────────────────────────────────┐      │     │
│  │  │  Table: Song/Image List            │      │     │
│  │  └────────────────────────────────────┘      │     │
│  └──────────────────────────────────────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 页面组件分解

#### 1. 顶部标题区域
- **元素**: `h1` 标题
- **文字内容**: "Kat Rec Web Control Center"
- **来源**: 前端硬编码 (`kat_rec_web/frontend/app/page.tsx:46`)
- **样式**: `text-4xl font-bold mb-8`

#### 2. 状态卡片区域（Grid布局）
- **布局**: `grid grid-cols-1 md:grid-cols-2 gap-6`
- **组件**: 
  - ChannelCard（左侧）
  - UploadStatus（右侧）

---

## 🎵 歌库管理（Songs Library）

### 交互逻辑

#### 标签页切换
- **当前实现**: `LibraryTabs` 组件，两个标签：`Songs` 和 `Images`
- **切换方式**: 点击标签按钮切换，URL不变化（客户端状态）
- **状态管理**: React `useState`，本地状态 `activeTab: 'songs' | 'images'`

#### 数据加载逻辑
1. **初始化**: 组件挂载时，根据 `activeTab` 自动加载对应数据
2. **切换时**: `useEffect` 监听 `activeTab` 变化，自动重新加载
3. **加载状态**: 显示 "Loading..." 文本
4. **刷新频率**: 无自动刷新，需手动切换标签触发

### 数据来源

#### API端点
- **路径**: `/api/library/songs`
- **方法**: `GET`
- **实现位置**: `kat_rec_web/backend/routes/library.py:16-25`
- **服务层**: `FileService.scan_songs()`

#### 数据扫描逻辑
```python
# 扫描目录: /app/library/songs/ (Docker) 或 /library/songs/
# 支持格式: .mp3, .flac, .wav, .m4a, .ogg
# 递归扫描: rglob("*") - 扫描所有子目录
```

#### 返回数据结构
```typescript
interface SongItem {
  id: string;              // 文件stem（不含扩展名）
  filename: string;         // 完整文件名
  filepath: string;         // 相对于library_root的路径
  file_size_bytes: number;  // 文件大小（字节）
  discovered_at: string;   // ISO 8601格式时间戳
}
```

### 前端显示

#### 表格结构
```
┌─────────────────────────────────────────────────────┐
│  Filename    │  Size      │  Discovered             │
├─────────────────────────────────────────────────────┤
│  song1.mp3   │  3.45 MB   │  2025-11-02            │
│  song2.flac  │  12.8 MB   │  2025-11-01            │
└─────────────────────────────────────────────────────┘
```

#### 字段说明

| 列名 | 显示内容 | 数据来源 | 格式化规则 |
|------|---------|---------|-----------|
| Filename | 文件名 | `song.filename` | `font-mono text-sm` |
| Size | 文件大小 | `song.file_size_bytes` | 转换为MB，保留2位小数 |
| Discovered | 发现时间 | `song.discovered_at` | ISO转本地日期格式 `toLocaleDateString()` |

#### 空状态
- **条件**: `songs.length === 0`
- **显示**: "No songs found in library"
- **样式**: `text-center py-8 text-dark-text-muted`

#### 样式细节
- **表格行**: `hover:bg-dark-border/20` （悬停效果）
- **边框**: `border-b border-dark-border/50` （行分隔线）
- **字体**: 文件名使用等宽字体 `font-mono`

---

## 🖼️ 图库管理（Images Library）

### 交互逻辑

- **与歌库共享同一组件** (`LibraryTabs`)
- **标签切换**: 点击 "Images" 标签
- **数据加载**: 切换到Images时调用 `fetchImages()`

### 数据来源

#### API端点
- **路径**: `/api/library/images`
- **方法**: `GET`
- **实现位置**: `kat_rec_web/backend/routes/library.py:28-37`
- **服务层**: `FileService.scan_images()`

#### 数据扫描逻辑
```python
# 扫描目录: /app/library/images/ (Docker) 或 /library/images/
# 支持格式: .jpg, .jpeg, .png, .webp, .gif
# 图片尺寸检测: 使用PIL库读取width和height
```

#### 返回数据结构
```typescript
interface ImageItem {
  id: string;              // 文件stem
  filename: string;         // 完整文件名
  filepath: string;         // 相对于library_root的路径
  width: number | null;     // 图片宽度（像素）
  height: number | null;    // 图片高度（像素）
  file_size_bytes: number;  // 文件大小（字节）
  discovered_at: string;   // ISO 8601格式时间戳
}
```

### 前端显示

#### 表格结构
```
┌─────────────────────────────────────────────────────────┐
│  Filename      │  Dimensions │  Size      │  Discovered   │
├─────────────────────────────────────────────────────────┤
│  image1.png    │  1920×1080  │  2.5 MB    │  2025-11-02  │
│  image2.jpg    │  N/A        │  1.2 MB    │  2025-11-01  │
└─────────────────────────────────────────────────────────┘
```

#### 字段说明

| 列名 | 显示内容 | 数据来源 | 格式化规则 |
|------|---------|---------|-----------|
| Filename | 文件名 | `image.filename` | `font-mono text-sm` |
| Dimensions | 尺寸 | `image.width` × `image.height` | 如果有尺寸显示 "width×height"，否则 "N/A" |
| Size | 文件大小 | `image.file_size_bytes` | 转换为MB，保留2位小数 |
| Discovered | 发现时间 | `image.discovered_at` | ISO转本地日期格式 |

#### 特殊处理
- **尺寸显示**: 如果 `width` 或 `height` 为 `null`，显示 "N/A"
- **尺寸格式**: `{width}×{height}` （使用乘号 ×）

---

## 📺 节目库管理（Episodes/Programs Library）

### 交互逻辑

**注意**: 节目库管理在当前Next.js前端中**未实现**，仅在HTML仪表板版本中展示。

### HTML仪表板版本（`web/dashboard/templates/dashboard.html`）

#### 数据来源

#### API端点
- **路径**: `/metrics/episodes`
- **方法**: `GET`
- **实现位置**: `web/dashboard/dashboard_server.py:201-250`
- **数据源**: `config/schedule_master.json`

#### schedule_master.json 结构

```json
{
  "created_at": "2025-11-02T14:59:39.976649",
  "start_date": "2025-11-02",
  "schedule_interval_days": 2,
  "total_episodes": 5,
  "episodes": [
    {
      "episode_number": 1,
      "schedule_date": "2025-11-02",
      "episode_id": "20251102",
      "image_path": "/path/to/image.png",
      "title": "Amber Lanterns on Quiet Streets",
      "tracks_used": ["Song1", "Song2", ...],
      "starting_track": "Song1",
      "status": "已完成",
      "youtube_video_id": "a6k-A8oQ2KA",
      "youtube_video_url": "https://www.youtube.com/watch?v=...",
      "metadata_updated_at": "2025-11-02T18:41:39.658615"
    }
  ]
}
```

#### 期数状态映射

前端显示需要将中文状态转换为英文显示：

| 原始状态（schedule_master.json） | 规范化状态（API返回） | 前端显示 |
|--------------------------------|-------------------|---------|
| 待制作 | pending | 待制作 |
| 制作中 | remixing | 制作中 |
| 上传中 | uploading | 上传中 |
| 排播完毕待播出 | uploading | 上传中 |
| 已完成 | completed | 已完成 |
| 已跳过 | pending | 待制作 |
| error | error | 失败 |

### 前端显示（HTML版本）

#### 期数列表卡片

```
┌─────────────────────────────────────────┐
│  📋 期数列表                              │
├─────────────────────────────────────────┤
│  ┌────────────────────────────────────┐  │
│  │ #20251102  [已完成]                │  │
│  │ Amber Lanterns on Quiet Streets    │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ #20251104  [已完成]                │  │
│  │ Cinnamon Dreams in the Evening... │  │
│  └────────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

#### 期数卡片结构

- **期数ID**: `episode_id` 或 `episode_number` 格式化显示
- **状态标签**: 根据状态显示不同颜色边框
  - `completed`: 绿色边框 `border-left-color: #4ade80`
  - `error`: 红色边框 `border-left-color: #f87171`
  - `pending`: 灰色边框 `border-left-color: #888`
- **标题**: `episode.title`，如果有则显示
- **恢复按钮**: 仅当 `status === 'error'` 时显示

#### 恢复功能

- **触发**: 点击"恢复"按钮
- **API调用**: `POST /api/recover/{episode_id}`
- **行为**: 将期数状态回滚到 "pending"
- **确认**: 浏览器 `confirm()` 对话框

---

## 📈 仪表板数据概览面板

### HTML仪表板版本的数据展示

#### 1. 概览卡片

| 数据项 | 数据来源 | 计算逻辑 |
|--------|---------|---------|
| 总期数 | `schedule_master.json` | `len(episodes)` |
| 已完成 | 同上 | `status === 'completed'` 的数量 |
| 失败 | 同上 | `status === 'error'` 的数量 |
| 进行中 | 同上 | `(remixing + rendering)` 的数量 |
| 成功率 | 同上 | `(completed / (completed + error)) × 100%` |

#### 2. 阶段耗时卡片

- **数据来源**: `/metrics/summary?period=24h` → `summary.stages`
- **显示**: 各阶段的平均耗时（秒）
- **阶段类型**: remixing, rendering, uploading 等

#### 3. 活跃阶段卡片

- **数据来源**: `/metrics/summary` → `global_state`
- **显示项**:
  - 混音中: `gs.remixing`
  - 渲染中: `gs.rendering`
  - 待制作: `gs.pending`

### 数据刷新逻辑

#### HTML仪表板
- **自动刷新**: 每10秒调用 `refreshDashboard()`
- **API调用**: 并行请求 `/metrics/summary`, `/metrics/episodes`, `/metrics/events`
- **刷新指示器**: 显示 "最后更新" 时间戳

#### Next.js前端
- **ChannelCard 和 UploadStatus**: 每30秒自动刷新
- **LibraryTabs**: 无自动刷新，需手动切换标签

---

## 🎨 设计规范

### 颜色系统

#### 深色主题（Next.js版本）

```css
/* 背景色 */
background: #1a1a1a (body)
card-bg: #2a2a2a

/* 文字颜色 */
primary-text: #e0e0e0
muted-text: #aaa
border: #333

/* 强调色 */
blue: #4a9eff
green: #4ade80
red: #f87171
yellow: #fbbf24
```

#### 状态颜色映射

| 状态 | 文字颜色 | 背景色 | 使用场景 |
|------|---------|--------|---------|
| 成功/已完成 | `text-green-400` | `bg-green-600/20` | ChannelCard active, UploadStatus connected |
| 错误/失败 | `text-red-400` | `bg-red-600/20` | ChannelCard inactive, UploadStatus disconnected |
| 警告/进行中 | `text-yellow-400` | `bg-yellow-600/20` | UploadStatus running |
| 活跃标签 | `text-white` | `border-b-2 border-blue-500` | LibraryTabs active tab |

### 间距系统

- **页面边距**: `p-8` (32px)
- **卡片间距**: `gap-6` (24px)
- **组件内边距**: `p-4` 或 `px-4 py-2`
- **表格行高**: `py-2` (8px vertical padding)

### 字体系统

- **标题**: `text-4xl font-bold` (主标题)
- **副标题**: `text-xl font-semibold` (卡片标题)
- **正文**: 默认字体，`text-sm` (小号文字)
- **等宽字体**: `font-mono` (文件名、ID)

### 交互反馈

#### 悬停效果
- **表格行**: `hover:bg-dark-border/20`
- **标签按钮**: `hover:text-dark-text` (非激活状态)

#### 加载状态
- **文字**: "Loading..."
- **样式**: `text-dark-text-muted text-center py-8`
- **动画**: 无（未来可考虑添加骨架屏）

---

## 📡 API端点总结

### 库管理相关

| 端点 | 方法 | 用途 | 数据来源 |
|------|------|------|---------|
| `/api/library/songs` | GET | 获取歌库列表 | `/library/songs/` 目录扫描 |
| `/api/library/images` | GET | 获取图库列表 | `/library/images/` 目录扫描 |

### 状态和频道相关

| 端点 | 方法 | 用途 | 数据来源 |
|------|------|------|---------|
| `/api/status` | GET | 系统状态 | Redis连接状态、队列长度 |
| `/api/channel` | GET | 频道信息 | 数据库（SQLite/PostgreSQL） |

### 期数管理相关（HTML仪表板）

| 端点 | 方法 | 用途 | 数据来源 |
|------|------|------|---------|
| `/metrics/episodes` | GET | 获取期数列表 | `config/schedule_master.json` |
| `/metrics/summary` | GET | 获取统计摘要 | `schedule_master.json` + 指标数据 |
| `/metrics/events` | GET | 获取事件流 | 指标管理器 |
| `/api/recover/{episode_id}` | POST | 恢复失败期数 | 更新 `schedule_master.json` |

---

## 🔄 数据流向图

### 歌库数据流

```
/library/songs/ (物理文件目录)
    ↓
FileService.scan_songs()
    ↓
/api/library/songs (FastAPI)
    ↓
fetchSongs() (前端API服务)
    ↓
LibraryTabs 组件 (React)
    ↓
表格渲染
```

### 图库数据流

```
/library/images/ (物理文件目录)
    ↓
FileService.scan_images()
    ↓ (PIL检测尺寸)
/api/library/images (FastAPI)
    ↓
fetchImages() (前端API服务)
    ↓
LibraryTabs 组件 (React)
    ↓
表格渲染
```

### 期数数据流

```
config/schedule_master.json
    ↓
StateManager 或直接读取
    ↓
/metrics/episodes (FastAPI)
    ↓ (状态规范化)
fetchEpisodes() (前端API服务)
    ↓
期数列表组件渲染
```

---

## 💡 交互设计建议

### 当前缺失的功能

1. **搜索和筛选**
   - 歌库/图库无搜索功能
   - 建议：添加文件名搜索、文件大小筛选、日期范围筛选

2. **排序功能**
   - 当前仅按文件名排序（后端）
   - 建议：支持按大小、日期排序，前端可切换

3. **分页**
   - 当前显示所有项目（可能性能问题）
   - 建议：后端分页，前端无限滚动或传统分页

4. **批量操作**
   - 无删除、移动等操作
   - 建议：选中多个项目，批量操作菜单

5. **详情视图**
   - 点击项目仅显示基本信息
   - 建议：模态框或详情页显示完整元数据

### 用户体验优化建议

1. **加载状态优化**
   - 当前仅文字 "Loading..."
   - 建议：骨架屏（Skeleton Screen）或进度条

2. **错误处理**
   - 当前错误仅在控制台输出
   - 建议：Toast通知或错误卡片

3. **数据刷新**
   - 歌库/图库无自动刷新
   - 建议：添加手动刷新按钮或自动刷新选项

4. **响应式设计**
   - 当前使用 `md:grid-cols-2`
   - 建议：优化移动端显示，考虑表格横向滚动

---

## 🎯 设计师检查清单

### 视觉设计

- [ ] 确保深色主题配色一致性
- [ ] 状态颜色符合语义（绿色=成功，红色=错误）
- [ ] 表格行悬停效果明显但不突兀
- [ ] 标签切换有明确的激活状态指示

### 交互设计

- [ ] 加载状态有视觉反馈
- [ ] 空状态有友好提示
- [ ] 错误状态有明确提示和恢复方式
- [ ] 表格内容在小屏幕上可横向滚动

### 信息架构

- [ ] 重要信息（期数、状态）优先展示
- [ ] 次要信息（文件大小、日期）适当弱化
- [ ] 操作按钮位置符合用户习惯

### 可访问性

- [ ] 颜色对比度符合WCAG标准
- [ ] 交互元素有足够的点击区域
- [ ] 表格有明确的表头
- [ ] 加载和错误状态有文字说明

---

## 📝 附录

### 文件位置索引

#### 前端代码
- **Next.js主页面**: `kat_rec_web/frontend/app/page.tsx`
- **库管理组件**: `kat_rec_web/frontend/components/LibraryTabs.tsx`
- **频道卡片**: `kat_rec_web/frontend/components/ChannelCard.tsx`
- **上传状态**: `kat_rec_web/frontend/components/UploadStatus.tsx`
- **API服务**: `kat_rec_web/frontend/services/api.ts`

#### 后端代码
- **库路由**: `kat_rec_web/backend/routes/library.py`
- **文件服务**: `kat_rec_web/backend/services/file_service.py`
- **主应用**: `kat_rec_web/backend/main.py`

#### HTML仪表板
- **HTML模板**: `web/dashboard/templates/dashboard.html`
- **仪表板服务**: `web/dashboard/dashboard_server.py`

#### 数据文件
- **排播表**: `config/schedule_master.json`
- **歌库配置**: `config/library_settings.yml`
- **歌库索引**: `data/song_library.csv`

### 相关文档

- **产品设计愿景**: `docs/WEB_PRODUCT_DESIGN_VISION.md` - 总导演式设计主张与任务优先级
- **前端架构方案**: `docs/WEB_FRONTEND_ARCHITECTURE.md` - 技术选型与架构演进
- **数据流与状态管理**: `docs/WEB_STATE_MANAGEMENT_DESIGN.md` - Zustand状态模型与数据流
- **架构文档**: `docs/ARCHITECTURE.md` - 系统整体架构
- **库管理指南**: `docs/LIBRARY_MANAGEMENT.md` - 歌库/图库管理
- **排播表指南**: `docs/SCHEDULE_MASTER_GUIDE.md` - 期数管理

---

**文档维护**: 本文档应随系统功能更新而同步更新。  
**反馈渠道**: 如有疑问或建议，请联系开发团队。

