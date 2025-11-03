# Kat Rec Web Frontend

Kat Records Web Control Center 前端应用

## 🚀 快速开始

### 安装依赖

```bash
pnpm install
```

### 环境配置

复制环境变量文件：

```bash
cp .env.local.example .env.local
```

编辑 `.env.local`，设置后端 API URL：

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 开发服务器

```bash
pnpm dev
```

访问 [http://localhost:3000](http://localhost:3000)

### 代码检查

```bash
# ESLint
pnpm lint
pnpm lint:fix

# Prettier
pnpm format
pnpm format:check

# TypeScript
pnpm type-check
```

## 📁 项目结构

```
frontend/
├── app/              # Next.js App Router
├── components/       # React 组件
├── stores/           # Zustand 状态管理
├── services/         # API 服务层
├── hooks/            # 自定义 Hook
├── utils/            # 工具函数
└── types/            # TypeScript 类型定义
```

## 🛠️ 技术栈

- **框架**: Next.js 15 + React 19
- **语言**: TypeScript
- **样式**: Tailwind CSS
- **状态管理**: Zustand + React Query
- **代码规范**: ESLint + Prettier + Husky

## 📚 相关文档

- [开发规范](../docs/DEVELOPMENT_STANDARDS.md)
- [Sprint 1 设置指南](../docs/SPRINT1_SETUP_GUIDE.md)
- [开发路线图](../docs/WEB_DEVELOPMENT_ROADMAP.md)

