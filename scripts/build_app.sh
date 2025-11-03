#!/bin/bash
set -e

echo "🔨 开始构建 Kat Rec Control Center 桌面应用"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 检查依赖
echo "1️⃣  检查依赖..."
cd "$(dirname "$0")/.."

if [ ! -d "desktop/tauri/node_modules" ]; then
    echo "   ⚠️  Tauri 依赖未安装，正在安装..."
    cd desktop/tauri
    pnpm install
    cd ../..
    echo "   ✅ 依赖安装完成"
else
    echo "   ✅ Tauri 依赖已安装"
fi

# 构建前端
echo ""
echo "2️⃣  构建前端静态导出..."
cd kat_rec_web/frontend
if [ ! -d "out" ]; then
    echo "   ⚠️  前端导出目录不存在，正在构建..."
    NEXT_OUTPUT_MODE=export pnpm build
    echo "   ✅ 前端构建完成"
else
    echo "   ✅ 前端导出目录已存在（跳过构建）"
    echo "   💡 如需重新构建，请删除 out 目录"
fi
cd ../..

# 构建 Tauri 应用
echo ""
echo "3️⃣  构建 Tauri 应用..."
echo "   ⏳ 这可能需要几分钟（首次构建需要编译 Rust）..."
cd desktop/tauri
pnpm tauri build

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 构建完成！"
echo ""
echo "📦 应用位置："
echo "   $(pwd)/src-tauri/target/release/bundle/macos/Kat Rec Control Center.app"
echo ""
echo "🚀 启动方式："
echo "   1. 在 Finder 中打开上面的路径"
echo "   2. 双击 'Kat Rec Control Center.app'"
echo "   3. 或者运行: open 'src-tauri/target/release/bundle/macos/Kat Rec Control Center.app'"
echo ""

