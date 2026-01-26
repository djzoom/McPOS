# 🎨 为 App 添加图标

## 快速开始

### 方法 1: 自动生成（推荐）

如果你已经有 `icon.png` 文件（1024x1024 PNG）：

```bash
# 生成图标
make create-icon

# 创建 App 包（会自动包含图标）
make create-app
```

### 方法 2: 手动指定图标

```bash
# 从自定义 PNG 文件生成图标
./scripts/create-icon.sh /path/to/your/icon.png

# 然后创建 App 包
make create-app
```

## 图标要求

### PNG 图标要求

- **尺寸**: 建议 1024x1024 像素（正方形）
- **格式**: PNG（支持透明背景）
- **位置**: 项目根目录的 `icon.png`，或使用自定义路径

### 生成的 .icns 文件

脚本会自动生成包含以下尺寸的 `.icns` 文件：

- 16x16 (标准 + Retina)
- 32x32 (标准 + Retina)
- 128x128 (标准 + Retina)
- 256x256 (标准 + Retina)
- 512x512 (标准 + Retina)
- 1024x1024

## 工作流程

1. **准备图标**: 确保有 `icon.png`（1024x1024 PNG）
2. **生成 .icns**: 运行 `make create-icon`
3. **创建 App**: 运行 `make create-app`（会自动检测并使用图标）

## 验证图标

创建 App 包后，可以通过以下方式验证：

```bash
# 查看 App 包中的图标
ls -lh "Kat Rec Control Center.app/Contents/Resources/AppIcon.icns"

# 在 Finder 中查看（图标应该显示在 App 上）
open "Kat Rec Control Center.app"
```

## 更新图标

如果需要更新图标：

1. 替换 `icon.png` 文件
2. 重新生成图标：`make create-icon`
3. 重新创建 App 包：`make create-app`

## 故障排除

### 问题 1: "找不到图标文件"

**解决方案**:
- 确保 `icon.png` 在项目根目录
- 或使用完整路径：`./scripts/create-icon.sh /path/to/icon.png`

### 问题 2: "sips 命令不可用"

**解决方案**:
- 这表示不在 macOS 系统上
- `.icns` 格式是 macOS 专有格式
- 可以在 macOS 上生成图标，然后在其他系统使用

### 问题 3: 图标显示不正确

**解决方案**:
1. 确保 PNG 是正方形（宽高相等）
2. 确保尺寸至少 1024x1024
3. 重新生成图标：`make create-icon`
4. 重新创建 App 包：`make create-app`
5. 清除 macOS 图标缓存：
   ```bash
   sudo killall Finder
   touch "Kat Rec Control Center.app"
   ```

### 问题 4: App 包中没有图标

**检查步骤**:
1. 确认 `AppIcon.icns` 已生成：
   ```bash
   ls -lh AppIcon.icns
   ```
2. 确认 App 包创建时检测到图标（查看创建脚本的输出）
3. 手动复制图标：
   ```bash
   cp AppIcon.icns "Kat Rec Control Center.app/Contents/Resources/"
   ```

## 高级用法

### 使用自定义图标名称

```bash
# 生成自定义名称的图标
./scripts/create-icon.sh icon.png CustomIcon.icns

# 然后需要手动更新 Info.plist 中的 CFBundleIconFile
```

### 批量生成多个尺寸

脚本会自动生成所有需要的尺寸，无需手动操作。

## 技术细节

### 使用的工具

- **sips**: macOS 自带的图像处理工具（用于调整尺寸）
- **iconutil**: macOS 自带的图标工具（用于生成 .icns）

### 图标尺寸说明

macOS 需要多种尺寸以支持：
- 不同显示分辨率（标准、Retina、Super Retina）
- 不同使用场景（Dock、Finder、菜单栏等）

脚本会自动生成所有必需的尺寸。

