#!/bin/bash
# Kat Records Studio - 封装脚本
# 用途：创建项目的完整封装包

set -e  # 遇到错误立即退出

VERSION="${1:-v1.0.0}"
PROJECT_NAME="kat-rec"
PACKAGE_NAME="${PROJECT_NAME}-${VERSION}"
TEMP_DIR="/tmp/${PACKAGE_NAME}_build"
CURRENT_DIR="$(pwd)"

echo "📦 Kat Records Studio 封装脚本"
echo "版本: ${VERSION}"
echo ""

# 清理旧的临时目录
if [ -d "$TEMP_DIR" ]; then
    echo "清理旧临时目录..."
    rm -rf "$TEMP_DIR"
fi

# 创建临时目录
mkdir -p "$TEMP_DIR"

echo "📋 步骤1: 复制项目文件..."
rsync -av \
    --exclude='.venv' \
    --exclude='.venv311' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='output' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='.DS_Store' \
    --exclude='*.log' \
    --exclude='config/openai_api_key.txt' \
    --exclude='config/*_api_key.txt' \
    --exclude='config/*_secret.txt' \
    --exclude='config/production_log.json' \
    --exclude='config/schedule_master.json' \
    --exclude='data/song_files' \
    --exclude='data/song_library.csv' \
    --exclude='data/song_usage.csv' \
    "$CURRENT_DIR/" "$TEMP_DIR/${PACKAGE_NAME}/"

echo ""
echo "📋 步骤2: 创建版本信息文件..."
cat > "$TEMP_DIR/${PACKAGE_NAME}/VERSION.txt" << EOF
Kat Records Studio
Version: ${VERSION}
Packaged: $(date '+%Y-%m-%d %H:%M:%S')
Python: $(python3 --version)
EOF

echo ""
echo "📋 步骤3: 创建压缩包..."
cd "$TEMP_DIR"

# 创建 tar.gz 压缩包
echo "创建 ${PACKAGE_NAME}.tar.gz..."
tar -czf "${CURRENT_DIR}/${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}/"

# 创建 zip 压缩包
echo "创建 ${PACKAGE_NAME}.zip..."
zip -r "${CURRENT_DIR}/${PACKAGE_NAME}.zip" "${PACKAGE_NAME}/" \
    -x "*.venv/*" "*__pycache__/*" "*.pyc" "output/*" ".git/*"

cd "$CURRENT_DIR"

echo ""
echo "📋 步骤4: 计算文件大小..."
TAR_SIZE=$(du -h "${PACKAGE_NAME}.tar.gz" | cut -f1)
ZIP_SIZE=$(du -h "${PACKAGE_NAME}.zip" | cut -f1)

echo ""
echo "✅ 封装完成！"
echo ""
echo "📦 生成的封装包:"
echo "  - ${PACKAGE_NAME}.tar.gz (${TAR_SIZE})"
echo "  - ${PACKAGE_NAME}.zip (${ZIP_SIZE})"
echo ""
echo "📍 位置: ${CURRENT_DIR}/"
echo ""

# 清理临时目录
echo "🧹 清理临时文件..."
rm -rf "$TEMP_DIR"

echo "✨ 完成！"
