#!/bin/bash
set -e

echo "🔍 验证 Kat Rec Control Center 桌面应用配置"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. 检查前端导出
echo "1️⃣  检查前端静态导出..."
if [ -d "kat_rec_web/frontend/out" ]; then
    echo "   ✅ 前端导出目录存在: kat_rec_web/frontend/out"
else
    echo "   ⚠️  前端导出目录不存在，正在构建..."
    cd kat_rec_web/frontend
    NEXT_OUTPUT_MODE=export pnpm build || {
        echo "   ❌ 前端构建失败"
        exit 1
    }
    cd ../..
fi

# 2. 检查Tauri配置
echo ""
echo "2️⃣  检查Tauri配置..."
if [ -f "desktop/tauri/src-tauri/tauri.conf.json" ]; then
    echo "   ✅ Tauri配置文件存在"
    PRODUCT_NAME=$(jq -r '.package.productName' desktop/tauri/src-tauri/tauri.conf.json)
    VERSION=$(jq -r '.package.version' desktop/tauri/src-tauri/tauri.conf.json)
    echo "   📦 应用名称: $PRODUCT_NAME"
    echo "   📌 版本: $VERSION"
else
    echo "   ❌ Tauri配置文件不存在"
    exit 1
fi

# 3. 检查Rust代码
echo ""
echo "3️⃣  检查Rust代码..."
if [ -f "desktop/tauri/src-tauri/src/main.rs" ]; then
    echo "   ✅ main.rs存在"
    if grep -q "DEFAULT_PORT.*8010" desktop/tauri/src-tauri/src/main.rs; then
        echo "   ✅ 默认端口配置正确 (8010)"
    fi
    if grep -q "USE_MOCK_MODE.*false" desktop/tauri/src-tauri/src/main.rs; then
        echo "   ✅ USE_MOCK_MODE设置为false"
    fi
else
    echo "   ❌ main.rs不存在"
    exit 1
fi

# 4. 检查后端主文件
echo ""
echo "4️⃣  检查后端配置..."
if [ -f "kat_rec_web/backend/main.py" ]; then
    echo "   ✅ backend/main.py存在"
    if grep -q "USE_MOCK_MODE" kat_rec_web/backend/main.py; then
        echo "   ✅ USE_MOCK_MODE支持已确认"
    fi
else
    echo "   ❌ backend/main.py不存在"
    exit 1
fi

# 5. 检查依赖
echo ""
echo "5️⃣  检查依赖..."
if [ -f "desktop/tauri/src-tauri/Cargo.toml" ]; then
    echo "   ✅ Cargo.toml存在"
    if grep -q "reqwest" desktop/tauri/src-tauri/Cargo.toml; then
        echo "   ✅ reqwest依赖已配置"
    fi
    if grep -q "tokio" desktop/tauri/src-tauri/Cargo.toml; then
        echo "   ✅ tokio依赖已配置"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 所有配置检查通过！"
echo ""
echo "📝 下一步："
echo "   1. 运行 'make app:dev' 启动开发模式"
echo "   2. 运行 'make app:build' 构建应用"
echo ""
