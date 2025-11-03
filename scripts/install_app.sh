#!/bin/bash
# 将 Kat Records 应用程序安装到 /Applications

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="Kat Records"
APP_PATH="$PROJECT_ROOT/${APP_NAME}.app"
TARGET_PATH="/Applications/${APP_NAME}.app"

echo "📦 安装 Kat Records 应用程序"
echo ""

# 检查应用程序是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "❌ 错误: 找不到应用程序: $APP_PATH"
    echo ""
    echo "💡 请先运行: make create-app"
    exit 1
fi

# 检查是否有旧版本
if [ -d "$TARGET_PATH" ]; then
    echo "⚠️  发现已存在的应用程序: $TARGET_PATH"
    read -p "是否要替换? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 已取消"
        exit 1
    fi
    echo "🗑️  删除旧版本..."
    rm -rf "$TARGET_PATH"
fi

# 复制应用程序
echo "📋 复制应用程序到 /Applications..."
cp -R "$APP_PATH" "$TARGET_PATH" || {
    echo "❌ 复制失败（可能需要管理员权限）"
    echo ""
    echo "💡 可以手动拖拽应用程序到 /Applications 文件夹"
    exit 1
}

echo "✅ 安装完成！"
echo ""
echo "📁 应用程序位置: $TARGET_PATH"
echo ""
echo "🚀 现在可以："
    echo "   1. 在 Launchpad 中搜索 'Kat Records'"
echo "   2. 在应用程序文件夹中找到并启动"
echo "   3. 拖拽到 Dock 以快速访问"

