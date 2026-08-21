#!/usr/bin/env python3
# coding: utf-8
"""频道孤儿普查 —— 平台上有、主表里没有的视频。

为什么需要:2026-08-19 发现旧原子 Ep8 的视频 F8WhUgKgOUQ 仍挂在频道上、
定于 10-03 自动公开,而主表里已查无此人(撤回时配额耗尽漏下,重写主表时
它的 ID 又被清掉)。这种视频没有任何本地记录指向它,只会在公开那天
自己冒出来 —— 本管线所有的门都在**本地**,拦不住一个平台上的幽灵。

对账口径:上传播放列表里的全部视频 vs 主表的 video_id / recalled_video_id。
只读不改,列出三类:孤儿(平台有本地无)、幽灵(本地有平台无)、待播清单。

配额:playlistItems.list 每页 1u(50 条/页),videos.list 每批 1u。
一次普查通常 2–4u,便宜到可以每天跑。

  ./.venv/bin/python scripts/sg/audit_channel_orphans.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quota                                    # noqa: E402
from sg_upload import build_service             # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "config" / "sg_schedule_master.json"
SHORTS_STATE = Path.home() / "Projects/TOYTUNE/publish_state.json"


def main() -> int:
    if not quota.can_afford(10):
        print(f"⛔ 配额不足(余 {quota.remaining()}u)—— 等重置")
        return 1
    yt = build_service()

    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    quota.record("channels.list", "orphan-audit")
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    vids: list[str] = []
    token = None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                    maxResults=50, pageToken=token).execute()
        quota.record("playlistItems.list", "orphan-audit")
        vids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break

    master = json.loads(MASTER.read_text(encoding="utf-8"))
    rows = master.get("episodes", [])
    known = {r.get("video_id") for r in rows if r.get("video_id")}
    recalled = {r.get("recalled_video_id") for r in rows if r.get("recalled_video_id")}
    by_vid = {r.get("video_id"): r for r in rows if r.get("video_id")}

    # 短片由 TOYTUNE 自己的状态表管,不在长片主表里 —— 只拿主表对账的话,
    # 14 条正常短片会被全判成孤儿(2026-08-21 实测 30 条报 20 条,几乎全是
    # 良性)。判据要认全**所有**在册来源,再按危害分级。
    shorts = set()
    if SHORTS_STATE.exists():
        shorts = {v.get("video_id")
                  for v in json.loads(SHORTS_STATE.read_text()).get(
                      "uploaded", {}).values() if v.get("video_id")}
    tracked = known | shorts
    untracked = [v for v in vids if v not in tracked]
    ghosts = sorted(known - set(vids))

    print(f"═══ 频道对账 · 平台 {len(vids)} 条 ═══")
    print(f"  在册:长片 {len(known & set(vids))} · 短片 {len(shorts & set(vids))}"
          f" · 无人记着 {len(untracked)}")

    danger, historical = [], []
    if untracked:
        det = yt.videos().list(part="snippet,status",
                               id=",".join(untracked[:50])).execute()
        quota.record("videos.list", "orphan-detail")
        for it in det.get("items", []):
            st = it["status"]
            # 真正危险的只有一类:没人记着、却挂着定时公开 —— 它会在某天
            # 自己冒出来(F8WhUgKgOUQ 就是)。已公开的旧内容是频道历史,
            # 不是故障。
            (danger if st.get("publishAt") else historical).append(
                (it["id"], st["privacyStatus"], st.get("publishAt"),
                 it["snippet"]["title"]))

    for vid_, priv, pub, title in danger:
        mark = "(撤回没删净的旧片)" if vid_ in recalled else ""
        print(f"  ❌ 真孤儿 {vid_} [{priv}] 将于 {pub} **自己公开** {mark}\n"
              f"       「{title[:64]}」")
    if not danger:
        print("  ✅ 无真孤儿:没有「无人记着却会自己公开」的视频")
    if historical:
        print(f"  ℹ 历史内容 {len(historical)} 条(已公开、非本管线产出,"
              f"属频道既往内容):")
        for vid_, _, _, title in historical[:8]:
            print(f"       {vid_} 「{title[:52]}」")

    for g in ghosts:
        r = by_vid.get(g, {})
        print(f"  ⚠ 幽灵 Ep{r.get('episode_number')} {g} —— 主表说已上传,"
              f"平台上找不到(被删?被拒?)")
    if not ghosts:
        print("  ✅ 无幽灵:主表在册的每条都在平台上")

    return 0 if (not danger and not ghosts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
