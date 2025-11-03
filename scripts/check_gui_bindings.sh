#!/usr/bin/env bash
set -euo pipefail

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                   GUI绑定验证脚本                                                ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

errors=0

check_file() {
  local file="$1"
  local pattern="$2"
  local description="$3"
  
  if grep -q "$pattern" "$file" 2>/dev/null; then
    echo "✅ $description: $pattern"
    return 0
  else
    echo "❌ $description: 未找到 $pattern"
    errors=$((errors + 1))
    return 1
  fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. API端点绑定检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_file "kat_rec_web/frontend/services/t2rApi.ts" "apiRequest('/api/t2r/scan" "Scan endpoint"
check_file "kat_rec_web/frontend/services/t2rApi.ts" "apiRequest('/api/t2r/srt/inspect" "SRT Inspect endpoint"
check_file "kat_rec_web/frontend/services/t2rApi.ts" "apiRequest('/api/t2r/desc/lint" "Desc Lint endpoint"
check_file "kat_rec_web/frontend/services/t2rApi.ts" "apiRequest('/api/t2r/plan" "Plan endpoint"
check_file "kat_rec_web/frontend/services/t2rApi.ts" "apiRequest('/api/t2r/run" "Run endpoint"
check_file "kat_rec_web/frontend/services/t2rApi.ts" "apiRequest('/api/t2r/upload/verify" "Upload Verify endpoint"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. 组件API调用检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_file "kat_rec_web/frontend/components/t2r/ChannelOverview.tsx" "scanSchedule()" "ChannelOverview scan"
check_file "kat_rec_web/frontend/components/t2r/SRTDoctor.tsx" "inspectSRT\|fixSRT" "SRTDoctor API calls"
check_file "kat_rec_web/frontend/components/t2r/DescriptionLinter.tsx" "lintDescription" "DescriptionLinter API call"
check_file "kat_rec_web/frontend/components/t2r/PlanAndRun.tsx" "planEpisode\|runEpisode" "PlanAndRun API calls"
check_file "kat_rec_web/frontend/components/t2r/PostUploadVerify.tsx" "verifyUpload" "PostUploadVerify API call"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Zustand Store绑定检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_file "kat_rec_web/frontend/components/t2r/ChannelOverview.tsx" "useT2RScheduleStore\|useT2RAssetsStore" "ChannelOverview stores"
check_file "kat_rec_web/frontend/components/t2r/SRTDoctor.tsx" "useT2RSrtStore" "SRTDoctor store"
check_file "kat_rec_web/frontend/components/t2r/DescriptionLinter.tsx" "useT2RDescStore" "DescriptionLinter store"
check_file "kat_rec_web/frontend/components/t2r/PlanAndRun.tsx" "useRunbookStore" "PlanAndRun store"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. 加载状态检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_file "kat_rec_web/frontend/components/t2r/ChannelOverview.tsx" "isLoading\|setLoading" "ChannelOverview loading"
check_file "kat_rec_web/frontend/components/t2r/SRTDoctor.tsx" "isLoading" "SRTDoctor loading"
check_file "kat_rec_web/frontend/components/t2r/DescriptionLinter.tsx" "isLoading" "DescriptionLinter loading"
check_file "kat_rec_web/frontend/components/t2r/PlanAndRun.tsx" "isPlanning\|isRunning" "PlanAndRun loading"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $errors -eq 0 ]; then
  echo "✅ 所有绑定检查通过"
  exit 0
else
  echo "❌ 有 $errors 个绑定问题"
  exit 1
fi

