#!/usr/bin/env python3
# coding: utf-8
"""按 atom-faithful 计划拼出该期 VO — 全部为 Locke 真实录音,零合成。

原子间插入静默,长度按语义分级(祷告需要留白):
  同段落内   GAP        1.6 s
  逗号收尾   GAP_HALF   0.9 s   (半句,接得紧一些)
  段落之间   GAP_SECTION 3.2 s
  开头       LEAD       1.0 s

输出 <ep>_vo.mp3 + <ep>_vo_timeline.json(每句的起止,供 SRT 精确对时)。

  ./.venv/bin/python scripts/sg/render_vo.py --episodes 1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

BD = Path.home() / ("Studio/Workspace/outputs/sg/sessions/"
                    "sg_toytune_ep1/text_batch_10")
PLANS = BD / "atom_faithful"
SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"

LEAD, GAP, GAP_HALF, GAP_SECTION = 1.0, 1.6, 0.9, 3.2
SR = 48000


def probe(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, required=True)
    a = ap.parse_args()
    n = a.episodes

    plan = json.loads((PLANS / f"sg_text_ep{n:02d}.json").read_text())
    eid = f"sg_ep{n:02d}"
    out_dir = SESSIONS / eid
    out_dir.mkdir(parents=True, exist_ok=True)

    items = plan["plan"]
    missing = [i["id"] for i in items if not Path(i["path"]).exists()]
    if missing:
        print(f"⛔ 缺原子音频 {len(missing)} 个: {missing[:5]}")
        return 1

    # 排 timeline:先算每句起止,再据此产 SRT/字幕
    timeline, t = [], LEAD
    prev_sec = None
    for i, it in enumerate(items):
        if prev_sec is not None and it["section"] != prev_sec:
            t += GAP_SECTION - GAP
        dur = probe(Path(it["path"]))
        timeline.append({"id": it["id"], "section": it["section"],
                         "text": it["text"], "start": round(t, 3),
                         "end": round(t + dur, 3)})
        gap = GAP_HALF if it["text"].rstrip().endswith((",", ";", "—", "-")) else GAP
        t += dur + gap
        prev_sec = it["section"]
    total = t + 2.0

    # 用 concat + adelay 精确落位:每个原子按 timeline 起点延迟后混合
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        inputs, filters, labels = [], [], []
        for k, (it, tl) in enumerate(zip(items, timeline)):
            inputs += ["-i", it["path"]]
            ms = int(tl["start"] * 1000)
            filters.append(f"[{k}:a]aresample={SR},adelay={ms}|{ms}[d{k}]")
            labels.append(f"[d{k}]")
        fc = ";".join(filters) + ";" + "".join(labels) + \
            f"amix=inputs={len(items)}:duration=longest:normalize=0," \
            f"apad,atrim=0:{total:.3f},loudnorm=I=-19:TP=-2:LRA=8[out]"
        vo = out_dir / f"{eid}_vo.mp3"
        cmd = (["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"]
               + inputs + ["-filter_complex", fc, "-map", "[out]",
                           "-c:a", "libmp3lame", "-b:a", "192k", str(vo)])
        print(f"拼接 {len(items)} 个原子 → {vo.name} …", flush=True)
        if subprocess.run(cmd).returncode != 0:
            return 1

    (out_dir / f"{eid}_vo_timeline.json").write_text(json.dumps({
        "episode_id": eid, "source_plan": str(PLANS / f"sg_text_ep{n:02d}.json"),
        "atoms": len(items), "duration_sec": round(probe(vo), 1),
        "gaps": {"lead": LEAD, "gap": GAP, "half": GAP_HALF,
                 "section": GAP_SECTION},
        "timeline": timeline}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {vo}  {probe(vo)/60:.1f} 分钟 · {len(items)} 句")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
