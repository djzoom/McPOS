#!/bin/bash
# Sleep in Grace 批次状态一览: 每期 渲染/上传/排期 三列
M="$(dirname "$0")/../../config/sg_schedule_master.json"
python3 - "$M" <<'PY'
import json, sys
from pathlib import Path
m = json.load(open(sys.argv[1]))
print(f"{'#':>3} {'episode':22} {'渲染':6} {'上传':22} {'排期'}")
for e in m["episodes"]:
    v = Path(e["output_file"])
    render = "✅" if v.exists() else "❌"
    flag = v.parent / f"{e['episode_id']}_upload_complete.flag"
    up = ("✅ " + (e.get("video_id") or "")) if flag.exists() else \
         ("⬆️ " + (e.get("video_id") or "")) if e.get("video_id") else "—"
    print(f"{e['episode_number']:>3} {e['episode_id']:22} {render:6} {up:22} "
          f"{e.get('publish_at','')} [{e.get('status')}]")
PY
