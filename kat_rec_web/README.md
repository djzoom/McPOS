# Kat Rec Web Control Center

**Mission Control: Reality Board (MCRB)** - 从 CLI 到 Web 控制中心的完整内容生命周期管理系统

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🎯 项目简介

Kat Rec Web Control Center 是一个全栈 Web 应用，用于管理 Kat Records（及未来所有频道）的内容生命周期：从素材管理、排播计划、生成执行、上传发布到验证监控的完整流程。

### 核心特性

- ✅ **实时同步**: WebSocket 实时状态更新，< 100ms UI 响应
- ✅ **智能扫描**: 自动扫描排播表与输出目录，锁定已发布内容
- ✅ **冲突检测**: 识别重复素材、资源冲突
- ✅ **SRT 处理**: 字幕文件体检、修复（重叠/间隙/编码）
- ✅ **描述规范化**: SEO 优化、品牌合规检查
- ✅ **动态规划**: 避免重复素材的智能 Recipe 生成
- ✅ **Runbook 执行**: 一键执行混音→渲染→上传→验证全流程
- ✅ **崩溃恢复**: 支持从断点恢复执行任务
- ✅ **并发控制**: 全局 4 任务，单频道 ≤2，确保稳定性
- ✅ **监控面板**: 实时系统指标、WebSocket 健康检查

---

## 🏗️ 系统架构

### 技术栈

**后端**
- FastAPI 0.104+ (Python 3.11+)
- WebSocket 实时通信
- 原子文件写入（崩溃安全）
- 重试机制（指数退避）

**前端**
- Next.js 15 (App Router)
- React 19 + TypeScript
- Zustand 状态管理
- TanStack Query 数据缓存
- Tailwind CSS + ShadCN/UI

**部署**
- Docker Compose
- GitHub Actions CI/CD
- 支持 Mock 模式（无依赖开发）

### 目录结构

```
kat_rec_web/
├── backend/                 # FastAPI 后端
│   ├── t2r/                # T2R 核心模块
│   │   ├── routes/         # API 路由
│   │   ├── services/       # 业务逻辑
│   │   ├── utils/          # 工具函数
│   │   └── config/         # 配置文件
│   ├── core/               # 核心功能（WebSocket 管理等）
│   ├── routes/             # 通用路由
│   └── tests/              # 测试文件
│
├── frontend/               # Next.js 前端
│   ├── app/               # App Router 页面
│   │   └── (t2r)/        # T2R 专用路由
│   ├── components/        # React 组件
│   ├── stores/            # Zustand 状态
│   ├── services/          # API 客户端
│   └── hooks/             # 自定义 Hooks
│
├── docs/                   # 文档
└── scripts/               # 工具脚本
```

---

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Node.js 20+
- pnpm (推荐) 或 npm
- Docker & Docker Compose (可选)

### 1. 克隆仓库

```bash
git clone <repository-url>
cd Kat_Rec
```

### 2. 后端设置

```bash
cd kat_rec_web/backend

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 设置 USE_MOCK_MODE=false（生产模式）

# 启动后端
uvicorn main:app --reload --port 8000
```

### 3. 前端设置

```bash
cd kat_rec_web/frontend

# 安装依赖
pnpm install  # 或 npm install

# 启动开发服务器
pnpm dev  # 或 npm run dev
```

### 4. 访问应用

- 前端: http://localhost:3000
- T2R 控制台: http://localhost:3000/t2r
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

---

## 📦 Docker 部署

### 快速启动（推荐）

```bash
cd kat_rec_web

# 启动所有服务
docker compose up --build

# 后台运行
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

### 环境变量

创建 `kat_rec_web/.env` 文件：

```env
# 后端配置
USE_MOCK_MODE=false
LIBRARY_ROOT=/app/library
OUTPUT_ROOT=/app/output
CONFIG_ROOT=/app/config
DATA_ROOT=/app/data

# WebSocket 配置
WS_HEARTBEAT_INTERVAL=5
WS_TIMEOUT_SECONDS=15
LOG_LEVEL=INFO

# 前端配置
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_WS_BASE=ws://localhost:8000
```

---

## 🔧 功能模块

### 1. Channel Overview（频道概览）

- 实时频道状态监控
- 任务进度追踪
- 健康指标展示

### 2. Schedule Doctor（排播医生）

- 扫描 `schedule_master.json`
- 锁定已发布内容（≥ 2025-11-02）
- 构建 `asset_usage_index.json`
- 检测资源冲突

**API**: `POST /api/t2r/scan`

### 3. Asset Health（资产健康）

- 跟踪素材使用历史
- 检测重复使用
- 冲突报告

### 4. SRT Doctor（字幕医生）

- 检查字幕重叠/间隙
- 编码验证
- 自动修复（裁剪/位移/合并）

**API**: 
- `POST /api/t2r/srt/inspect`
- `POST /api/t2r/srt/fix`

### 5. Description Linter（描述检查）

- 品牌合规检查
- SEO 元数据注入
- CC0 标签规范化

**API**: `POST /api/t2r/desc/lint`

### 6. Plan & Run（计划与执行）

- 生成 Recipe（避免重复素材）
- 执行 Runbook（混音→渲染→上传→验证）
- 实时进度更新
- 崩溃恢复支持

**API**:
- `POST /api/episodes/plan`
- `POST /api/episodes/run`

### 7. Post-Upload Verify（上传后验证）

- YouTube 元数据验证
- 缩略图检查
- 可见性确认

**API**:
- `POST /api/upload/start`
- `GET /api/upload/status`
- `POST /api/upload/verify`

### 8. Audit Trail（审计追踪）

- 每日/每周报告生成
- 操作历史记录
- 导出（MD/CSV/JSON）

**API**: `GET /api/t2r/audit?fmt=md|csv|json`

---

## 📡 API 文档

### 健康检查

```bash
# 系统健康
curl http://localhost:8000/health

# 系统指标
curl http://localhost:8000/metrics/system

# WebSocket 健康
curl http://localhost:8000/metrics/ws-health
```

### 核心 API

#### 扫描排播表

```bash
curl -X POST http://localhost:8000/api/t2r/scan \
  -H "Content-Type: application/json"
```

响应:
```json
{
  "status": "ok",
  "summary": {
    "locked_count": 5,
    "conflicts_count": 2
  },
  "conflicts": [...]
}
```

#### 生成 Recipe

```bash
curl -X POST http://localhost:8000/api/episodes/plan \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251102",
    "avoid_duplicates": true,
    "seo_template": true
  }'
```

#### 执行 Runbook

```bash
curl -X POST http://localhost:8000/api/episodes/run \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251102",
    "stages": ["remix", "render", "upload", "verify"],
    "dry_run": false
  }'
```

### WebSocket 端点

- `ws://localhost:8000/ws/status` - 状态更新流
- `ws://localhost:8000/ws/events` - 事件流

**事件格式**:
```json
{
  "type": "t2r_scan_progress",
  "version": 123,
  "ts": "2025-11-10T12:00:00Z",
  "level": "info",
  "data": {...}
}
```

完整 API 文档: http://localhost:8000/docs

---

## 🧪 测试

### 后端测试

```bash
cd kat_rec_web/backend

# 运行所有测试
pytest -v

# 运行特定测试
pytest tests/test_resume_run.py -v

# 带覆盖率
pytest --cov=t2r --cov-report=html
```

### 验证脚本

```bash
# 完整验证
bash scripts/verify_t2r.sh

# 检查项：
# - 后端/前端文件存在性
# - API 端点响应
# - 系统指标
# - WebSocket 健康
# - 结果对比（与上次）
```

### 手动测试

```bash
# 1. 健康检查
curl http://localhost:8000/health | jq

# 2. 扫描
curl -X POST http://localhost:8000/api/t2r/scan | jq

# 3. 计划
curl -X POST http://localhost:8000/api/episodes/plan \
  -H "Content-Type: application/json" \
  -d '{"episode_id": "20251102"}' | jq

# 4. WebSocket 测试
python3 scripts/test_websocket_client.py
```

---

## 📊 性能指标

| 指标 | 目标 | 状态 |
|------|------|------|
| 后端启动时间 | < 3s | ✅ |
| WebSocket 延迟 | < 50ms | ✅ |
| Recipe I/O | < 100ms | ✅ |
| Runbook 吞吐量 | 4 并行任务 | ✅ |
| UI 更新延迟 | < 100ms | ✅ |
| 前端 prod bundle | < 100 MB | ✅ |

---

## 🔐 安全与最佳实践

### 环境变量

- 生产环境: `USE_MOCK_MODE=false`
- 开发环境: `USE_MOCK_MODE=true`（跳过 Redis/DB）

### 原子写入

所有关键文件写入使用原子操作（临时文件 + rename），确保崩溃安全。

### 重试策略

`t2r/config/retry_policy.json` 定义每个阶段的重试次数和退避策略。

### WebSocket 安全

- 心跳检测（5s 间隔）
- 空闲连接清理（15s 超时）
- 版本号去重

---

## 🛠️ 开发指南

### 添加新 API 端点

1. 在 `backend/t2r/routes/` 创建路由文件
2. 在 `backend/t2r/router.py` 注册路由
3. 实现业务逻辑在 `backend/t2r/services/`

### 添加前端组件

1. 在 `frontend/components/t2r/` 创建组件
2. 使用 Zustand store 管理状态
3. 通过 `useT2RWebSocket` hook 接收实时更新

### 修改 WebSocket 事件

1. 更新 `backend/routes/websocket.py` 中的 `generate_t2r_event`
2. 前端在 `frontend/hooks/useT2RWebSocket.ts` 处理事件

---

## 📚 文档

- [T2R 系统设计文档](docs/T2R_PRODUCTION_READY.md)
- [Sprint 5 完成总结](docs/T2R_SPRINT5_COMPLETE.md)
- [Sprint 6 硬化总结](docs/T2R_SPRINT6_COMPLETE.md)
- [前端架构设计](docs/WEB_FRONTEND_ARCHITECTURE.md)
- [状态管理设计](docs/WEB_STATE_MANAGEMENT_DESIGN.md)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发流程

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

### 代码规范

- Python: 遵循 PEP 8，使用 `black` 格式化
- TypeScript: 使用 ESLint + Prettier
- 提交信息: 使用约定式提交 (Conventional Commits)

---

## 📝 许可证

MIT License

---

## 🙏 致谢

- FastAPI 团队
- Next.js 团队
- 所有贡献者

---

## 📞 支持

- 💬 Issue: [GitHub Issues](https://github.com/your-org/kat-rec/issues)
- 📖 文档: 查看 `docs/` 目录

---

**Kat Rec Web Control Center** - 让内容管理更简单、更可靠、更高效 🚀
