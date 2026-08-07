#!/usr/bin/env python3
# coding: utf-8
"""Sleep in Grace — 独立验证器。

对 status=uploaded 的期:videos.list 核对可访问性/privacy/publishAt 与主表一致、
captions.list 有字幕、缩略图已挂 —— 全部通过才落 upload_complete.flag 并把主表
status 改为 verified。**flag 是验证通过的结论,不是上传动作的副产品。**

    python scripts/sg/sg_verify_uploads.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quota                                    # noqa: E402
from sg_upload import build_service             # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "config" / "sg_schedule_master.json"


def main() -> int:
    master = json.loads(MASTER_PATH.read_text())
    targets = [e for e in master["episodes"] if e.get("status") == "uploaded"
               and e.get("video_id")]
    if not targets:
        print("无待验证期(status=uploaded)")
        return 0

    yt = build_service()
    changed = False
    for ep in targets:
        vid, num = ep["video_id"], ep["episode_number"]
        problems: list[str] = []

        r = yt.videos().list(part="status,snippet,processingDetails",
                             id=vid).execute()
        quota.record("videos.list", ep["episode_id"])
        items = r.get("items", [])
        if not items:
            problems.append("视频不可访问(可能被删/错 id)")
        else:
            v = items[0]
            st = v["status"]
            if st.get("privacyStatus") != "private":
                problems.append(f"privacy={st.get('privacyStatus')} ≠ private")
            want = ep["publish_at"]
            got = st.get("publishAt", "")
            if not got:
                problems.append("无 publishAt(未排播!)")
            elif got[:16] != want.replace("+07:00", "")[:16] and \
                    not _same_instant(got, want):
                problems.append(f"publishAt {got} ≠ 主表 {want}")
            thumbs = v.get("snippet", {}).get("thumbnails", {})
            if "maxres" not in thumbs and "standard" not in thumbs \
                    and "high" not in thumbs:
                problems.append("缩略图未就绪")

        c = yt.captions().list(part="snippet", videoId=vid).execute()
        quota.record("captions.list", ep["episode_id"])
        if not c.get("items"):
            problems.append("无字幕轨")

        if problems:
            print(f"  ❌ #{num} {vid}: {'; '.join(problems)}")
            continue

        flag = Path(ep["output_file"]).parent / \
            f"{ep['episode_id']}_upload_complete.flag"
        flag.write_text(datetime.now().isoformat() + "\n")
        ep["status"] = "verified"
        ep["caption_uploaded"] = True
        changed = True
        print(f"  ✅ #{num} {vid} 验证通过 → flag 落地, status=verified")

    if changed:
        stamp = datetime.now().strftime("%Y%m%d")
        bak = MASTER_PATH.with_suffix(f".json.bak_{stamp}")
        if not bak.exists():
            bak.write_text(MASTER_PATH.read_text())
        MASTER_PATH.write_text(json.dumps(master, ensure_ascii=False, indent=2))
        print("主表已更新 — 记得 git 提交")
    return 0


def _same_instant(a: str, b: str) -> bool:
    from datetime import datetime as dt
    try:
        pa = dt.fromisoformat(a.replace("Z", "+00:00"))
        pb = dt.fromisoformat(b.replace("Z", "+00:00"))
        return abs((pa - pb).total_seconds()) < 120
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
