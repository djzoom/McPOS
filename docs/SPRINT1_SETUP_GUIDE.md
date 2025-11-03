# Sprint 1 设置指南

**版本**: v1.0  
**目标**: 完成 Next.js 环境与开发脚手架，接通后端 Mock 数据  
**最后更新**: 2025-11-10

---

## 🎯 Sprint 1 验收条件

- ✅ `localhost:3000` 页面可运行
- ✅ 主框架与 Mock 数据正常渲染
- ✅ 项目通过 lint 与 type check

---

## 📋 快速开始

### 前置要求

- Node.js 20+ 和 pnpm（推荐）或 npm
- Python 3.11+（后端）
- Git

### 1. 前端环境初始化

```bash
cd kat_rec_web/frontend

# 安装依赖
pnpm install

# 初始化 Husky
pnpm prepare

# 复制环境变量文件
cp .env.local.example .env.local

# 启动开发服务器
pnpm dev
```

访问 `http://localhost:3000` 应该可以看到页面。

### 2. 后端 Mock API 启动

```bash
cd kat_rec_web/backend

# 创建虚拟环境（如果还没有）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量文件
cp .env.example .env

# 确保 USE_MOCK_MODE=true
echo "USE_MOCK_MODE=true" >> .env

# 启动 FastAPI 服务器
uvicorn main:app --reload --port 8000
```

后端应该在 `http://localhost:8000` 运行。

### 3. 验证连接

**测试后端 Mock API**：
```bash
# 测试歌曲列表
curl http://localhost:8000/api/library/songs

# 测试图片列表
curl http://localhost:8000/api/library/images

# 测试期数列表
curl http://localhost:8000/metrics/episodes
```

**测试前端页面**：
访问 `http://localhost:3000`，检查浏览器控制台无 CORS 错误。

---

## 🛠️ 开发工具配置

### ESLint

配置文件：`.eslintrc.json`

```bash
# 检查代码
pnpm lint

# 自动修复
pnpm lint:fix
```

### Prettier

配置文件：`.prettierrc`

```bash
# 格式化代码
pnpm format

# 检查格式
pnpm format:check
```

### TypeScript

```bash
# 类型检查
pnpm type-check
```

### Husky Git Hooks

Git 提交前自动运行 lint-staged：

- 自动修复 ESLint 问题
- 自动格式化 Prettier
- 确保代码质量

---

## 📁 目录结构

```
kat_rec_web/
├── frontend/
│   ├── app/              # Next.js App Router
│   ├── components/       # React 组件
│   ├── services/         # API 服务
│   ├── styles/           # 样式文件
│   └── .env.local        # 环境变量（不提交）
│
└── backend/
    ├── routes/           # FastAPI 路由
    │   └── mock.py       # Mock API 端点
    ├── services/         # 业务逻辑
    └── .env              # 环境变量（不提交）
```

---

## 🎨 主题配置

### CSS 变量

主题变量定义在 `app/globals.css`：

```css
:root {
  --color-primary: #4a9eff;
  --color-success: #4ade80;
  --color-error: #f87171;
  --bg-primary: #1a1a1a;
  --text-primary: #e0e0e0;
  /* ... */
}
```

### Tailwind 配置

Tailwind 配置在 `tailwind.config.js`，使用 CSS 变量：

```javascript
colors: {
  primary: 'var(--color-primary)',
  success: 'var(--color-success)',
  // ...
}
```

---

## 🔌 Mock API 端点

### 可用端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/library/songs` | GET | 返回20条模拟歌曲数据 |
| `/api/library/images` | GET | 返回15条模拟图片数据 |
| `/metrics/episodes` | GET | 返回10条模拟期数数据 |
| `/metrics/summary` | GET | 返回模拟汇总数据 |
| `/metrics/events` | GET | 返回模拟事件流数据 |

### Mock 数据格式

**歌曲数据**：
```json
{
  "id": "song_0001",
  "filename": "track_0001.mp3",
  "file_size_bytes": 5000000,
  "discovered_at": "2025-11-01T10:00:00",
  "duration_seconds": 180
}
```

**期数数据**：
```json
{
  "episodes": [
    {
      "episode_id": "20251110",
      "episode_number": 1,
      "schedule_date": "2025-11-10",
      "status": "completed",
      "title": "Episode 1"
    }
  ],
  "total": 10
}
```

---

## 🐛 常见问题

### 问题1：CORS 错误

**症状**：浏览器控制台显示 CORS 错误

**解决**：
1. 检查后端 `.env` 中 `USE_MOCK_MODE=true`
2. 确认前端 `.env.local` 中 `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. 重启后端服务器

### 问题2：端口被占用

**症状**：`Error: listen EADDRINUSE: address already in use`

**解决**：
```bash
# 查找占用端口的进程
lsof -i :3000  # 前端
lsof -i :8000  # 后端

# 杀死进程
kill -9 <PID>
```

### 问题3：Husky 未生效

**症状**：Git 提交时没有运行 lint-staged

**解决**：
```bash
cd kat_rec_web/frontend
pnpm prepare
chmod +x .husky/pre-commit
```

### 问题4：TypeScript 类型错误

**症状**：`pnpm type-check` 报错

**解决**：
1. 确保所有依赖已安装：`pnpm install`
2. 检查 `tsconfig.json` 配置
3. 如果使用新版本 React/Next.js，可能需要更新类型定义

---

## ✅ 验收检查清单

### 前端验收

- [ ] `pnpm dev` 成功启动，无错误
- [ ] `localhost:3000` 页面可访问
- [ ] `pnpm lint` 无错误（或只有警告）
- [ ] `pnpm type-check` 通过
- [ ] `pnpm format:check` 通过
- [ ] Git 提交时 Husky 自动运行

### 后端验收

- [ ] `uvicorn main:app --reload` 成功启动
- [ ] `localhost:8000` 可访问
- [ ] `localhost:8000/docs` 显示 Swagger UI
- [ ] Mock API 端点返回数据
- [ ] 无 CORS 错误

### 集成验收

- [ ] 前端可以获取后端 Mock 数据
- [ ] 浏览器控制台无错误
- [ ] 数据正常渲染在页面上

---

## 📚 下一步

完成 Sprint 1 后，可以开始：

1. **Sprint 2**：实现核心模块（Mission Control、Channel Workbench 等）
2. 参考：[开发路线图](./WEB_DEVELOPMENT_ROADMAP.md)

---

## 📝 相关文档

- [开发路线图](./WEB_DEVELOPMENT_ROADMAP.md) - 完整开发计划
- [前端架构方案](./WEB_FRONTEND_ARCHITECTURE.md) - 技术选型
- [产品设计愿景](./WEB_PRODUCT_DESIGN_VISION.md) - 设计规范

---

**文档维护**: 本文档应随环境配置变化持续更新。  
**问题反馈**: 如有设置问题，请联系开发团队。

