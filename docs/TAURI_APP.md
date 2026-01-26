# 🚀 Tauri 桌面应用指南

## 什么是 Tauri？

Tauri 是一个使用 Rust 构建的桌面应用框架，具有以下优势：

- ⚡ **启动速度快**：Rust 编译的原生应用，启动时间 < 1 秒
- 🎨 **界面流畅**：原生窗口，60fps 动画
- 📦 **体积小**：比 Electron 小 10-20 倍
- 🔒 **安全性高**：Rust 的内存安全保证
- 💻 **原生体验**：完全的原生窗口和交互

## 快速开始

### 方法 1: 构建生产版本（推荐）

```bash
# 一键构建（包含前端构建）
make build-tauri
```

这会：
1. 构建前端（静态导出到 `out` 目录）
2. 构建 Tauri 应用（Rust 编译）
3. 生成 `.app` 和 `.dmg` 文件

构建完成后，在 `desktop/tauri/src-tauri/target/release/bundle/macos/` 找到应用。

### 方法 2: 开发模式

```bash
# 启动开发模式（自动重新加载）
make tauri-dev
```

或手动：

```bash
cd desktop/tauri
pnpm tauri dev
```

## 启动流程优化

### 1. 美观的启动画面

Tauri 应用现在包含：
- ✨ 渐变背景和粒子动画
- 🎯 流畅的进度条动画
- 📊 实时状态更新
- 🎨 现代化的 UI 设计

### 2. 快速启动

- **后端启动**：在后台异步启动，不阻塞界面
- **前端加载**：使用静态导出，加载速度快
- **状态更新**：实时显示启动进度

### 3. 原生窗口体验

- 原生 macOS 窗口装饰
- 流畅的窗口动画
- 原生菜单和快捷键支持

## 与 Shell 脚本 App 的对比

| 特性 | Shell 脚本 App | Tauri 应用 |
|------|---------------|-----------|
| **启动速度** | 慢（需要等待后端） | 快（< 1 秒显示界面） |
| **界面** | 终端窗口 | 原生窗口 + Web UI |
| **交互** | 命令行风格 | 现代化 GUI |
| **性能** | 一般 | 优秀（Rust 原生） |
| **体积** | 小（几 MB） | 中等（~50MB） |
| **构建时间** | 快（几秒） | 慢（需要编译 Rust，5-10 分钟） |

## 构建要求

### 前置依赖

1. **Rust 工具链**：
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

2. **系统依赖**（macOS）：
   ```bash
   # 通常已预装，如果需要：
   xcode-select --install
   ```

3. **Node.js 和 pnpm**：
   ```bash
   # Node.js (通过 nvm 或官网安装)
   # pnpm
   curl -fsSL https://get.pnpm.io/install.sh | sh
   ```

### 构建步骤

```bash
# 1. 安装 Rust（如果未安装）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# 2. 构建前端
cd kat_rec_web/frontend
pnpm install
NEXT_OUTPUT_MODE=export pnpm build

# 3. 构建 Tauri
cd ../../desktop/tauri
pnpm install
pnpm tauri build
```

## 使用建议

### 开发时

使用开发模式，支持热重载：

```bash
make tauri-dev
```

### 生产使用

构建生产版本，性能最优：

```bash
make build-tauri
```

然后双击生成的 `.app` 文件。

## 性能优化

### 已实现的优化

1. ✅ **静态前端导出**：使用 Next.js 静态导出，加载速度快
2. ✅ **异步后端启动**：后端在后台启动，不阻塞界面
3. ✅ **优化的启动画面**：美观的加载动画，提升用户体验
4. ✅ **原生窗口**：使用系统原生窗口，性能好

### 进一步优化建议

1. **预加载后端**：可以在应用启动时预加载 Python 环境
2. **缓存机制**：缓存常用数据，减少 API 调用
3. **代码分割**：前端代码分割，按需加载
4. **资源优化**：压缩图片和静态资源

## 故障排除

### 问题 1: Rust 未安装

**错误**: `command not found: cargo`

**解决**:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

### 问题 2: 前端构建失败

**解决**:
```bash
cd kat_rec_web/frontend
rm -rf .next out node_modules
pnpm install
NEXT_OUTPUT_MODE=export pnpm build
```

### 问题 3: Tauri 构建失败

**解决**:
```bash
cd desktop/tauri
rm -rf src-tauri/target
pnpm install
pnpm tauri build
```

### 问题 4: 应用无法启动

**检查**:
1. 前端是否已构建（`kat_rec_web/frontend/out` 目录是否存在）
2. 后端是否可访问（`http://127.0.0.1:8000/health`）
3. 查看日志：`desktop/tauri/backend.log`

## 更新应用

```bash
# 重新构建前端
cd kat_rec_web/frontend
pnpm build

# 重新构建 Tauri
cd ../../desktop/tauri
pnpm tauri build
```

## 分发应用

构建完成后，可以：

1. **直接使用 `.app`**：
   - 位置：`desktop/tauri/src-tauri/target/release/bundle/macos/Kat Rec Control Center.app`
   - 可以拖到 Applications 文件夹

2. **使用 `.dmg` 安装包**：
   - 位置：`desktop/tauri/src-tauri/target/release/bundle/dmg/`
   - 可以分发给其他用户

3. **代码签名**（可选）：
   ```bash
   codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" "Kat Rec Control Center.app"
   ```

## 总结

Tauri 应用提供了：
- ⚡ 更快的启动速度
- 🎨 更美观的界面
- 💻 更流畅的交互
- 📦 更好的性能

推荐用于生产环境！

