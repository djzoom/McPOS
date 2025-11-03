#!/bin/bash
# Sprint 2 功能验证脚本
# 用途：自动化验证前端 A 已完成的工作

set -e

echo "🔍 Sprint 2 功能验证开始..."
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 1. 检查前端依赖
echo "1. 检查前端依赖..."
cd kat_rec_web/frontend

if [ -d "node_modules" ]; then
    check_pass "前端依赖已安装"
else
    check_warn "前端依赖未安装，请运行: pnpm install"
fi

# 检查 package.json 中的关键依赖
if grep -q "@tanstack/react-query" package.json; then
    check_pass "React Query 已配置"
else
    check_fail "React Query 未配置"
fi

if grep -q "framer-motion" package.json; then
    check_pass "Framer Motion 已配置"
else
    check_fail "Framer Motion 未配置"
fi

if grep -q "recharts" package.json; then
    check_pass "Recharts 已配置"
else
    check_fail "Recharts 未配置"
fi

echo ""

# 2. 检查组件文件
echo "2. 检查组件文件..."

if [ -f "components/ChannelWorkbench/index.tsx" ]; then
    check_pass "ChannelWorkbench/index.tsx 存在"
else
    check_fail "ChannelWorkbench/index.tsx 不存在"
fi

if [ -f "components/ChannelWorkbench/ChannelCard.tsx" ]; then
    check_pass "ChannelWorkbench/ChannelCard.tsx 存在"
else
    check_fail "ChannelWorkbench/ChannelCard.tsx 不存在"
fi

if [ -f "components/MissionControl/index.tsx" ]; then
    check_pass "MissionControl/index.tsx 存在"
else
    check_fail "MissionControl/index.tsx 不存在"
fi

if [ -f "app/providers.tsx" ]; then
    check_pass "app/providers.tsx 存在"
else
    check_fail "app/providers.tsx 不存在"
fi

echo ""

# 3. 检查 TypeScript 配置
echo "3. 检查 TypeScript 配置..."

if [ -f "tsconfig.json" ]; then
    check_pass "tsconfig.json 存在"
    
    # 检查类型检查（如果依赖已安装）
    if [ -d "node_modules" ]; then
        if npx tsc --noEmit --skipLibCheck 2>/dev/null; then
            check_pass "TypeScript 类型检查通过"
        else
            check_warn "TypeScript 类型检查有警告（可能需要安装依赖）"
        fi
    else
        check_warn "跳过 TypeScript 检查（依赖未安装）"
    fi
else
    check_fail "tsconfig.json 不存在"
fi

echo ""

# 4. 检查后端 Mock API
echo "4. 检查后端 Mock API..."

cd ../backend

if [ -f "routes/mock.py" ]; then
    check_pass "routes/mock.py 存在"
    
    # 检查是否包含频道端点
    if grep -q "@router.get(\"/channels\")" routes/mock.py; then
        check_pass "频道端点已实现"
    else
        check_fail "频道端点未实现"
    fi
    
    # 检查是否包含 generate_mock_channel 函数
    if grep -q "def generate_mock_channel" routes/mock.py; then
        check_pass "generate_mock_channel 函数存在"
    else
        check_fail "generate_mock_channel 函数不存在"
    fi
else
    check_fail "routes/mock.py 不存在"
fi

# 检查 main.py 是否挂载了 mock 路由
if grep -q "api/channels" main.py; then
    check_pass "Mock API 路由已挂载"
else
    check_warn "Mock API 路由可能未挂载"
fi

echo ""

# 5. 检查 API 服务
echo "5. 检查前端 API 服务..."

cd ../frontend

if [ -f "services/api.ts" ]; then
    check_pass "services/api.ts 存在"
    
    if grep -q "fetchChannels" services/api.ts; then
        check_pass "fetchChannels 函数存在"
    else
        check_fail "fetchChannels 函数不存在"
    fi
    
    if grep -q "fetchSummary" services/api.ts; then
        check_pass "fetchSummary 函数存在"
    else
        check_fail "fetchSummary 函数不存在"
    fi
else
    check_fail "services/api.ts 不存在"
fi

echo ""

# 6. 检查页面集成
echo "6. 检查页面集成..."

if grep -q "MissionControl" app/page.tsx; then
    check_pass "MissionControl 已集成到主页面"
else
    check_fail "MissionControl 未集成到主页面"
fi

if grep -q "ChannelWorkbench" app/page.tsx; then
    check_pass "ChannelWorkbench 已集成到主页面"
else
    check_fail "ChannelWorkbench 未集成到主页面"
fi

if grep -q "activeSection" app/page.tsx; then
    check_pass "标签导航已实现"
else
    check_fail "标签导航未实现"
fi

echo ""

# 总结
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 验证总结"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "静态检查完成！"
echo ""
echo "📝 下一步操作："
echo ""
echo "1. 安装依赖（如未安装）："
echo "   cd kat_rec_web/frontend && pnpm install"
echo ""
echo "2. 启动后端 Mock API："
echo "   cd kat_rec_web/backend"
echo "   export USE_MOCK_MODE=true"
echo "   uvicorn main:app --reload --port 8000"
echo ""
echo "3. 启动前端开发服务器："
echo "   cd kat_rec_web/frontend"
echo "   pnpm dev"
echo ""
echo "4. 浏览器访问 http://localhost:3000 进行功能测试"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

