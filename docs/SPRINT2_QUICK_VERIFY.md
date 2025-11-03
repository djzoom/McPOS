# Sprint 2 快速验证指南

**目标**: 快速验证前端 A 已完成的工作  
**时间**: 约 10 分钟

---

## 🚀 快速验证步骤

### 1. 安装依赖（首次需要）

```bash
cd kat_rec_web/frontend
pnpm install
```

**预期结果**: 依赖安装成功，无错误

---

### 2. 启动后端 Mock API

```bash
cd kat_rec_web/backend

# 确保 Mock 模式启用
export USE_MOCK_MODE=true

# 启动服务器
uvicorn main:app --reload --port 8000
```

**预期结果**:
- 服务器启动成功
- 看到 `🔧 Mock mode enabled` 提示
- 访问 `http://localhost:8000/docs` 可以看到 Swagger UI

**验证 API**:
```bash
# 测试频道端点
curl http://localhost:8000/api/channels | jq '.[0]'

# 测试期数端点
curl http://localhost:8000/metrics/episodes | jq '.total'
```

**预期结果**: 返回 Mock 数据

---

### 3. 启动前端开发服务器

```bash
cd kat_rec_web/frontend
pnpm dev
```

**预期结果**:
- 服务器启动成功
- 访问 `http://localhost:3000` 可以看到页面

---

### 4. 浏览器功能验证

#### 4.1 总览页验证

访问 `http://localhost:3000`（默认总览页）

**检查项**:
- [ ] 页面标题 "Kat Rec Web Control Center" 显示正常
- [ ] 导航标签显示（总览/频道工作盘/资产库）
- [ ] ChannelCard 组件显示（左侧）
- [ ] UploadStatus 组件显示（右侧）
- [ ] Mission Control 区域显示：
  - [ ] 成功率卡片（显示百分比）
  - [ ] 失败任务卡片（显示数量）
  - [ ] 下次发片倒计时卡片（显示时间）
  - [ ] 队列状态卡片（显示进度条）
  - [ ] 趋势图表（显示7日趋势）

**交互测试**:
- [ ] 点击"批量重试"按钮（应有响应，即使功能未完全实现）

---

#### 4.2 频道工作盘验证

点击导航标签"频道工作盘"

**检查项**:
- [ ] Channel Workbench 组件正常显示
- [ ] 默认显示卡片视图
- [ ] 显示 10 个频道卡片（Mock 数据）
- [ ] 每个卡片显示：
  - [ ] 频道名称
  - [ ] 状态指示器（彩色圆点）
  - [ ] 下次发片时间（如果有）
  - [ ] 队列数量

**交互测试**:
- [ ] **视图切换**：点击"表格"标签，切换到表格视图
  - [ ] 表格正常显示
  - [ ] 表头显示（ID、名称、状态、下次发片、队列）
  - [ ] 数据行正确显示

- [ ] **搜索功能**：在搜索框输入"Channel"
  - [ ] 列表自动过滤
  - [ ] 只显示匹配的频道

- [ ] **密度切换**：选择不同密度模式
  - [ ] 舒适模式：卡片较大
  - [ ] 标准模式：卡片中等
  - [ ] 紧凑模式：卡片较小

- [ ] **切换回卡片视图**：点击"卡片"标签
  - [ ] 正常切换回卡片视图

---

#### 4.3 浏览器控制台检查

打开浏览器开发者工具（F12）

**检查项**:
- [ ] Console 标签无错误（红色错误信息）
- [ ] Network 标签：
  - [ ] `/api/channels` 请求成功（200）
  - [ ] `/metrics/episodes` 请求成功（200）
  - [ ] `/metrics/summary` 请求成功（200）

---

#### 4.4 响应式测试

调整浏览器窗口大小

**检查项**:
- [ ] 桌面端（≥1024px）：3列网格布局
- [ ] 平板端（768-1023px）：2列网格布局
- [ ] 移动端（<768px）：1列布局

---

### 5. TypeScript 类型检查

```bash
cd kat_rec_web/frontend
pnpm type-check
```

**预期结果**: 无类型错误

---

## ✅ 验证结果记录

### 功能验证

- [ ] 页面可正常访问
- [ ] Mission Control 正常显示
- [ ] Channel Workbench 正常显示
- [ ] 视图切换功能正常
- [ ] 搜索功能正常
- [ ] 密度调整功能正常
- [ ] 无控制台错误
- [ ] API 请求成功

### 性能验证

- [ ] 页面加载时间 < 3秒
- [ ] 组件渲染流畅
- [ ] 动画效果平滑
- [ ] 虚拟滚动正常（如频道数 > 20）

---

## 🐛 常见问题

### 问题1：依赖安装失败

**错误**: `pnpm: command not found`

**解决**:
```bash
# 安装 pnpm
npm install -g pnpm

# 或使用 npm
npm install
```

---

### 问题2：后端启动失败

**错误**: `ModuleNotFoundError: No module named 'fastapi'`

**解决**:
```bash
cd kat_rec_web/backend
pip install -r requirements.txt
```

---

### 问题3：前端启动失败

**错误**: `Cannot find module '@tanstack/react-query'`

**解决**:
```bash
cd kat_rec_web/frontend
pnpm install
```

---

### 问题4：API 请求失败（CORS 错误）

**错误**: `CORS policy: No 'Access-Control-Allow-Origin' header`

**解决**:
1. 确保后端 `.env` 中 `USE_MOCK_MODE=true`
2. 检查后端 CORS 配置
3. 重启后端服务器

---

### 问题5：组件不显示或报错

**检查**:
1. 浏览器控制台查看错误信息
2. 检查 Network 标签，确认 API 请求成功
3. 检查 React Query DevTools（如已安装）

---

## 📝 验证结论

**验证日期**: _________________  
**验证人**: _________________

### 静态检查
- ✅ 代码文件完整
- ✅ 配置文件正确
- ✅ 无语法错误

### 功能检查
- [ ] 页面正常访问
- [ ] 组件正常显示
- [ ] 交互功能正常
- [ ] API 数据正常

### 结论
- [ ] ✅ 通过
- [ ] ❌ 未通过（问题描述：_________）

---

**下次更新**: 验证完成后

