#!/usr/bin/env python3
# coding: utf-8
"""筛查「说话人自比上帝」的原子 —— 神学红线,必须销毁。

危险来源:母带里有大量**经文引用**,其中上帝以第一人称说话
("I am with you", "I will strengthen you")。这些句子在原文里由引号和
"says" 框住,合法;但一旦被切成独立原子、脱离引文框架,再拼进以
「我/我们」向上帝祷告的段落里,说话人就变成了自称神性 —— 渎神。

  原文:Isaiah 41:10 says, "So do not fear, for I am with you."   ← 合法
  原子:"For I am with you."                                      ← 危险
  拼进:"Lord, we come to You. ... For I am with you."            ← 渎神

判定:第一人称 + 只有上帝能做的动作/断言(神性谓词)。
分三级:
  RED    明确自称神性,必须销毁(quarantine)
  AMBER  疑似,需人工听后定夺
  QUOTE  能证明是引文(原子内自带 says / 引号 / 书卷名)—— 保留但标记,
         编排时必须与其引文头连用,不可单独出现

  ./.venv/bin/python scripts/sg/screen_blasphemy.py            # 只报告
  ./.venv/bin/python scripts/sg/screen_blasphemy.py --quarantine  # 标记隔离
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
CONF = Path(__file__).resolve().parents[2] / "config"
REPORT = CONF / "sg_blasphemy_review.md"
DATA = CONF / "sg_blasphemy_review.json"

FIRST = r"\b(i|i'll|i'm|i've|my|me)\b"

# 只有上帝能做/能说的 —— 第一人称 + 这些 = 自称神性
DIVINE_PREDICATE = [
    (r"\bi am with (you|thee)\b", "我与你同在"),
    (r"\bi (will|shall) (never )?(leave|forsake|abandon)\b", "我必不撇下你"),
    (r"\bi (will|shall) (strengthen|uphold|help|sustain|keep)\b", "我必坚固/扶持你"),
    (r"\bi (give|grant|bestow) (you|them) (eternal life|rest|peace|my peace)\b",
     "我赐你永生/安息/平安"),
    (r"\bi (have )?(called|chosen|redeemed) you\b", "我拣选/救赎了你"),
    (r"\bi am (the|your) (lord|god|way|truth|life|light|shepherd|alpha)\b",
     "我是主/道路/真理"),
    # 只有「我的**公义的**右手」是上帝自称(赛 41:10);
    # 「他在我右边」(诗 16:8)的说话人是诗人,不算自比上帝
    (r"\bmy righteous right hand\b", "我公义的右手"),
    (r"\bwith my right hand i\b", "我用右手"),
    (r"\bi know the plans i have for you\b", "我知道我向你所怀的意念"),
    (r"\bcome to me\b", "到我这里来"),
    (r"\bmy yoke\b|\bmy burden is light\b", "我的轭/我的担子"),
    (r"\bi (will|shall) be with you\b", "我必与你同在"),
    (r"\bsurely i am with you\b", "我就常与你们同在"),
]

# 引文证据 —— 原子内自带这些说明它还在引文框架里
QUOTE_MARK = re.compile(
    r"\bsays?\b|\bsaid\b|\bdeclares?\b|\bpromises?\b|[\"“”]|"
    r"\b(genesis|exodus|deuteronomy|joshua|psalms?|proverbs|isaiah|jeremiah|"
    r"lamentations|ezekiel|daniel|zephaniah|matthew|mark|luke|john|romans|"
    r"corinthians|philippians|colossians|hebrews|james|peter|revelation)\b",
    re.I)


def scan(text: str) -> tuple[str, list[str]]:
    t = " " + text.lower().replace("’", "'") + " "
    hits = [label for pat, label in DIVINE_PREDICATE if re.search(pat, t)]
    if not hits:
        return "OK", []
    if QUOTE_MARK.search(text):
        return "QUOTE", hits
    # 第一人称必须真的在句中(避免 "my soul" 这类被上面误抓)
    if not re.search(FIRST, t):
        return "AMBER", hits
    return "RED", hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarantine", action="store_true",
                    help="把 RED 标记为 quarantined,出片时排除")
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text())
    atoms = [x for x in man["atoms"] if x.get("text")]

    buckets: dict[str, list[dict]] = {"RED": [], "AMBER": [], "QUOTE": []}
    for x in atoms:
        v, hits = scan(x["text"])
        if v == "OK":
            continue
        buckets[v].append({**{k: x[k] for k in ("id", "path", "role", "text")},
                           "addressee": x.get("addressee"),
                           "duration": x.get("duration_sec"), "hits": hits})

    print("=== 自比上帝 筛查 ===")
    for k, label in (("RED", "明确自称神性(销毁)"),
                     ("AMBER", "疑似(人工定夺)"),
                     ("QUOTE", "引文框架内(保留但须与引文头连用)")):
        print(f"  {label:<32} {len(buckets[k]):>4}")

    for k in ("RED", "AMBER"):
        if buckets[k]:
            print(f"\n--- {k} ---")
            for r in buckets[k][:12]:
                print(f"  {r['id']:<22} [{r['addressee']}] {r['text'][:56]}")
                print(f"    ↳ {', '.join(r['hits'])}")

    DATA.write_text(json.dumps(
        {"generated": datetime.now(timezone.utc).isoformat(),
         "counts": {k: len(v) for k, v in buckets.items()},
         "buckets": buckets}, ensure_ascii=False, indent=1))

    md = ["# 自比上帝 · 筛查结果", "",
          "母带含大量经文引用,其中上帝以第一人称说话。这些句子在原文里由",
          "`says` 与引号框住是合法的;一旦被切成独立原子、脱离引文框架,",
          "再拼进以「我/我们」向上帝祷告的段落,说话人就成了自称神性。", ""]
    for k, label in (("RED", "🔴 明确自称神性 —— 销毁"),
                     ("AMBER", "🟡 疑似 —— 人工听后定夺"),
                     ("QUOTE", "🔵 引文框架内 —— 保留,但编排时必须与引文头连用")):
        md += [f"## {label}({len(buckets[k])} 条)", "",
               "| 原子 | 角色 | addressee | 文本 | 命中 |",
               "|---|---|---|---|---|"]
        for r in buckets[k]:
            md.append(f"| `{r['id']}` | {r['role']} | {r['addressee']} | "
                      f"{r['text'][:56]} | {', '.join(r['hits'])} |")
        md.append("")
    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"\n报告 → {REPORT.name}")

    if a.quarantine and buckets["RED"]:
        ids = {r["id"] for r in buckets["RED"]}
        stamp = datetime.now().strftime("%Y%m%d")
        bak = MANIFEST.with_suffix(f".json.bak_quarantine_{stamp}")
        if not bak.exists():
            bak.write_text(MANIFEST.read_text())
        for x in man["atoms"]:
            if x["id"] in ids:
                x["quarantined"] = "self-deification"
                x["quarantined_at"] = datetime.now(timezone.utc).isoformat()
        MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
        print(f"🔒 已隔离 {len(ids)} 条(备份 {bak.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
