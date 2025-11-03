#!/bin/bash
# coding: utf-8
# 安全配置 OpenAI API 密钥
#
# 功能：
# 1. 从用户输入读取密钥（不回显）
# 2. 提供多种安全配置方式
# 3. 自动设置文件权限
# 4. 提供环境变量配置选项
#
# 用法：
#     bash scripts/setup_api_key.sh
set -e

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

echo "🔐 OpenAI API 密钥安全配置"
echo "================================"
echo ""

# 检查是否已存在
CONFIG_FILE="$REPO_ROOT/config/openai_api_key.txt"
if [ -f "$CONFIG_FILE" ]; then
    echo "⚠️  发现已存在的密钥文件: $CONFIG_FILE"
    read -p "是否覆盖？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 已取消"
        exit 0
    fi
fi

# 方法1：从用户输入读取（推荐）
echo "请输入 OpenAI API 密钥（输入时不会显示）:"
read -s API_KEY
echo ""

if [ -z "$API_KEY" ]; then
    echo "❌ 密钥不能为空"
    exit 1
fi

# 创建配置目录（如果不存在）
mkdir -p "$REPO_ROOT/config"

# 保存密钥
echo "$API_KEY" > "$CONFIG_FILE"

# 设置严格的文件权限（仅所有者可读）
chmod 600 "$CONFIG_FILE"

echo ""
echo "✅ 密钥已保存到: $CONFIG_FILE"
echo "✅ 文件权限已设置为 600（仅所有者可读）"
echo ""

# 验证密钥格式（简单检查）
if [[ ! "$API_KEY" =~ ^sk- ]]; then
    echo "⚠️  警告：密钥格式可能不正确（应该以 'sk-' 开头）"
fi

# 提供环境变量选项
echo "================================"
echo "💡 配置选项"
echo "================================"
echo ""
echo "方式1：使用配置文件（当前）"
echo "  位置: $CONFIG_FILE"
echo "  权限: 600（仅所有者可读）"
echo ""
echo "方式2：使用环境变量（推荐用于生产环境）"
echo "  添加到 ~/.zshrc 或 ~/.bashrc:"
echo "  export OPENAI_API_KEY=\"$API_KEY\""
echo ""
echo "方式3：使用密钥管理工具（macOS）"
echo "  可以使用 Keychain 存储："
echo "  security add-generic-password -a 'OPENAI_API_KEY' -s 'Kat_Rec' -w \"$API_KEY\" -U"
echo ""
read -p "是否添加到环境变量？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SHELL_RC="$HOME/.zshrc"
    if [ -f "$HOME/.bashrc" ] && [ ! -f "$SHELL_RC" ]; then
        SHELL_RC="$HOME/.bashrc"
    fi
    
    if grep -q "OPENAI_API_KEY" "$SHELL_RC" 2>/dev/null; then
        echo "⚠️  环境变量 OPENAI_API_KEY 已存在于 $SHELL_RC"
        read -p "是否更新？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # 删除旧的（如果存在）
            sed -i.bak '/export OPENAI_API_KEY=/d' "$SHELL_RC"
            echo "" >> "$SHELL_RC"
            echo "# OpenAI API Key for Kat Records Studio" >> "$SHELL_RC"
            echo "export OPENAI_API_KEY=\"$API_KEY\"" >> "$SHELL_RC"
            echo "✅ 已更新 $SHELL_RC"
            echo "💡 请运行: source $SHELL_RC 或重新打开终端"
        fi
    else
        echo "" >> "$SHELL_RC"
        echo "# OpenAI API Key for Kat Records Studio" >> "$SHELL_RC"
        echo "export OPENAI_API_KEY=\"$API_KEY\"" >> "$SHELL_RC"
        echo "✅ 已添加到 $SHELL_RC"
        echo "💡 请运行: source $SHELL_RC 或重新打开终端"
    fi
fi

echo ""
echo "================================"
echo "✅ 配置完成"
echo "================================"
echo ""
echo "⚠️  安全提醒："
echo "  - 不要将密钥文件提交到 Git"
echo "  - 不要分享密钥给他人"
echo "  - 如果密钥泄露，请立即更换"
echo ""
echo "📝 当前配置："
echo "  - 配置文件: $CONFIG_FILE ($(ls -lh "$CONFIG_FILE" | awk '{print $1}'))"
if [ -n "${OPENAI_API_KEY:-}" ]; then
    echo "  - 环境变量: ✅ 已设置"
else
    echo "  - 环境变量: ❌ 未设置（需要重新打开终端或运行 source ~/.zshrc）"
fi

