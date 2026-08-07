#!/usr/bin/env python3
# coding: utf-8
"""长视频的标题 / 简介 / 标签 —— 以**本期实际念到的经文**为主题。

主题不是事后贴上去的标签,而是从成片里读出来的:扫一遍 plan,找出这一期
真正引用了哪些经文,取最主要的那一处作题眼。这样标题与内容由构造保证一致,
不会出现「标题写诗篇 23,片中一句都没念」。

经文表**复用 TOYTUNE 的 shorts_copy.SCRIPTURES**(22 条,带 KJV 原文与
一句转折),不另建一份 —— 两条线共用同一份策展,短视频与长视频的经文
说法才不会分头演化。

长视频的 SEO 与 Shorts 不同:
  · 时长必须进标题("1 Hour"/"3 Hours")—— 助眠观众按时长搜
  · 经文出处本身就是搜索词,要完整写(Psalm 46:10,不写 Psalm 46)
  · 关键词前置,品牌靠后 —— 标题左侧才是搜索与推荐读到的部分
  · 期号让系列可以「被追」,比请求订阅有效

  ./.venv/bin/python scripts/sg/episode_meta.py --session qc05
  ./.venv/bin/python scripts/sg/episode_meta.py --session qc05 --episode 12
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
from pathlib import Path

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
SHORTS_COPY = Path.home() / "Projects/TOYTUNE/shorts_copy.py"

BOOKS = (r"psalms?|matthew|mark|luke|john|isaiah|jeremiah|lamentations|proverbs|"
         r"deuteronomy|romans|philippians|corinthians|peter|hebrews|james|"
         r"revelation|zephaniah|nehemiah|exodus|numbers|joshua|colossians|ephesians")

# 口读数字 → 阿拉伯数字。母带里经文编号是念出来的("Psalm one twenty seven"),
# 不先合并的话「one twenty seven」会变成 1-20-7 而不是 127。
UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
        "seventy": 70, "eighty": 80, "ninety": 90}


def spoken_number(tokens: list[str]) -> int | None:
    """把一串口读数字合成一个数。one twenty seven → 127,forty six → 46。"""
    vals: list[int] = []
    i = 0
    while i < len(tokens):
        t = tokens[i].lower().strip(",.")
        if t.isdigit():
            vals.append(int(t))
        elif t in TENS:
            n = TENS[t]
            if i + 1 < len(tokens) and tokens[i + 1].lower().strip(",.") in UNITS:
                n += UNITS[tokens[i + 1].lower().strip(",.")]
                i += 1
            vals.append(n)
        elif t in UNITS:
            vals.append(UNITS[t])
        elif t in ("hundred",):
            if vals:
                vals[-1] *= 100
        else:
            break
        i += 1
    if not vals:
        return None
    # 「one twenty seven」= 1,27 → 127;「forty six」= 46
    out = ""
    for v in vals:
        out += str(v)
    try:
        return int(out)
    except ValueError:
        return None


def load_scriptures() -> list[dict]:
    if not SHORTS_COPY.exists():
        return []
    spec = importlib.util.spec_from_file_location("shorts_copy", SHORTS_COPY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(getattr(mod, "SCRIPTURES", []))


def refs_in_plan(plan: list[dict]) -> collections.Counter:
    """本期实际念到的经文出处(书卷 + 章 [+ 节])。"""
    found: collections.Counter = collections.Counter()
    for p in plan:
        if p.get("type") != "atom":
            continue
        t = p.get("text") or ""
        for m in re.finditer(rf"\b({BOOKS})\b[\s,]*([^.;!?]{{0,42}})", t, re.I):
            book = (m.group(1).title().rstrip("s")
                    if m.group(1).lower().startswith("psalm") else m.group(1).title())
            # 章与节是**两组**数字,必须按分隔符切开再各自合成。
            # 拼在一起会得到「Psalm 34, verse 18」→ 3418 这种乱码;
            # 而组**内**才需要合成(「one twenty seven」→ 127)。
            rest = re.sub(r"\bverse\b|\bchapter\b|\band\b", "|", m.group(2), flags=re.I)
            rest = re.sub(r"[,;:]| - ", "|", rest)
            groups = []
            for chunk in rest.split("|"):
                toks = re.findall(r"[a-z]+|\d+", chunk, re.I)
                # 「127.2」这类点分写法直接就是章.节
                dotted = re.match(r"\s*(\d+)\s*[.]\s*(\d+)", chunk)
                if dotted:
                    groups += [int(dotted.group(1)), int(dotted.group(2))]
                    continue
                n = spoken_number(toks)
                if n is not None:
                    groups.append(n)
            if not groups:
                continue
            ch, vs = groups[0], (groups[1] if len(groups) > 1 else None)
            if not (1 <= ch <= 176):            # 诗篇最多 150 章,留点余量
                continue
            if vs is not None and not (1 <= vs <= 176):
                vs = None
            found[f"{book} {ch}:{vs}" if vs else f"{book} {ch}"] += 1
    return found


def pick_primary(found: collections.Counter, table: list[dict]) -> dict | None:
    """优先选**能在策展表里找到全文**的那一处 —— 简介里要引原文。"""
    by_ref = {s["ref"]: s for s in table}
    for ref, _ in found.most_common():
        if ref in by_ref:
            return by_ref[ref]
        chapter = ref.split(":")[0]
        for k, s in by_ref.items():
            if k.startswith(chapter + ":"):
                return s
    return None


def duration_label(sec: float) -> str:
    h = sec / 3600.0
    if h >= 2.75:
        return f"{round(h)} Hours"
    if h >= 1.75:
        return "2 Hours"
    if h >= 0.9:
        return "1 Hour"
    return f"{round(sec/60)} Minutes"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--episode", type=int)
    ap.add_argument("--write", action="store_true", help="写入 <session>_meta.txt")
    a = ap.parse_args()

    D = SESSIONS / a.session
    meta = json.loads((D / f"{a.session}_session.json").read_text())
    plan = meta.get("plan") or []
    total = float(meta.get("total_duration_sec") or 0)

    table = load_scriptures()
    found = refs_in_plan(plan)
    primary = pick_primary(found, table)

    print(f"=== {a.session} ===")
    print(f"时长 {total/60:.0f} 分钟 · 原子 {sum(1 for p in plan if p.get('type')=='atom')} 条")
    print(f"检出经文 {len(found)} 处:{', '.join(k for k,_ in found.most_common(8))}")
    if not primary:
        print("\n⚠️ 没有一处能在策展表里找到全文 —— 标题无法引原文。")
        print("   要么补策展表,要么这一期不该以经文为题。")
        return 1

    dur = duration_label(total)
    # 标题必须 ≤100 字符,否则 YouTube 截断 —— 被截掉的往往正是品牌与期号。
    # 关键词前置:搜索与推荐读的是标题左侧。经文出处写全(章:节),
    # 时长紧随其后(助眠观众按时长筛选)。期号放最后,它是给老观众看的。
    head = primary["turn"].rstrip(".")
    ep = f" · No. {a.episode:03d}" if a.episode else ""
    title = f"{head} — {primary['ref']} | {dur} Christian Night Prayer for Sleep{ep}"
    if len(title) > 100:                 # 转折句太长时先砍它,而不是砍关键词
        room = 100 - len(f" — {primary['ref']} | {dur} Christian Night Prayer for Sleep{ep}")
        head = head[:max(12, room - 1)].rstrip(" ,;—-")
        title = f"{head} — {primary['ref']} | {dur} Christian Night Prayer for Sleep{ep}"
    others = [k for k, _ in found.most_common() if k != primary["ref"]][:5]
    body = "\n".join([
        primary["turn"],
        "",
        f'"{primary["kjv"]}" — {primary["ref"]}, KJV',
        "",
        (f"A spoken night prayer of about {dur.lower()}. The voice rests after "
         f"{meta.get('vo_ends_sec',0)/60:.0f} minutes; the music stays with you "
         f"until morning."
         if total - float(meta.get("vo_ends_sec") or 0) > 120
         else f"A spoken night prayer of about {dur.lower()}."),
        "",
        "Also read tonight: " + ", ".join(others) + "." if others else "",
        "",
        "Three rings of light turn around the cross. Each time a gold crest "
        "crosses an arm, the wire catches — the light has the same cause as "
        "the voice, not a reaction to it.",
        "",
        "Sleep in Grace — a new night prayer every evening.",
    ])
    tags = ["#nightprayer", "#christianmeditation", "#sleepmusic", "#bible",
            "#prayer", "#faith", "#peacefulmusic", "#sleepingrace",
            "#" + primary["ref"].split()[0].lower() + primary["ref"].split()[1].split(":")[0]]

    out = (f"TITLE\n{title}\n\nDESCRIPTION\n{body}\n\nTAGS\n{' '.join(tags)}\n")
    print(f"\n{out}")
    print(f"标题长度 {len(title)} 字符" +
          ("  ⚠️ 超过 100,YouTube 会截断" if len(title) > 100 else ""))
    if a.write:
        p = D / f"{a.session}_meta.txt"
        p.write_text(out, encoding="utf-8")
        print(f"→ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
