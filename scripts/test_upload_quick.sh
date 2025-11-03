#!/bin/bash
# YouTube Upload 快速测试脚本

cd "$(dirname "$0")/.." || exit 1

echo "🧪 YouTube Upload 快速测试"
echo ""

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv .venv"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
.venv/bin/python3 -c "
import sys
try:
    import google.auth
    import google_auth_oauthlib
    import googleapiclient
    print('✅ Google API 依赖已安装')
except ImportError as e:
    print(f'❌ 依赖缺失: {e}')
    print('💡 安装命令: .venv/bin/pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib')
    sys.exit(1)
" || exit 1

# 检查 OAuth 凭证
echo ""
echo "🔐 检查 OAuth 凭证..."
CLIENT_SECRETS="config/google/client_secrets.json"
if [ -f "$CLIENT_SECRETS" ]; then
    echo "✅ OAuth 凭证文件存在: $CLIENT_SECRETS"
else
    echo "⚠️  OAuth 凭证文件不存在: $CLIENT_SECRETS"
    echo "💡 运行设置向导: python3 scripts/setup_youtube_oauth.py"
    echo ""
    echo "   或手动配置:"
    echo "   1. 访问 https://console.cloud.google.com/"
    echo "   2. 启用 YouTube Data API v3"
    echo "   3. 创建 OAuth 2.0 凭证（Desktop app）"
    echo "   4. 下载 JSON 文件到: $CLIENT_SECRETS"
fi

# 检查视频文件
echo ""
echo "📹 检查视频文件..."
VIDEO_FILE=$(find output -name "*_youtube.mp4" -type f 2>/dev/null | head -1)
if [ -n "$VIDEO_FILE" ]; then
    EPISODE_ID=$(basename "$VIDEO_FILE" | cut -d'_' -f1)
    echo "✅ 找到视频文件: $VIDEO_FILE"
    echo "   期数 ID: $EPISODE_ID"
    echo ""
    echo "📋 测试上传命令:"
    echo "   .venv/bin/python3 scripts/kat_cli.py upload --episode $EPISODE_ID"
    echo ""
    echo "   或直接调用:"
    echo "   .venv/bin/python3 scripts/uploader/upload_to_youtube.py \\"
    echo "     --episode $EPISODE_ID \\"
    echo "     --video $VIDEO_FILE"
else
    echo "⚠️  未找到视频文件 (*_youtube.mp4)"
    echo "💡 需要先运行 Stage 9 (视频渲染) 生成视频"
fi

echo ""
echo "=" | tr -d '\n' | head -c 70
echo ""

