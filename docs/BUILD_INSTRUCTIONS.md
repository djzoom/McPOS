# 构建桌面应用指南

## 前置要求

### 1. 安装 Rust（必需）

Tauri 应用是用 Rust 编写的，需要先安装 Rust 工具链。

#### 方式 1: 官方安装脚本（推荐）

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

安装完成后：
```bash
source $HOME/.cargo/env
```

#### 方式 2: 使用 Homebrew

```bash
brew install rust
rustup default stable
```

#### 验证安装

```bash
cargo --version
rustc --version
```

### 2. 安装 Node.js 和 pnpm（必需）

```bash
# 安装 pnpm（如果还没有）
npm install -g pnpm

# 或使用 Homebrew
brew install pnpm
```

### 3. Python 环境（必需）

确保已配置 Python 虚拟环境：

```bash
# 检查 Python
python3 --version

# 如果有虚拟环境
cd kat_rec_web/backend
python3 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
```

## 构建步骤

### 快速构建

```bash
bash scripts/build_app.sh
```

### 手动构建

```bash
# 1. 安装 Tauri 依赖（首次需要）
cd desktop/tauri
pnpm install

# 2. 构建前端静态导出
cd ../../kat_rec_web/frontend
NEXT_OUTPUT_MODE=export pnpm build

# 3. 构建 Tauri 应用
cd ../../desktop/tauri
pnpm tauri build
```

## 构建输出

构建完成后，应用位于：

```
desktop/tauri/src-tauri/target/release/bundle/macos/Kat Rec Control Center.app
```

## 启动应用

### 方式 1: Finder 双击

1. 在 Finder 中打开 `desktop/tauri/src-tauri/target/release/bundle/macos/`
2. 双击 `Kat Rec Control Center.app`

### 方式 2: 命令行

```bash
open "desktop/tauri/src-tauri/target/release/bundle/macos/Kat Rec Control Center.app"
```

### 方式 3: 移动到 Applications

可以将 .app 文件拖到 `/Applications` 文件夹，方便从 Launchpad 或 Spotlight 启动。

## 开发模式

如果只是想测试应用（不打包），可以使用开发模式：

```bash
make app:dev
```

这会直接启动窗口，但不会生成 .app 文件。

## 常见问题

### 构建失败：找不到 Cargo

**原因**：Rust 未安装或不在 PATH 中

**解决**：
1. 安装 Rust（见上方）
2. 重启终端
3. 运行 `source $HOME/.cargo/env`

### 构建失败：端口范围配置错误

如果看到 `"http://127.0.0.1:*" is not a "uri"` 错误，说明 Tauri 配置已更新，需要重新构建。

### 首次构建很慢

首次构建需要下载 Rust 依赖和编译，可能需要 5-10 分钟。后续构建会快很多。

### macOS 安全警告

首次运行时，macOS 可能会提示"无法验证开发者"。解决：

1. 右键点击 .app
2. 选择"打开"
3. 在警告对话框中点击"打开"

或者在系统设置中允许该应用运行。

## 更新应用

如果修改了代码，需要重新构建：

```bash
# 删除旧的构建产物（可选）
rm -rf desktop/tauri/src-tauri/target

# 重新构建
bash scripts/build_app.sh
```

