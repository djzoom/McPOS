#!/usr/bin/env python3
# coding: utf-8
"""运营日志 —— 把当日事实从各处**现场汇总**成一条不可变记录。

不手写快照:手抄的数字第二天就过时,而且没人知道它是何时抄的。
这里的每一项都从磁盘上的真实产物读出来:

    素材库   manifest.json(可用池/隔离分布/白名单)
    成品     sessions/*/[_session.json,_rings.mp4,字幕]
    长片发布 config/sg_schedule_master.json(video_id/status/排期)
    短片发布 TOYTUNE/publish_state.json(video_id/评论挂起)
    配额     config/sg_quota_ledger.json(当日窗口用量)

一天一条,追加进 config/sg_ops_log.jsonl(JSONL:只追加,不改写历史),
同时渲染成人读的 Markdown 摘要。运营指标的价值在**趋势**,所以
落盘的是逐日的机器可读行,而不是一份被反复覆盖的当前状态。

  ./.venv/bin/python scripts/sg/ops_log.py            # 打印今日摘要
  ./.venv/bin/python scripts/sg/ops_log.py --append   # 追加进日志
  ./.venv/bin/python scripts/sg/ops_log.py --history  # 回看趋势
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atom_quality import load_whitelist, reject_reason

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "config" / "sg_ops_log.jsonl"
MASTER = ROOT / "config" / "sg_schedule_master.json"
LEDGER = ROOT / "config" / "sg_quota_ledger.json"
MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
SHORTS_STATE = Path.home() / "Projects/TOYTUNE/publish_state.json"
SHORTS_SCHED = Path.home() / "Projects/TOYTUNE/shorts_schedule.json"


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def collect() -> dict:
    # —— 素材库 ——
    man = _load(MANIFEST, {"atoms": []})
    atoms = man.get("atoms", [])
    try:
        wl = load_whitelist()
    except Exception:
        wl = None
    usable = [a for a in atoms if reject_reason(a, wl) is None]
    quarantine: dict[str, int] = {}
    for a in atoms:
        q = a.get("quarantined")
        if q:
            quarantine[q] = quarantine.get(q, 0) + 1

    # —— 成品(以 session.json 为准,顺带核对视频与中文字幕是否齐)——
    episodes = []
    for d in sorted(SESSIONS.glob("sg_gold_*")):
        meta = _load(d / f"{d.name}_session.json", None)
        if not meta:
            continue
        episodes.append({
            "id": d.name,
            "minutes": round(float(meta.get("total_duration_sec") or 0) / 60, 1),
            "atoms": meta.get("atom_count_used"),
            "vo_score": (meta.get("vo_score") or {}).get("score"),
            "video": (d / f"{d.name}_rings.mp4").exists(),
            "zh_srt": (d / f"{d.name}.zh-Hans.srt").exists(),
            "cover": (d / f"{d.name}_cover.jpg").exists(),
        })

    # —— 长片发布 ——
    master = _load(MASTER, {"episodes": []})
    longs = [{"n": r.get("episode_number"), "date": r.get("schedule_date"),
              "status": r.get("status"), "video_id": r.get("video_id")}
             for r in master.get("episodes", [])]

    # —— 短片发布 ——
    sstate = _load(SHORTS_STATE, {"uploaded": {}}).get("uploaded", {})
    ssched = _load(SHORTS_SCHED, {"episodes": []}).get("episodes", [])
    shorts = {
        "rendered": len(ssched),
        "uploaded": len(sstate),
        "comment_pending": sorted(int(k) for k, v in sstate.items()
                                  if v.get("comment_pending")),
        "last_publish_at": max((v.get("publish_at", "") for v in sstate.values()),
                               default=None),
    }

    # —— 配额(当日窗口)——
    led = _load(LEDGER, {})
    return {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "library": {
            "total": len(atoms), "usable": len(usable),
            "unique_texts": len({(a.get("text") or "").strip().lower()
                                 for a in usable}),
            "quarantine": quarantine,
        },
        "episodes": episodes,
        "long_form": longs,
        "shorts": shorts,
        "quota": {"window": led.get("window"), "spent": led.get("spent"),
                  "calls": len(led.get("calls") or [])},
    }


def render(s: dict) -> str:
    lib, q = s["library"], s["quota"]
    eps, longs, sh = s["episodes"], s["long_form"], s["shorts"]
    published = [e for e in longs if e.get("video_id")]
    complete = [e for e in eps if e["video"] and e["zh_srt"] and e["cover"]]
    out = [f"# SG 运营日志 · {s['at'][:10]}", ""]
    out.append(f"**素材库** 可用 {lib['usable']}/{lib['total']} 条 · "
               f"唯一文案 {lib['unique_texts']} · "
               f"隔离 {sum(lib['quarantine'].values())}"
               f"({', '.join(f'{k} {v}' for k, v in sorted(lib['quarantine'].items()))})")
    out.append(f"**成品** {len(eps)} 期 · 六件齐备 {len(complete)} 期 · "
               f"合计 {sum(e['minutes'] for e in eps):.0f} 分钟")
    out.append(f"**长片发布** 已上线 {len(published)}/{len(longs)} 期 · "
               f"排期至 {max((e['date'] or '') for e in longs) if longs else '—'}")
    out.append(f"**短片发布** 已传 {sh['uploaded']}/{sh['rendered']} 条 · "
               f"评论待补发 {len(sh['comment_pending'])} 条")
    out.append(f"**配额** {q['window']} 已用 {q['spent']}u / 10000u "
               f"({q['calls']} 次调用)")
    out += ["", "| 期 | 时长 | 原子 | VO | 视频 | 中字 | 封面 | 排期 | 状态 |",
            "|---|---:|---:|---:|:-:|:-:|:-:|---|---|"]
    by_id = {f"sg_gold_{e['n']:03d}": e for e in longs if e.get("n")}
    for e in eps:
        p = by_id.get(e["id"], {})
        y = lambda b: "✅" if b else "—"
        out.append(f"| {e['id'][-3:]} | {e['minutes']}m | {e['atoms']} | "
                   f"{e['vo_score']} | {y(e['video'])} | {y(e['zh_srt'])} | "
                   f"{y(e['cover'])} | {p.get('date','—')} | "
                   f"{p.get('status','—')} |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--append", action="store_true", help="追加进 sg_ops_log.jsonl")
    ap.add_argument("--history", action="store_true", help="回看历史趋势")
    a = ap.parse_args()

    if a.history:
        if not LOG.exists():
            print("暂无历史记录")
            return 0
        print(f"{'日期':<12}{'可用原子':>8}{'成品':>6}{'长片上线':>9}{'短片':>7}{'配额':>8}")
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            s = json.loads(line)
            pub = sum(1 for e in s["long_form"] if e.get("video_id"))
            print(f"{s['at'][:10]:<12}{s['library']['usable']:>8}"
                  f"{len(s['episodes']):>6}{pub:>9}"
                  f"{s['shorts']['uploaded']:>7}{s['quota']['spent'] or 0:>8}")
        return 0

    snap = collect()
    print(render(snap))
    if a.append:
        # 同日重跑覆盖当日那条,历史行不动 —— 一天一条事实,不是一天多条草稿
        rows = []
        if LOG.exists():
            rows = [json.loads(x) for x in
                    LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
        rows = [r for r in rows if r["at"][:10] != snap["at"][:10]] + [snap]
        rows.sort(key=lambda r: r["at"])
        LOG.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
                       + "\n", encoding="utf-8")
        print(f"\n📝 已记入 {LOG.relative_to(ROOT)}({len(rows)} 条)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
