#!/bin/bash
# 📦 封装前清理脚本
# 用途：清理临时文件、缓存和不需要的文件，准备封装

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🧹 封装前清理准备"
echo "================================"
echo ""

# 1. 清理Python缓存
echo "📋 步骤1: 清理Python缓存..."
find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -not -path "./.venv/*" -delete 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
echo "✅ Python缓存已清理"

# 2. 清理临时文件
echo ""
echo "📋 步骤2: 清理临时文件..."
find . -type f -name "*.tmp" -not -path "./.venv/*" -delete 2>/dev/null || true
find . -type f -name "*.bak" -not -path "./.venv/*" -delete 2>/dev/null || true
find . -type f -name "*.swp" -not -path "./.venv/*" -delete 2>/dev/null || true
find . -type f -name "*~" -not -path "./.venv/*" -delete 2>/dev/null || true
find . -type f -name "*.log" -not -path "./.venv/*" -not -path "./output/logs/*" -delete 2>/dev/null || true
echo "✅ 临时文件已清理"

# 3. 清理系统文件
echo ""
echo "📋 步骤3: 清理系统文件..."
find . -type f -name ".DS_Store" -delete 2>/dev/null || true
find . -type f -name "Thumbs.db" -delete 2>/dev/null || true
echo "✅ 系统文件已清理"

# 4. 验证.gitignore完整性
echo ""
echo "📋 步骤4: 验证.gitignore..."
if [ -f ".gitignore" ]; then
    # 检查关键规则是否存在
    if grep -q "__pycache__" .gitignore && \
       grep -q "\.pyc" .gitignore && \
       grep -q "output/" .gitignore && \
       grep -q "openai_api_key" .gitignore; then
        echo "✅ .gitignore 规则完整"
    else
        echo "⚠️  .gitignore 可能缺少某些规则，请检查"
    fi
else
    echo "❌ 未找到 .gitignore 文件"
    exit 1
fi

# 5. 检查敏感文件
echo ""
echo "📋 步骤5: 检查敏感文件..."
SENSITIVE_FILES=(
    "config/openai_api_key.txt"
    "config/*_api_key.txt"
    "config/*_secret.txt"
    ".env"
    ".env.*"
)

FOUND_SENSITIVE=0
for pattern in "${SENSITIVE_FILES[@]}"; do
    if ls $pattern 2>/dev/null | grep -q .; then
        echo "⚠️  发现敏感文件: $pattern"
        FOUND_SENSITIVE=1
    fi
done

if [ $FOUND_SENSITIVE -eq 0 ]; then
    echo "✅ 未发现敏感文件（或已正确忽略）"
else
    echo "⚠️  警告：发现敏感文件，请确保它们已在.gitignore中"
fi

# 6. 检查Git状态
echo ""
echo "📋 步骤6: 检查Git状态..."
if command -v git &> /dev/null; then
    # 检查是否有未跟踪的敏感文件
    UNTRACKED=$(git status --porcelain | grep "^??" || true)
    if [ -n "$UNTRACKED" ]; then
        echo "📝 未跟踪的文件："
        echo "$UNTRACKED" | head -10
        echo ""
        echo "💡 提示：请确保这些文件应在.gitignore中（如果是敏感文件）"
    else
        echo "✅ 无未跟踪的敏感文件"
    fi
    
    # 检查是否有待提交的文件
    STAGED=$(git diff --cached --name-only 2>/dev/null || true)
    if [ -n "$STAGED" ]; then
        echo ""
        echo "📝 已暂存的文件："
        echo "$STAGED" | head -10
    fi
else
    echo "⚠️  Git 未安装或不可用，跳过Git状态检查"
fi

# 7. 检查output目录（只检查，不删除）
echo ""
echo "📋 步骤7: 检查output目录..."
if [ -d "output" ]; then
    OUTPUT_SIZE=$(du -sh output 2>/dev/null | cut -f1)
    echo "📁 output目录大小: $OUTPUT_SIZE"
    echo "✅ output目录已在.gitignore中，不会被封装"
else
    echo "✅ output目录不存在"
fi

# 8. 检查配置目录中的运行时文件
echo ""
echo "📋 步骤8: 检查运行时配置文件..."
RUNTIME_CONFIGS=(
    "config/production_log.json"
    "config/schedule_master.json"
)

for config in "${RUNTIME_CONFIGS[@]}"; do
    if [ -f "$config" ]; then
        echo "📄 $config 存在（运行时生成，不应打包）"
        if grep -q "$(basename $config)" .gitignore; then
            echo "   ✅ 已在.gitignore中"
        else
            echo "   ⚠️  未在.gitignore中，建议添加"
        fi
    fi
done

# 9. 统计清理结果
echo ""
echo "📋 步骤9: 统计项目文件..."
PROJECT_SIZE=$(du -sh . --exclude=.venv --exclude=.git --exclude=output 2>/dev/null | cut -f1)
PYTHON_FILES=$(find . -name "*.py" -not -path "./.venv/*" | wc -l | tr -d ' ')
MARKDOWN_FILES=$(find . -name "*.md" | wc -l | tr -d ' ')
CONFIG_FILES=$(find config -name "*.yml" 2>/dev/null | wc -l | tr -d ' ')

echo "📊 项目统计："
echo "   - 项目大小（排除.venv/.git/output）: $PROJECT_SIZE"
echo "   - Python文件: $PYTHON_FILES"
echo "   - Markdown文档: $MARKDOWN_FILES"
echo "   - 配置文件: $CONFIG_FILES"

# 10. 最终建议
echo ""
echo "================================"
echo "✅ 清理完成！"
echo ""
echo "📋 封装前建议："
echo "1. 运行测试: make test"
echo "2. 检查Git状态: git status"
echo "3. 确保所有敏感文件已在.gitignore中"
echo "4. 验证文档完整性"
echo ""
echo "📦 准备封装: bash scripts/package.sh [版本号]"
echo "   例如: bash scripts/package.sh v1.0.0"
echo ""

