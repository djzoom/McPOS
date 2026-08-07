#!/usr/bin/env python3
# coding: utf-8
"""VO 质检 — 把渲染出的音频用 whisper 转录回来,与剧本逐词比对。

这是最硬的验收:音频真正说出的话,必须与剧本一致。检四项:

  WER      整体词错误率(转写噪声容忍上限 6%)
  漏句     剧本里有、音频里找不到的句子(必须 0)
  串词     相邻句边界处的词序错乱(拼接事故)
  静默     句间间隔是否落在设计范围(1.6/0.9/3.2 s ±35%)

  ./.venv/bin/python scripts/sg/qc_vo.py --episodes 1
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
WER_LIMIT = 0.06
GAP_TOL = 0.35


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()


def wer(ref: list[str], hyp: list[str]) -> float:
    sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    same = sum(b.size for b in sm.get_matching_blocks())
    return 1.0 - same / max(1, len(ref))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, required=True)
    a = ap.parse_args()
    eid = f"sg_ep{a.episodes:02d}"
    D = SESSIONS / eid

    tl = json.loads((D / f"{eid}_vo_timeline.json").read_text())
    stt = json.loads((D / "_qc.json").read_text())
    segs = stt.get("transcription") or []
    hyp_text = " ".join((s.get("text") or "").strip() for s in segs)
    hyp = words(hyp_text)
    ref = words(" ".join(t["text"] for t in tl["timeline"]))

    problems: list[str] = []

    # ① 整体 WER
    w = wer(ref, hyp)
    print(f"① WER {w:.1%}  (剧本 {len(ref)} 词 / 转录 {len(hyp)} 词)")
    if w > WER_LIMIT:
        problems.append(f"WER {w:.1%} 超过 {WER_LIMIT:.0%}")

    # ② 漏句:每句的词序列必须能在转录里连续找到
    hyp_join = " " + " ".join(hyp) + " "
    missing = []
    for t in tl["timeline"]:
        sw = words(t["text"])
        if not sw:
            continue
        if " " + " ".join(sw) + " " in hyp_join:
            continue
        # 容忍单词级转写差异:取 80% 最长匹配
        sm = difflib.SequenceMatcher(a=sw, b=hyp, autojunk=False)
        m = max((b.size for b in sm.get_matching_blocks()), default=0)
        if m / len(sw) < 0.8:
            missing.append(t)
    print(f"② 漏句 {len(missing)}")
    for t in missing[:6]:
        print(f"     ✗ [{t['start']:.1f}s] {t['text'][:66]}")
    if missing:
        problems.append(f"{len(missing)} 句在音频中找不到")

    # ③ 错位:每句在音频里"实际被说出"的时刻,应落在其 timeline 窗口内。
    #    用 whisper 分段时间戳判定 —— 词序相邻是转录的必然,不能当证据
    #    (2026-08-05 第一版误报 53 处,教训:判据必须用时间不用词序)。
    def seg_span(text_words):
        """返回转录中匹配该词序列的时间区间。"""
        best = None
        for s in segs:
            sw = words(s.get("text") or "")
            if not sw:
                continue
            ov = len(set(text_words) & set(sw)) / max(1, len(set(text_words)))
            o = s.get("offsets", {})
            if ov >= 0.6:
                a, b = o.get("from", 0) / 1000, o.get("to", 0) / 1000
                best = (a, b) if best is None else (min(best[0], a), max(best[1], b))
        return best

    drift = []
    for t in tl["timeline"]:
        sw = words(t["text"])
        if len(sw) < 3:
            continue
        sp = seg_span(sw)
        if sp is None:
            continue
        if sp[1] < t["start"] - 2.5 or sp[0] > t["end"] + 2.5:
            drift.append((t, sp))
    print(f"③ 时间错位 {len(drift)}")
    for t, sp in drift[:5]:
        print(f"     ✗ 剧本 [{t['start']:.1f}] 实听 [{sp[0]:.1f}] {t['text'][:52]}")
    if drift:
        problems.append(f"{len(drift)} 句音频位置与剧本错位")

    # ④ 静默:实际间隔应等于设计值
    gaps = tl["gaps"]
    bad_gap = 0
    for i in range(len(tl["timeline"]) - 1):
        cur, nxt = tl["timeline"][i], tl["timeline"][i+1]
        g = nxt["start"] - cur["end"]
        if cur["section"] != nxt["section"]:
            want = gaps["section"]
        elif cur["text"].rstrip().endswith((",", ";", "—", "-")):
            want = gaps["half"]
        else:
            want = gaps["gap"]
        if abs(g - want) > want * GAP_TOL:
            bad_gap += 1
    print(f"④ 间隔异常 {bad_gap} / {len(tl['timeline'])-1}")
    if bad_gap:
        problems.append(f"{bad_gap} 处句间静默偏离设计值")

    print()
    if problems:
        print("⛔ QC 未通过:")
        for p in problems:
            print("   ·", p)
        return 1
    print(f"✅ QC 通过 — {eid} 音频与剧本一致,可冻结管线")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
