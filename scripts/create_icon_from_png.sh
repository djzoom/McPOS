#!/bin/bash
# 从PNG创建.icns图标并添加到应用程序包

PNG_FILE="$1"
ICONSET_DIR="AppIcon.iconset"
ICNS_FILE="AppIcon.icns"
APP_NAME="Kat Records"

if [ -z "$PNG_FILE" ] || [ ! -f "$PNG_FILE" ]; then
    echo "❌ 错误: 请提供PNG文件路径"
    echo ""
    echo "用法: $0 <png文件路径>"
    echo "示例: $0 assets/icon/icon.png"
    exit 1
fi

echo "🎨 从PNG创建图标..."
echo "   源文件: $PNG_FILE"
echo ""

# 创建iconset目录
mkdir -p "$ICONSET_DIR"

# 生成所有必需尺寸（macOS图标规范）
echo "📐 生成图标尺寸..."
sips -z 16 16 "$PNG_FILE" --out "$ICONSET_DIR/icon_16x16.png" 2>/dev/null || echo "  ⚠️  16x16 生成失败"
sips -z 32 32 "$PNG_FILE" --out "$ICONSET_DIR/icon_16x16@2x.png" 2>/dev/null || echo "  ⚠️  16x16@2x 生成失败"
sips -z 32 32 "$PNG_FILE" --out "$ICONSET_DIR/icon_32x32.png" 2>/dev/null || echo "  ⚠️  32x32 生成失败"
sips -z 64 64 "$PNG_FILE" --out "$ICONSET_DIR/icon_32x32@2x.png" 2>/dev/null || echo "  ⚠️  32x32@2x 生成失败"
sips -z 128 128 "$PNG_FILE" --out "$ICONSET_DIR/icon_128x128.png" 2>/dev/null || echo "  ⚠️  128x128 生成失败"
sips -z 256 256 "$PNG_FILE" --out "$ICONSET_DIR/icon_128x128@2x.png" 2>/dev/null || echo "  ⚠️  128x128@2x 生成失败"
sips -z 256 256 "$PNG_FILE" --out "$ICONSET_DIR/icon_256x256.png" 2>/dev/null || echo "  ⚠️  256x256 生成失败"
sips -z 512 512 "$PNG_FILE" --out "$ICONSET_DIR/icon_256x256@2x.png" 2>/dev/null || echo "  ⚠️  256x256@2x 生成失败"
sips -z 512 512 "$PNG_FILE" --out "$ICONSET_DIR/icon_512x512.png" 2>/dev/null || echo "  ⚠️  512x512 生成失败"
sips -z 1024 1024 "$PNG_FILE" --out "$ICONSET_DIR/icon_512x512@2x.png" 2>/dev/null || echo "  ⚠️  512x512@2x 生成失败"

echo "  ✅ 图标尺寸生成完成"
echo ""

# 转换为.icns
echo "📦 转换为.icns格式..."
iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE" 2>/dev/null

if [ ! -f "$ICNS_FILE" ]; then
    echo "  ❌ 转换失败"
    echo ""
    echo "💡 提示："
    echo "   1. 确保源PNG文件存在且可读"
    echo "   2. 确保所有尺寸的图标都已生成"
    echo "   3. 可以手动检查: ls -la $ICONSET_DIR/"
    rm -rf "$ICONSET_DIR"
    exit 1
fi

echo "  ✅ 图标已创建: $ICNS_FILE"
echo ""

# 复制到应用程序包
if [ -d "${APP_NAME}.app" ]; then
    echo "📦 添加图标到应用程序包..."
    mkdir -p "${APP_NAME}.app/Contents/Resources"
    cp "$ICNS_FILE" "${APP_NAME}.app/Contents/Resources/AppIcon.icns"
    
    # 验证Info.plist中是否有图标引用
    if ! grep -q "CFBundleIconFile" "${APP_NAME}.app/Contents/Info.plist" 2>/dev/null; then
        echo "  ⚠️  Info.plist中缺少图标引用，正在添加..."
        # 使用sed添加图标引用（在CFBundleExecutable之后）
        sed -i '' '/<key>CFBundleExecutable<\/key>/a\
    <key>CFBundleIconFile</key>\
    <string>AppIcon</string>
' "${APP_NAME}.app/Contents/Info.plist" 2>/dev/null
    fi
    
    echo "  ✅ 图标已添加到: ${APP_NAME}.app/Contents/Resources/AppIcon.icns"
    echo ""
    echo "💡 刷新图标："
    echo "   1. 删除应用程序（如果已安装到/Applications）"
    echo "   2. 重新安装: make install-app"
    echo "   或手动: killall Finder"
else
    echo "⚠️  应用程序包不存在: ${APP_NAME}.app"
    echo "   请先运行: make create-app"
    echo ""
    echo "💡 图标文件已保存为: $ICNS_FILE"
    echo "   可以手动复制到应用程序包的 Resources 目录"
fi

# 清理临时文件
rm -rf "$ICONSET_DIR"

echo ""
echo "✅ 完成！"

