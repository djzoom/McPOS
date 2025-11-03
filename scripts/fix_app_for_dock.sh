#!/bin/bash
# 修复应用以便添加到Dock和桌面

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="Kat Records"
APP_PATH="$PROJECT_ROOT/${APP_NAME}.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ 找不到应用: $APP_PATH"
    echo ""
    echo "💡 提示：先运行以下命令创建应用："
    echo "   bash scripts/create_app.sh"
    exit 1
fi

echo "🔧 修复应用以支持Dock和桌面..."
echo ""

# 1. 移除隔离属性
echo "  → 移除隔离属性..."
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true

# 验证隔离属性是否已移除
if xattr -l "$APP_PATH" 2>/dev/null | grep -q "quarantine"; then
    echo "  ⚠️  警告：无法完全移除隔离属性"
else
    echo "  ✅ 隔离属性已移除"
fi

# 2. 确保可执行文件权限
echo "  → 设置执行权限..."
EXECUTABLE="$APP_PATH/Contents/MacOS/MaoMaoRecords"
if [ -f "$EXECUTABLE" ]; then
    chmod +x "$EXECUTABLE"
    echo "  ✅ 执行权限已设置"
else
    echo "  ⚠️  找不到可执行文件: $EXECUTABLE"
    echo "     请确保Info.plist中的CFBundleExecutable与此文件名一致"
fi

# 3. 验证Info.plist
echo "  → 验证Info.plist..."
if [ -f "$APP_PATH/Contents/Info.plist" ]; then
    EXECUTABLE_NAME=$(defaults read "$APP_PATH/Contents/Info.plist" CFBundleExecutable 2>/dev/null || echo "")
    if [ -n "$EXECUTABLE_NAME" ]; then
        if [ -f "$APP_PATH/Contents/MacOS/$EXECUTABLE_NAME" ]; then
            echo "  ✅ Info.plist配置正确"
        else
            echo "  ⚠️  警告：Info.plist中的可执行文件名与实际文件不匹配"
            echo "     CFBundleExecutable: $EXECUTABLE_NAME"
            echo "     实际文件: $EXECUTABLE"
        fi
    else
        echo "  ⚠️  警告：无法读取CFBundleExecutable"
    fi
else
    echo "  ⚠️  警告：找不到Info.plist"
fi

# 4. 代码签名（使用临时证书）
echo "  → 代码签名..."
if codesign --force --deep --sign - "$APP_PATH" 2>/dev/null; then
    echo "  ✅ 代码签名成功"
else
    echo "  ⚠️  代码签名失败（这是正常的，如果没有开发者证书）"
    echo "     应用仍可使用，但可能需要右键点击选择'打开'"
fi

# 5. 验证签名
echo "  → 验证签名..."
if codesign --verify --verbose "$APP_PATH" 2>/dev/null; then
    echo "  ✅ 签名验证通过"
else
    echo "  ⚠️  签名验证失败，但应用应该可以正常使用"
fi

# 6. 刷新Finder
echo "  → 刷新Finder..."
killall Finder 2>/dev/null || true
sleep 1

echo ""
echo "✅ 应用修复完成！"
echo ""
echo "📍 应用位置: $APP_PATH"
echo ""
echo "💡 下一步操作："
echo ""
echo "   1. 首次使用（如果仍有安全提示）："
echo "      • 右键点击应用 -> 选择'打开'"
echo "      • 或者：系统设置 -> 隐私与安全性 -> 允许运行"
echo ""
echo "   2. 添加到Dock："
echo "      • 直接拖拽应用到Dock"
echo "      • 或者：打开应用后，在Dock中右键图标 -> 选项 -> 保留在Dock"
echo ""
echo "   3. 添加到桌面："
echo "      • 直接拖拽应用到桌面"
echo "      • 或者：右键点击 -> 制作替身 -> 拖到桌面"
echo ""
echo "   4. 添加到应用程序文件夹："
echo "      • 拖拽到 /Applications 文件夹"
echo ""
echo "🔍 如果仍有问题，请查看: docs/应用封装与打包指南.md"

