#!/usr/bin/env python3
# coding: utf-8
"""SiG 英文文案缺陷审计器 — 打磨环节的前置证据收集。

text-first 文案由 Whisper 转写原子拼接而成,常见拼接伤:
  DUP    重复/近重复句(转写变体,如 "It's nothing you need to do…")
  MERGE  两句拼一句(句中出现第二个大写句首,句号丢失)
  FRAG   孤立残句(无谓语/以连词或介词开头且不接续)
  DANGLE 及物动词悬空(abandon/forget/hold 等后面直接句号)
  LOWER  句号后小写开头(切点缝)
  ECHO   相邻句 >70% 词重叠(同义重复拼接)

  ./.venv/bin/python scripts/sg/audit_text_batch.py            # 全部十期
  ./.venv/bin/python scripts/sg/audit_text_batch.py --episodes 1
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BATCH_DIR = Path.home() / ("Studio/Workspace/outputs/sg/sessions/"
                           "sg_toytune_ep1/text_batch_10")

TRANSITIVE_DANGLE = {"abandon", "abandons", "forsake", "forsakes",
                     "carry", "carries", "bring", "brings"}
FRAG_STARTERS = {"when", "if", "that", "which", "while", "though", "although"}
# 祷告文的专名与品牌词:句中出现大写不算拼接缝
PROPER = {"I", "God", "Lord", "Jesus", "Christ", "Father", "Spirit", "Holy",
          "He", "His", "Him", "You", "Your", "Sleep", "Grace", "Most", "High",
          "Almighty", "Shepherd", "Amen",
          "Genesis", "Exodus", "Numbers", "Deuteronomy", "Joshua", "Psalm",
          "Psalms", "Proverbs", "Isaiah", "Jeremiah", "Lamentations",
          "Matthew", "Mark", "Luke", "John", "Romans", "Philippians",
          "Colossians", "Hebrews", "James", "Peter", "Revelation",
          "Zephaniah", "Ecclesiastes", "Israel", "Behold"}


def sentences(text: str) -> list[str]:
    # 按句末标点切,保留原文顺序
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def overlap(a: str, b: str) -> float:
    wa, wb = set(norm(a).split()), set(norm(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def audit_text(text: str) -> list[dict]:
    defects: list[dict] = []
    sents = sentences(text)
    seen: dict[str, int] = {}
    for i, s in enumerate(sents):
        n = norm(s)
        # DUP: 完全/近重复(与任意前句)
        if n in seen:
            defects.append({"type": "DUP", "at": i, "text": s,
                            "note": f"与句 {seen[n]} 完全重复"})
        else:
            def _dup_with(j: int, prev_n: str) -> bool:
                # 主语互换的对句(You just need… / I just need…)是修辞,
                # 只认两类真重复:同首词高重叠,或词序列包含(转写尾巴)。
                if len(n) <= 12:
                    return False
                same_head = n.split()[0] == prev_n.split()[0]
                shorter_words = min(len(n.split()), len(prev_n.split()))
                contained = shorter_words >= 5 and \
                    ((f" {n} " in f" {prev_n} ") or (f" {prev_n} " in f" {n} "))
                if contained:
                    return True
                return same_head and overlap(s, sents[j]) > 0.8 \
                    and abs(len(n) - len(prev_n)) < 15
            for prev_n, j in seen.items():
                if _dup_with(j, prev_n):
                    defects.append({"type": "DUP", "at": i, "text": s,
                                    "note": f"与句 {j} 近重复: {sents[j][:40]}"})
                    break
            seen[n] = i
        # MERGE: 句中「小写词后接大写」缝;专名与 says, 后的引文起始豁免
        for m in re.finditer(r"[a-z0-9]\s+([A-Z][a-z]+)\s", s):
            w = m.group(1)
            if w in PROPER:
                continue
            head = s[: m.start() + 1]
            if re.search(r"says?,?\s*$", head):      # 经文引文的起始大写
                continue
            defects.append({"type": "MERGE", "at": i, "text": s,
                            "note": f"疑似两句拼接于「{w}」"})
            break
        # DANGLE: 及物动词直接句号
        m = re.search(r"\b(\w+)[.!?]$", s)
        if m and m.group(1).lower() in TRANSITIVE_DANGLE:
            if not re.search(r"[a-z]+\s+(we|you|they|i)\s+"
                             r"(cannot|can't|could not|do not|don't|will not|"
                             r"won't|must)?\s*\w+[.!?]$", s, re.I):
                defects.append({"type": "DANGLE", "at": i, "text": s,
                                "note": f"及物动词「{m.group(1)}」悬空"})
        # LOWER: 小写开头(切缝)
        if s and s[0].islower():
            defects.append({"type": "LOWER", "at": i, "text": s,
                            "note": "句首小写(切点缝)"})
        # 排比(首语重复)豁免:相邻句同首词 = 刻意连祷节奏
        def _first(k):
            w = norm(sents[k]).split()
            return w[0] if w else ""
        CONT = {"and", "or", "but", "so"}
        anaphora = (i > 0 and _first(i) == _first(i - 1)) or \
                   (i + 1 < len(sents) and _first(i) == _first(i + 1)) or \
                   (i + 1 < len(sents) and _first(i + 1) in CONT) or \
                   (i > 0 and _first(i) in CONT and _first(i - 1) not in CONT)
        # FRAG: 从属连词开头且短,且非排比
        first = _first(i)
        if first in FRAG_STARTERS and len(norm(s).split()) <= 5 and not anaphora:
            defects.append({"type": "FRAG", "at": i, "text": s,
                            "note": "疑似孤立残句"})
        # ECHO: 极高重叠且非排比
        if i > 0 and not anaphora and overlap(s, sents[i - 1]) > 0.85 \
                and len(norm(s)) > 10:
            defects.append({"type": "ECHO", "at": i, "text": s,
                            "note": f"与前句同义重复: {sents[i-1][:40]}"})
        # WORDDUP: 词组重叠("the burdens the burdens")
        m = re.search(r"\b(\w+\s+\w+)\s+\1\b", s, re.I)
        if m:
            defects.append({"type": "WORDDUP", "at": i, "text": s,
                            "note": f"词组重叠「{m.group(1)}」"})
    return defects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default="1-10")
    a = ap.parse_args()
    if "-" in a.episodes:
        lo, hi = a.episodes.split("-")
        nums = range(int(lo), int(hi) + 1)
    else:
        nums = [int(a.episodes)]

    total = 0
    report = {}
    for n in nums:
        p = BATCH_DIR / f"sg_text_ep{n:02d}.json"
        src = json.loads(p.read_text())
        body = " ".join(x["text"].strip() for x in src["plan"])
        defects = audit_text(body)
        report[f"ep{n:02d}"] = defects
        total += len(defects)
        print(f"ep{n:02d}: {len(defects):3d} 处缺陷 "
              f"({', '.join(sorted({d['type'] for d in defects})) or '—'})")
        for d in defects[:6]:
            print(f"    [{d['type']}] {d['text'][:64]}  ← {d['note'][:44]}")
        if len(defects) > 6:
            print(f"    … 其余 {len(defects) - 6} 处见报告")
    out = BATCH_DIR / "english_audit_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\n共 {total} 处;完整报告 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
