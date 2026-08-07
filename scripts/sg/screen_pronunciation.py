#!/usr/bin/env python3
# coding: utf-8
"""发音筛查 — 找出 ElevenLabs 念错的原子(粗筛),产出人工细筛队列。

原理:母带是 ElevenLabs 用**原始脚本**合成的。脚本说的是「应该念什么」,
whisper 听到的是「实际念了什么」。两者在同一位置对不上,就是发音可疑点。

  脚本(应念)  ──┐
                 ├── 序列对齐 ── 差异点 ── 排除转写噪声 ── 人工细筛队列
  whisper(实念)─┘

排除的噪声类型:大小写/标点、数字与拼写形式(4 vs four)、常见同音异形
(their/there)、以及 whisper 对静音的幻听。剩下的才送人工听。

母带与脚本的配对用**内容重合度**而非文件名 —— 文件名会错配
(Isaiah26 的母带曾被错配到 Isaiah41 的脚本)。

  ./.venv/bin/python scripts/sg/screen_pronunciation.py --pair    # 只看配对
  ./.venv/bin/python scripts/sg/screen_pronunciation.py           # 全流程
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

VO = Path.home() / "Studio/Library/sg/assets/vo"
DOCS = Path.home() / "Documents/文档"
MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
CONF = Path(__file__).resolve().parents[2] / "config"
QUEUE = CONF / "sg_pronunciation_review.json"
SHEET = CONF / "sg_pronunciation_review.md"

# whisper 与脚本之间的正常差异,不算念错
HOMOPHONE_OK = {
    frozenset(("their", "there")), frozenset(("your", "you're")),
    frozenset(("its", "it's")), frozenset(("thy", "the")),
    frozenset(("oh", "o")), frozenset(("lord", "lord's")),
    frozenset(("god", "god's")), frozenset(("towards", "toward")),
    frozenset(("amen", "amen")),
}
NUM_WORDS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
             "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
             "10": "ten", "11": "eleven", "12": "twelve", "13": "thirteen",
             "20": "twenty", "21": "twentyone", "22": "twentytwo",
             "27": "twentyseven", "28": "twentyeight", "30": "thirty"}
NUMWORD = {v: k for k, v in NUM_WORDS.items()}
NUMWORD.update({"twenty": "20", "seven": "7", "one": "1", "two": "2",
                "three": "3", "eight": "8"})


TTS_MARKUP = re.compile(
    r"<[^>]*>|\[[^\]]*\]|\bbreak\s*time\s*[\d.]+\s*s?\b|"
    r"\bpause\b|\bssml\b|\bprosody\b", re.I)


def words(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("—", " ").replace("–", " ")
    s = TTS_MARKUP.sub(" ", s)          # 脚本里的 TTS 控制标记不是要念的词
    return re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()


UNITS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,
         "seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,
         "thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,
         "seventeen":17,"eighteen":18,"nineteen":19}
TENS = {"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,
        "seventy":70,"eighty":80,"ninety":90}


def numeric(seq: list[str]) -> str:
    """把「ten twenty seven」与「10 27」归一成同一串数字。

    英文口读的复合数(twenty seven = 27)必须先合并,否则
    「ten twenty seven」会变成 10-20-7 而不是 10-27,永远对不上
    (2026-08-05 第一版就栽在这里)。
    """
    nums, i = [], 0
    for w in seq:
        if w.isdigit():
            nums.append(int(w))
        elif w in TENS:
            nums.append(TENS[w])
        elif w in UNITS:
            # 紧跟在整十后面的个位 → 合并(twenty + seven = 27)
            if nums and nums[-1] in TENS.values() and UNITS[w] < 10:
                nums[-1] += UNITS[w]
            else:
                nums.append(UNITS[w])
    return "-".join(str(x) for x in nums)


def benign(a: str, b: str) -> bool:
    """脚本词 a 与实听词 b 的差异是否属于正常噪声。"""
    if a == b:
        return True
    if frozenset((a, b)) in HOMOPHONE_OK:
        return True
    if NUM_WORDS.get(a) == b or NUM_WORDS.get(b) == a:
        return True
    if a.rstrip("s") == b.rstrip("s"):          # 单复数
        return True
    if a.replace("'", "") == b.replace("'", ""):
        return True
    return False


def load_scripts() -> dict[Path, list[str]]:
    out = {}
    for p in list(VO.glob("*.txt")) + list(DOCS.glob("*.txt")):
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        w = words(t)
        if len(w) > 120:                         # 太短的不是整篇脚本
            out[p] = w
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", action="store_true", help="只输出母带↔脚本配对")
    ap.add_argument("--min-run", type=int, default=1,
                    help="连续差异达到几个词才上报(默认 1)")
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text())
    atoms = [x for x in man["atoms"] if x.get("text")]
    by_master: dict[str, list[dict]] = {}
    for x in atoms:
        by_master.setdefault(x.get("source_master", "?"), []).append(x)
    for v in by_master.values():
        v.sort(key=lambda x: x.get("t_start", 0))

    scripts = load_scripts()
    print(f"母带 {len(by_master)} · 候选脚本 {len(scripts)}\n")

    pairs = {}
    for master, items in by_master.items():
        heard = words(" ".join(x["text"] for x in items))
        hset = set(heard)
        best, sc = None, 0.0
        for p, sw in scripts.items():
            ov = len(hset & set(sw)) / max(1, len(set(sw)))
            if ov > sc:
                best, sc = p, ov
        pairs[master] = (best, sc, heard, items)
        print(f"{'✅' if sc >= 0.5 else '⚠️ '} 内容重合 {sc:.0%}  "
              f"{Path(master).stem[:46]}")
        if best:
            print(f"      ← {best.name[:66]}")
    if a.pair:
        return 0

    review = []
    for master, (script, sc, heard, items) in pairs.items():
        if not script or sc < 0.5:
            continue
        ref = scripts[script]
        sm = difflib.SequenceMatcher(a=ref, b=heard, autojunk=False)
        # 词在 heard 中的下标 → 所属原子
        owner, k = [], 0
        for x in items:
            n = len(words(x["text"]))
            owner += [x] * n
            k += n
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            said = ref[i1:i2]
            got = heard[j1:j2]
            # 发音错误的形态:该念 A 却念成 B,两侧长度相当且都很短。
            # 长度悬殊(如 1 词 vs 6 词)是对齐漂移或整段删改,不是念错 ——
            # 2026-08-05 第一版没这条,362 条候选里绝大多数是这类假阳性。
            if tag != "replace":
                continue
            if not said or not got:
                continue
            if len(said) > 4 or len(got) > 4:
                continue
            if abs(len(said) - len(got)) > 1:
                continue
            if all(benign(x, y) for x, y in
                   zip(said, got + [""] * (len(said) - len(got)))):
                continue
            # 经文章节的读法差异:「three twenty two」vs「3 22」是 whisper 的
            # 书写偏好,不是念错
            ns, ng = numeric(said), numeric(got)
            if ns and ng and ns == ng:
                continue
            # 两侧首词发音相近(编辑距离小)才更像"念歪",而非换了个词
            if difflib.SequenceMatcher(a=said[0], b=got[0]).ratio() < 0.45 \
                    and len(said) == 1 and len(got) == 1:
                continue
            owners = {id(o): o for o in owner[j1:j2] if o}
            for o in owners.values():
                review.append({
                    "atom_id": o["id"], "path": o["path"],
                    "t_start": o.get("t_start"), "duration": o.get("duration_sec"),
                    "script_says": " ".join(said) or "(缺)",
                    "whisper_heard": " ".join(got) or "(无声)",
                    "atom_text": o["text"][:70],
                    "master": Path(master).stem[:46],
                })

    # 同一原子多处差异合并
    merged: dict[str, dict] = {}
    for r in review:
        m = merged.setdefault(r["atom_id"], {**r, "hits": 0})
        m["hits"] += 1
    rows = sorted(merged.values(), key=lambda r: -r["hits"])

    QUEUE.write_text(json.dumps(
        {"generated": datetime.now(timezone.utc).isoformat(),
         "candidates": len(rows), "rows": rows}, ensure_ascii=False, indent=1))

    md = ["# 发音细筛队列(人工)", "",
          f"粗筛产出 **{len(rows)}** 条待听。判据:原始 TTS 脚本与 whisper 实听",
          "在同一位置不一致,且不属于大小写/标点/数字形式/同音异形等正常噪声。", "",
          "听法:命令行 `afplay <路径>`,或在访达里双击。",
          "判定后把结果填进「结论」列 —— OK(念对了)/ BAD(念错,弃用)。", "",
          "| # | 原子 | 脚本应念 | 实际听到 | 时长 | 结论 |",
          "|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        md.append(f"| {i} | `{r['atom_id']}` | {r['script_says'][:34]} | "
                  f"{r['whisper_heard'][:34]} | {r['duration']}s |  |")
    md += ["", "## 音频路径", ""]
    md += [f"- `{r['atom_id']}` — `{r['path']}`" for r in rows]
    SHEET.write_text("\n".join(md), encoding="utf-8")

    print(f"\n粗筛候选 {len(rows)} 条 → {SHEET.name}")
    for r in rows[:10]:
        print(f"  {r['atom_id']}  脚本「{r['script_says'][:30]}」 "
              f"实听「{r['whisper_heard'][:30]}」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
