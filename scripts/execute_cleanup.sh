#!/bin/bash
# 项目清理执行脚本
# 基于 cleanup_plan.json 自动生成

set -e  # 遇到错误立即退出

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE_DIR="$REPO_ROOT/scripts/archive"

echo "=========================================="
echo "🧹 Kat Rec 项目清理"
echo "=========================================="
echo ""

# 创建归档目录
echo "📦 创建归档目录..."
mkdir -p "$ARCHIVE_DIR"/{test,fix,debug,deprecated}
echo "✅ 归档目录已创建"
echo ""

# 归档测试脚本
echo "📦 归档测试脚本..."
mv "$REPO_ROOT/scripts/check_api_status.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/check_api_status.py"
mv "$REPO_ROOT/scripts/test_render_params.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_params.py"
mv "$REPO_ROOT/scripts/check_render_progress.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/check_render_progress.py"
mv "$REPO_ROOT/scripts/test_render_preset_timing.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_preset_timing.py"
mv "$REPO_ROOT/scripts/check_progress.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/check_progress.py"
mv "$REPO_ROOT/scripts/test_render_30.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_30.py"
mv "$REPO_ROOT/scripts/test_render_g_comparison.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_g_comparison.py"
mv "$REPO_ROOT/scripts/test_render_full_length_3configs.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_full_length_3configs.py"
mv "$REPO_ROOT/scripts/test_render_1min.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_1min.py"
mv "$REPO_ROOT/scripts/check_doc_links.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/check_doc_links.py"
mv "$REPO_ROOT/scripts/check_episode_date_range.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/check_episode_date_range.py"
mv "$REPO_ROOT/scripts/test_cursor_logic.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_cursor_logic.py"
mv "$REPO_ROOT/scripts/test_cursor_after_upload.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_cursor_after_upload.py"
mv "$REPO_ROOT/scripts/test_cursor_flow.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_cursor_flow.py"
mv "$REPO_ROOT/scripts/check_render_status.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/check_render_status.py"
mv "$REPO_ROOT/scripts/check_youtube_api.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/check_youtube_api.py"
mv "$REPO_ROOT/scripts/test_youtube_upload.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_youtube_upload.py"
mv "$REPO_ROOT/scripts/test_render_crf_gradient.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_crf_gradient.py"
mv "$REPO_ROOT/scripts/test_render_1130_full_length.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_1130_full_length.py"
mv "$REPO_ROOT/scripts/check_episode_assets.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/check_episode_assets.py"
mv "$REPO_ROOT/scripts/test_render_full_length_timing.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_render_full_length_timing.py"
mv "$REPO_ROOT/scripts/test_websocket_client.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/test_websocket_client.py"
mv "$REPO_ROOT/scripts/local_picker/check_episode_files.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/local_picker/check_episode_files.py"
mv "$REPO_ROOT/scripts/local_picker/check_schedule_health.py" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: scripts/local_picker/check_schedule_health.py"
echo "✅ 测试脚本已归档"
echo ""
# 归档修复脚本
echo "📦 归档修复脚本..."
mv "$REPO_ROOT/scripts/fix_images_path.py" "$ARCHIVE_DIR/fix/" 2>/dev/null || echo "跳过: scripts/fix_images_path.py"
mv "$REPO_ROOT/scripts/fix_december_descriptions.py" "$ARCHIVE_DIR/fix/" 2>/dev/null || echo "跳过: scripts/fix_december_descriptions.py"
mv "$REPO_ROOT/scripts/fix_ssl_certificates.py" "$ARCHIVE_DIR/fix/" 2>/dev/null || echo "跳过: scripts/fix_ssl_certificates.py"
mv "$REPO_ROOT/scripts/fix_doc_links.py" "$ARCHIVE_DIR/fix/" 2>/dev/null || echo "跳过: scripts/fix_doc_links.py"
mv "$REPO_ROOT/scripts/fix_problematic_titles_api.py" "$ARCHIVE_DIR/fix/" 2>/dev/null || echo "跳过: scripts/fix_problematic_titles_api.py"
mv "$REPO_ROOT/scripts/fix_output_structure.py" "$ARCHIVE_DIR/fix/" 2>/dev/null || echo "跳过: scripts/fix_output_structure.py"
echo "✅ 修复脚本已归档"
echo ""
# 归档调试脚本
echo "📦 归档调试脚本..."
mv "$REPO_ROOT/scripts/diagnose_episode_generation.py" "$ARCHIVE_DIR/debug/" 2>/dev/null || echo "跳过: scripts/diagnose_episode_generation.py"
mv "$REPO_ROOT/scripts/diagnose_automation.py" "$ARCHIVE_DIR/debug/" 2>/dev/null || echo "跳过: scripts/diagnose_automation.py"
mv "$REPO_ROOT/scripts/diagnose_youtube_oauth.py" "$ARCHIVE_DIR/debug/" 2>/dev/null || echo "跳过: scripts/diagnose_youtube_oauth.py"
echo "✅ 调试脚本已归档"
echo ""
echo "=========================================="
echo "✅ 清理完成"
echo "=========================================="
