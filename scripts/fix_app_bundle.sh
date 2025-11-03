#!/bin/bash
# 修复应用程序包，使其可以正常拖动和移动

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="Kat Records"
APP_PATH="$PROJECT_ROOT/${APP_NAME}.app"

echo "🔧 修复应用程序包: $APP_PATH"
echo ""

# 检查应用程序是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "❌ 错误: 找不到应用程序: $APP_PATH"
    echo ""
    echo "💡 请先运行: make create-app"
    exit 1
fi

# 检查应用程序是否正在运行
if pgrep -f "KatRecords" > /dev/null; then
    echo "⚠️  检测到应用程序可能正在运行"
    echo "   正在尝试关闭..."
    killall -9 Terminal 2>/dev/null || true
    sleep 1
fi

echo "🧹 步骤 1: 清除扩展属性..."
# 清除所有扩展属性（这些可能阻止拖动）
xattr -cr "$APP_PATH" 2>/dev/null || true

# 尝试逐个清除顽固的属性
xattr -d com.apple.FinderInfo "$APP_PATH" 2>/dev/null || true
xattr -d com.apple.macl "$APP_PATH" 2>/dev/null || true
xattr -d com.apple.provenance "$APP_PATH" 2>/dev/null || true

# 清除所有子文件的扩展属性
find "$APP_PATH" -exec xattr -cr {} \; 2>/dev/null || true

echo "🔓 步骤 2: 检查并修复权限..."
# 确保所有文件都有正确的权限
chmod -R 755 "$APP_PATH" 2>/dev/null || true
chmod +x "$APP_PATH/Contents/MacOS/KatRecords" 2>/dev/null || true

echo "📦 步骤 3: 验证应用程序包结构..."
# 验证关键文件是否存在
if [ ! -f "$APP_PATH/Contents/Info.plist" ]; then
    echo "❌ 错误: Info.plist 不存在"
    exit 1
fi

if [ ! -f "$APP_PATH/Contents/MacOS/KatRecords" ]; then
    echo "❌ 错误: 可执行文件不存在"
    exit 1
fi

# 验证 Info.plist
if ! plutil -lint "$APP_PATH/Contents/Info.plist" > /dev/null 2>&1; then
    echo "❌ 错误: Info.plist 格式无效"
    exit 1
fi

echo "✅ 应用程序包结构验证通过"

echo ""
echo "🔄 步骤 4: 刷新 Finder 缓存..."
# 强制 Finder 刷新
killall Finder 2>/dev/null || true

echo ""
echo "✅ 修复完成！"
echo ""
echo "📋 现在您可以："
echo "   1. 在 Finder 中拖动应用程序"
echo "   2. 拖到 /Applications 文件夹"
echo "   3. 添加到 Dock"
echo ""
echo "💡 如果仍然无法拖动，请尝试："
echo "   1. 重启 Finder: killall Finder"
echo "   2. 或重启电脑"
echo "   3. 或使用命令行安装: make install-app"

