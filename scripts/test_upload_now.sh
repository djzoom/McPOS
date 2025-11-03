#!/bin/bash
# 快速测试上传脚本

cd "$(dirname "$0")/.." || exit 1

EPISODE=${1:-20251102}
PRIVACY=${2:-unlisted}

echo "🧪 测试上传：期数 $EPISODE"
echo "📹 隐私设置: $PRIVACY"
echo ""

# 检查视频文件
VIDEO_FILE="output/${EPISODE}_youtube.mp4"
if [ ! -f "$VIDEO_FILE" ]; then
    echo "❌ 视频文件不存在: $VIDEO_FILE"
    exit 1
fi

echo "✅ 视频文件存在: $VIDEO_FILE"
echo ""

# 执行上传
.venv/bin/python3 scripts/kat_cli.py upload \
  --episode "$EPISODE" \
  --privacy "$PRIVACY"

echo ""
echo "📋 检查上传结果："
echo "   cat output/*/${EPISODE}_youtube_upload.json"
echo ""
echo "   tail -5 logs/katrec.log | grep upload"

