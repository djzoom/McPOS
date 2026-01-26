# 快速开始指南

**最后更新**: 2025-11-16

---

## 🚀 启动方式选择

Kat Rec 支持三种启动方式，选择最适合你的：

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **App 启动器** | 一键启动，无需命令行 | 需要手动停止服务 | 日常使用 |
| **Tauri 桌面应用** | 原生窗口，集成后端，性能好 | 需要构建，体积较大 | 生产环境 |
| **命令行脚本** | 灵活，可自定义 | 需要打开终端 | 开发调试 |

---

## 📱 方式 1: App 启动器（推荐日常使用）

### 创建 App 启动器

```bash
./scripts/create-app-bundle.sh
```

这会在项目根目录创建 `Kat Rec Control Center.app`。

### 使用方法

1. **双击启动**：在 Finder 中找到 `Kat Rec Control Center.app`，双击即可
2. **从 Dock 启动**：将 App 拖到 Dock，以后可以直接点击
3. **从终端启动**：`open "Kat Rec Control Center.app"`

### 前置要求

```bash
# 1. Python 虚拟环境
python3 -m venv .venv311
source .venv311/bin/activate
pip install -e .[backend-full]

# 2. pnpm（前端包管理器）
curl -fsSL https://get.pnpm.io/install.sh | sh

# 3. 前端依赖
cd kat_rec_web/frontend
pnpm install
```

### 停止服务

```bash
# 方法 1: 关闭终端窗口（如果 App 打开了终端）
# 方法 2: 使用停止脚本
./scripts/stop-services.sh
# 方法 3: 手动停止
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

### 添加应用图标

```bash
# 如果有 icon.png (1024x1024 PNG)
make create-icon

# 然后重新创建 App
make create-app
```

详细说明请参考 [APP_LAUNCHER.md](./APP_LAUNCHER.md) 和 [ADD_ICON.md](./ADD_ICON.md)。

---

## 🖥️ 方式 2: Tauri 桌面应用（推荐生产环境）

### 构建要求

```bash
# 1. Rust 工具链
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 2. Node.js 和 pnpm
curl -fsSL https://get.pnpm.io/install.sh | sh
```

### 构建生产版本

```bash
# 一键构建（包含前端构建）
make build-tauri
```

构建完成后，在 `desktop/tauri/src-tauri/target/release/bundle/macos/` 找到应用。

### 开发模式

```bash
# 启动开发模式（自动重新加载）
make tauri-dev
```

### 优势

- ⚡ **启动速度快**：< 1 秒显示界面
- 🎨 **界面流畅**：原生窗口，60fps 动画
- 📦 **体积小**：比 Electron 小 10-20 倍
- 🔒 **安全性高**：Rust 内存安全保证

详细说明请参考 [TAURI_APP.md](./TAURI_APP.md)。

---

## 💻 方式 3: 命令行启动

### 后端启动

```bash
cd kat_rec_web/backend
source .venv/bin/activate  # 或使用项目根目录的 .venv311
uvicorn main:app --reload --port 8000
```

### 前端启动

```bash
cd kat_rec_web/frontend
pnpm install
pnpm dev
```

### 访问应用

- 前端: http://localhost:3000
- T2R 控制台: http://localhost:3000/t2r
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

---

## 🔧 故障排除

### 端口被占用

```bash
# 检查端口占用
lsof -i :8000
lsof -i :3000

# 停止占用端口的进程
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

详细说明请参考 [PORT_MANAGEMENT.md](./PORT_MANAGEMENT.md)。

### 依赖缺失

```bash
# 后端依赖
pip install -e .[backend-full]

# 前端依赖
cd kat_rec_web/frontend
pnpm install
```

### 查看日志

```bash
# 后端日志
tail -f logs/katrec.log

# 前端日志（在浏览器控制台查看）
```

---

## 📚 下一步

- 查看 [系统概览](./01_SYSTEM_OVERVIEW.md) 了解架构
- 查看 [工作流指南](./02_WORKFLOW_AND_AUTOMATION.md) 了解使用流程
- 查看 [开发指南](./03_DEVELOPMENT_GUIDE.md) 了解开发流程

---

**快速开始完成** ✅

