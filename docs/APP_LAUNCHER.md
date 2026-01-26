# Kat Rec Control Center - App 启动器使用指南

## 📦 什么是 App 启动器？

App 启动器是一个 macOS 应用程序包（`.app`），可以让你通过双击图标来启动整个 Kat Rec 系统，无需手动运行命令行。

## 🚀 创建 App 启动器

运行以下命令创建 App 启动器：

```bash
./scripts/create-app-bundle.sh
```

这会在项目根目录创建 `Kat Rec Control Center.app`。

## 🎯 使用方法

### 方法 1: 双击启动（推荐）

1. 在 Finder 中找到 `Kat Rec Control Center.app`
2. 双击图标启动
3. 应用会自动：
   - 启动后端服务（端口 8000）
   - 启动前端服务（端口 3000）
   - 打开浏览器到控制中心界面

### 方法 2: 从终端启动

```bash
open "Kat Rec Control Center.app"
```

### 方法 3: 添加到 Dock

1. 将 `Kat Rec Control Center.app` 拖到 Dock
2. 以后可以直接从 Dock 点击启动

## ⚙️ 前置要求

在首次使用前，请确保已安装以下依赖：

### 1. Python 虚拟环境

```bash
# 在项目根目录运行
python3 -m venv .venv311
source .venv311/bin/activate
pip install -e .[backend-full]
```

### 2. pnpm（前端包管理器）

```bash
curl -fsSL https://get.pnpm.io/install.sh | sh
```

### 3. 前端依赖

```bash
cd kat_rec_web/frontend
pnpm install
```

## 📝 日志文件

所有日志文件保存在 `.logs/` 目录：

- `backend.log` - 后端服务日志
- `frontend.log` - 前端服务日志
- `backend.pid` - 后端进程 ID
- `frontend.pid` - 前端进程 ID

## 🛑 停止服务

### 方法 1: 关闭终端窗口

如果 App 启动器打开了终端窗口，直接关闭窗口即可停止服务。

### 方法 2: 使用停止脚本

```bash
# 停止所有服务
./scripts/stop-services.sh
```

### 方法 3: 手动停止

```bash
# 停止后端
lsof -ti:8000 | xargs kill -9

# 停止前端
lsof -ti:3000 | xargs kill -9
```

## 🔧 自定义配置

如果需要修改端口或其他配置，可以编辑启动脚本：

```bash
# 编辑启动脚本
open -a TextEdit "Kat Rec Control Center.app/Contents/MacOS/Kat Rec Control Center"
```

在脚本顶部可以修改：
- `BACKEND_PORT` - 后端端口（默认 8000）
- `FRONTEND_PORT` - 前端端口（默认 3000）
- `VENV_PATH` - 虚拟环境路径（默认 `.venv311`）

## 🐛 故障排除

### 问题 1: "找不到虚拟环境"

**解决方案：**
```bash
# 创建虚拟环境
python3 -m venv .venv311
source .venv311/bin/activate
pip install -e .[backend-full]
```

### 问题 2: "未找到 pnpm"

**解决方案：**
```bash
curl -fsSL https://get.pnpm.io/install.sh | sh
# 然后重新打开终端或运行: source ~/.zshrc
```

### 问题 3: 端口已被占用

**解决方案：**
```bash
# 停止占用端口的进程
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

### 问题 4: 服务启动失败

**检查日志：**
```bash
# 查看后端日志
tail -f .logs/backend.log

# 查看前端日志
tail -f .logs/frontend.log
```

## 🎨 添加应用图标（可选）

如果你想为 App 添加自定义图标：

1. 准备一个 `.icns` 格式的图标文件
2. 将其复制到：
   ```
   Kat Rec Control Center.app/Contents/Resources/AppIcon.icns
   ```
3. 更新 `Info.plist` 中的图标引用（如果需要）

## 📦 分发 App

如果你想将 App 分享给其他人：

1. **确保所有依赖已安装**（虚拟环境、pnpm 等）
2. **压缩 App 包**：
   ```bash
   zip -r "Kat Rec Control Center.zip" "Kat Rec Control Center.app"
   ```
3. **提供安装说明**：
   - 解压 zip 文件
   - 确保已安装 Python 3.10+ 和 pnpm
   - 运行 `pip install -e .[backend-full]` 安装后端依赖
   - 运行 `cd kat_rec_web/frontend && pnpm install` 安装前端依赖
   - 双击 App 启动

## 🔄 更新 App

如果项目代码更新了，重新运行创建脚本即可：

```bash
./scripts/create-app-bundle.sh
```

这会覆盖现有的 App 包，但会保留你的自定义配置（如果有）。

## 💡 提示

- **首次启动可能较慢**：需要启动后端和前端服务，请耐心等待
- **保持终端窗口打开**：如果 App 打开了终端窗口，关闭窗口会停止服务
- **检查端口占用**：如果启动失败，可能是端口被占用，先停止旧进程
- **查看日志**：遇到问题时，查看 `.logs/` 目录下的日志文件

## 🆚 与其他启动方式的对比

| 方式 | 优点 | 缺点 |
|------|------|------|
| **App 启动器** | 一键启动，无需命令行 | 需要手动停止服务 |
| **Tauri 桌面应用** | 原生窗口，集成后端 | 需要构建，体积较大 |
| **命令行脚本** | 灵活，可自定义 | 需要打开终端 |

选择最适合你的方式！

