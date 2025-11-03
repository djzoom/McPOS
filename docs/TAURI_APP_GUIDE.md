# 如何用双击启动 Kat Rec 控制中心

Kat Rec Control Center 提供了便捷的桌面应用，让你只需双击就能启动整个系统。

## 📦 首次使用

### 1. 构建桌面应用

```bash
# 确保前端已导出
cd kat_rec_web/frontend
NEXT_OUTPUT_MODE=export pnpm build

# 构建桌面应用（macOS）
cd ../../desktop/tauri
pnpm tauri build
```

构建完成后，应用位于：
```
desktop/tauri/src-tauri/target/release/bundle/macos/Kat Rec Control Center.app
```

### 2. 启动应用

#### 方式一：从构建目录启动

直接双击 `Kat Rec Control Center.app`

#### 方式二：使用命令

```bash
make app:dev
```

这会：
1. 自动启动后端 FastAPI 服务（端口 8010）
2. 等待 `/health` 端点就绪（最多 20 秒）
3. 自动打开窗口并导航到 `/t2r` 页面
4. 注入 API 和 WebSocket 基础 URL

## 🎯 应用功能

### 自动启动后端

应用会自动：
- 检测 Python 环境（优先使用 `.venv311/bin/python`）
- 在端口 8010 启动 uvicorn 服务
- 设置 `USE_MOCK_MODE=false`
- 等待后端健康检查通过

### 日志文件

后端日志保存在：
```
desktop/tauri/backend.log
```

日志会自动轮转（保留 5 个文件，每个最大 1MB）。

### 优雅关闭

关闭应用窗口时：
1. 发送 SIGTERM 信号给后端进程
2. 等待 3 秒
3. 如果进程未退出，强制 SIGKILL

## 🔧 开发模式

```bash
make app:dev
```

开发模式下：
- 会监听前端代码变化
- 自动重新加载
- 后端仍然需要手动重启（或自动重启）

## 📋 验证配置

运行验证脚本检查所有配置：

```bash
make app:verify
# 或
bash scripts/verify_app.sh
```

验证项包括：
- ✅ 前端静态导出目录存在
- ✅ Tauri 配置文件正确
- ✅ Rust 代码配置（端口 8010、USE_MOCK_MODE=false）
- ✅ 后端主文件存在
- ✅ 依赖已配置

## 🐛 故障排除

### 后端启动失败

1. **检查日志**：查看 `desktop/tauri/backend.log`
2. **检查 Python**：确保 Python 环境正确
3. **检查端口**：确保 8010 端口未被占用

```bash
# 检查端口
lsof -i :8010

# 检查 Python
which python3
python3 --version
```

### 前端页面无法加载

1. **检查导出目录**：确保 `kat_rec_web/frontend/out` 存在
2. **重新构建前端**：

```bash
cd kat_rec_web/frontend
NEXT_OUTPUT_MODE=export pnpm build
```

### 窗口无法打开

1. **检查 Tauri CLI**：

```bash
cd desktop/tauri
pnpm install
```

2. **检查系统权限**：macOS 可能需要授予应用网络权限

## 📝 技术细节

### 端口选择

应用按以下顺序尝试端口：
1. 8010（默认）
2. 8000-8010（如果 8010 被占用）

### 环境变量

应用会自动设置：
- `API_PORT`: 选择的端口号
- `USE_MOCK_MODE`: false

### 进程管理

- 后端进程由 Tauri 管理
- 进程句柄存储在全局静态变量中
- 窗口关闭时自动清理

## 🎨 启动画面

应用启动时会显示：
- 渐变背景（#202020 → #2a2a2a）
- "Mission Control Loading…" 文字
- 绿色进度条动画（#00ff66）
- 淡入动画（3 秒）

加载完成后自动跳转到 `/t2r` 页面。

## 🔐 安全

- 应用仅允许连接到 `127.0.0.1`（本地）
- 不会暴露端口到外部网络
- 所有通信通过本地回环接口

---

**提示**：如果遇到问题，请先运行 `make app:verify` 检查配置，然后查看日志文件。

