#!/usr/bin/env python3
# coding: utf-8
"""给**已上线**的期次补挂缺失的字幕轨。

2026-08-16 发现:本地八期都生成了简繁中文字幕,平台上却只有英文轨 ——
`upload_caption` 把 language 硬编码成 "en",中文字幕从没被送出去过。
上传器已修,但已上线的八期得回头补挂,这就是本脚本。

幂等:先查平台已有哪些语言轨,只补缺的;重跑安全。
预算:captions.insert 每条 400u,按配额分批,不够就停在当条并说明。

  ./.venv/bin/python scripts/sg/backfill_captions.py --dry-run
  ./.venv/bin/python scripts/sg/backfill_captions.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quota                                                    # noqa: E402
from sg_upload import (CAPTION_TRACKS, build_service,           # noqa: E402
                       upload_caption, upload_link_lock)

ROOT = Path(__file__).resolve().parents[1].parent
MASTER = ROOT / "config" / "sg_schedule_master.json"
SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    eps = [r for r in json.loads(MASTER.read_text())["episodes"] if r.get("video_id")]
    yt = build_service()
    todo: list[tuple[dict, Path, str, str]] = []

    for ep in eps:
        vid, eid = ep["video_id"], ep["episode_id"]
        have = {i["snippet"]["language"] for i in
                yt.captions().list(part="snippet", videoId=vid).execute().get("items", [])
                if i["snippet"]["trackKind"] != "asr"}
        for suffix, lang, label in CAPTION_TRACKS:
            if lang in have:
                continue
            track = SESSIONS / eid / f"{eid}{suffix}.srt"
            if not track.exists():
                print(f"  ⚠ {eid} 缺文件 {track.name}")
                continue
            todo.append((ep, track, lang, label))
        print(f"  {eid} 平台已有 {sorted(have) or '无'} → 待补 "
              f"{[l for _, _, l, _ in todo if _ is ep] if False else ''}"
              f"{[t[2] for t in todo if t[0] is ep]}")

    cost = 400 * len(todo)
    print(f"\n待补 {len(todo)} 条轨 · 需 {cost}u · 余 {quota.remaining()}u")
    if a.dry_run or not todo:
        return 0

    done = 0
    with upload_link_lock("sg-captions-backfill"):
        for ep, track, lang, label in todo:
            if not quota.can_afford(400):
                print(f"  🛑 配额不足,已补 {done} 条,余下明日再跑")
                break
            upload_caption(yt, ep["video_id"], track, language=lang, name=label)
            quota.record("captions.insert", f"{ep['episode_id']} {lang}")
            done += 1
            print(f"  ✅ {ep['episode_id']} + {label}")
    print(f"\n补挂 {done}/{len(todo)} 条 · 配额余 {quota.remaining()}u")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
