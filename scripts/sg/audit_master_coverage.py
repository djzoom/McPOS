#!/usr/bin/env python3
# coding: utf-8
"""母带覆盖审计 —— 用波形找出「说了但没被任何原子收录」的语音。

比逐条重听可靠得多,也快得多:
  · 逐条重听要跑 965 次 whisper,只能回答「这条多出了词吗」
  · 扫波形只需 13 次(每个母带一次),能直接回答「哪一段语音掉了」,
    而且精确到毫秒

2026-08-05 的事故就是这么产生的(约翰福音 14:1):

    母带      166.9 ─ 170.7  "Do not let your hearts be troubled."
    原子边界        168.8 ─ 170.7
    掉在外面  166.9 ─ 168.8  "Do not"        ← 没有任何原子覆盖

结果入库文本变成 "Let your hearts be troubled.",意思完全相反。这条原子
语法完整、首字母大写、句末有句号,句法检查一律放行 —— 只有比对波形与
覆盖区间才看得见。

做法:
  ① silencedetect 扫出母带的静音区间 → 取补集得到**语音区间**
  ② 合并该母带所有原子的 [t_start, t_end] → **覆盖区间**
  ③ 语音区间减去覆盖区间 = 漏掉的语音,按时长排序
  ④ 只对漏掉的那几段转写,看丢了什么词

  ./.venv/bin/python scripts/sg/audit_master_coverage.py
  ./.venv/bin/python scripts/sg/audit_master_coverage.py --transcribe
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import harvest_whisper as hw

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
CONF = Path(__file__).resolve().parents[2] / "config"
NOISE_DB = -45          # 与 trim_atom_edges 保持一致
MIN_SIL = 0.15          # 短于此的停顿算在语音内(句中换气)
MIN_GAP = 0.25          # 短于此的漏音不足一个词,忽略
Span = tuple[float, float]


def silences(path: Path) -> list[Span]:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af",
         f"silencedetect=noise={NOISE_DB}dB:d={MIN_SIL}", "-f", "null", "-"],
        capture_output=True, text=True)
    out: list[Span] = []
    cur: float | None = None
    for kind, val in re.findall(r"silence_(start|end): ([-\d.]+)", r.stderr):
        v = float(val)
        if kind == "start":
            cur = v
        elif cur is not None:
            out.append((cur, v))
            cur = None
    if cur is not None:
        out.append((cur, float("inf")))
    return out


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def invert(spans: list[Span], total: float) -> list[Span]:
    """静音区间取补集 = 语音区间。"""
    out: list[Span] = []
    cur = 0.0
    for s, e in sorted(spans):
        if s > cur:
            out.append((cur, min(s, total)))
        cur = max(cur, min(e, total))
    if cur < total:
        out.append((cur, total))
    return [(s, e) for s, e in out if e - s > 0.01]


def merge(spans: list[Span]) -> list[Span]:
    out: list[Span] = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1] + 0.01:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def subtract(base: list[Span], cover: list[Span]) -> list[Span]:
    """base 减去 cover。"""
    out: list[Span] = []
    for s, e in base:
        cur = s
        for cs, ce in cover:
            if ce <= cur or cs >= e:
                continue
            if cs > cur:
                out.append((cur, min(cs, e)))
            cur = max(cur, ce)
            if cur >= e:
                break
        if cur < e:
            out.append((cur, e))
    return [(s, e) for s, e in out if e - s >= MIN_GAP]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcribe", action="store_true",
                    help="对漏掉的语音段转写,看丢了什么词")
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text())
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for x in man["atoms"]:
        by[x.get("source_master", "?")].append(x)

    rows: list[dict] = []
    print(f"扫描 {len(by)} 个母带的波形…\n")
    for m, items in sorted(by.items()):
        p = Path(m)
        if not p.exists():
            print(f"  ✗ 母带缺失 {p.name[:50]}")
            continue
        total = duration(p)
        speech = invert(silences(p), total)
        # 覆盖要算上**已隔离**的原子 —— 它们是被主动排除的(自比上帝、无语音),
        # 不是采集时漏掉的。把两者混在一起会让「赛41:10 上帝第一人称」这类
        # 刻意隔离的内容混进「未采集」清单,数字就没法用了。
        cover = merge([(float(x["t_start"]), float(x["t_end"])) for x in items])
        lost = subtract(speech, cover)
        spoken = sum(e - s for s, e in speech)
        missed = sum(e - s for s, e in lost)
        print(f"  {p.name[:52]}")
        print(f"    时长 {total/60:5.1f}min · 语音 {spoken/60:4.1f}min · "
              f"原子覆盖 {sum(e-s for s,e in cover)/60:4.1f}min")
        print(f"    ▶ 从未采集 {missed:6.1f}s,分 {len(lost)} 段"
              f"({missed/max(0.01,spoken):.1%})")
        for s, e in lost:
            rows.append({"master": m, "start": round(s, 3), "end": round(e, 3),
                         "sec": round(e - s, 3)})

    rows.sort(key=lambda r: -r["sec"])
    print(f"\n=== 合计漏掉 {len(rows)} 段 · "
          f"{sum(r['sec'] for r in rows):.0f} 秒 ===")

    if a.transcribe and rows:
        model = hw.resolve_model(None)
        top = rows[:400]
        print(f"\n转写其中最长的 {len(top)} 段…")
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            wavs = []
            for i, r in enumerate(top):
                w = d / f"{i:04d}.wav"
                q = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-ss", f"{r['start']:.3f}",
                     "-to", f"{r['end']:.3f}", "-i", r["master"],
                     "-ar", "16000", "-ac", "1", str(w)],
                    capture_output=True, text=True)
                if q.returncode == 0 and w.exists():
                    wavs.append((i, w))
            for b in range(0, len(wavs), 120):
                subprocess.run(
                    ["whisper-cli", "-m", str(model), "-nt", "-l", "en", "-otxt"]
                    + [str(w) for _, w in wavs[b:b + 120]],
                    capture_output=True, text=True)
            for i, w in wavs:
                t = Path(str(w) + ".txt")
                if t.exists():
                    top[i]["heard"] = " ".join(
                        t.read_text(errors="ignore").split()).strip()
        print(f"\n--- 漏掉的语音内容(前 30 段)---")
        for r in top[:30]:
            h = r.get("heard", "")
            if h:
                print(f"  {r['sec']:5.1f}s  {h[:64]}")

    CONF.mkdir(exist_ok=True)
    (CONF / "sg_master_coverage.json").write_text(json.dumps(
        {"generated": datetime.now(timezone.utc).isoformat(),
         "noise_db": NOISE_DB, "min_gap": MIN_GAP, "lost": rows},
        ensure_ascii=False, indent=1))
    print(f"\n明细 → config/sg_master_coverage.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
