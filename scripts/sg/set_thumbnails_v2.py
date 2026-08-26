#!/usr/bin/env python3
"""给 SG Ep2-10 设置 v2 封面缩略图，并更新主表 cover_file。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Studio/Projects/McPOS/scripts/sg"))
import quota                      # noqa: E402
from sg_upload import build_service, set_thumbnail   # noqa: E402

MASTER = Path.home() / "Studio/Projects/McPOS/config/sg_schedule_master.json"
SESS = Path.home() / "Studio/Workspace/outputs/sg/sessions"

yt = build_service()
# 频道身份闸门：确认 token 指向 Sleep in Grace
ch = yt.channels().list(part="snippet", mine=True).execute()
quota.record("channels.list", "cover-v2 identity gate")
title = ch["items"][0]["snippet"]["title"]
print(f"频道身份: {title}")
if "Sleep in Grace" not in title:
    sys.exit(f"⛔ token 指向 {title}，不是 Sleep in Grace — 中止")

master = json.loads(MASTER.read_text())
done, skipped = 0, 0
for ep in master["episodes"]:
    if ep["episode_number"] == 1:
        continue                  # Ep1 封面本来就对
    ep_id = ep["episode_id"]
    v2 = SESS / ep_id / f"{ep_id}_cover_v2.jpg"
    if not v2.exists():
        print(f"⚠️ {ep_id} 无 v2 封面，跳过"); skipped += 1; continue
    if not quota.can_afford(50):
        print(f"⛔ 配额不足，余 {quota.remaining()}u — 停"); break
    set_thumbnail(yt, ep["video_id"], v2)
    quota.record("thumbnails.set", f"cover-v2 #{ep['episode_number']}")
    ep["cover_file"] = str(v2)
    done += 1
    print(f"✅ #{ep['episode_number']} {ep_id} → {ep['video_id']} 封面已更新")

MASTER.write_text(json.dumps(master, ensure_ascii=False, indent=2))
print(f"完成 {done} 期, 跳过 {skipped}。配额余 {quota.remaining()}u。主表 cover_file 已指向 v2。")
