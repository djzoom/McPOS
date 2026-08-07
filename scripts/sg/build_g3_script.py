#!/usr/bin/env python3
# coding: utf-8
"""G3 补录稿生成器 —— 缺口补充 + 废弃原子回收，预算硬约束。

两个来源合成一份录音稿：

  ① **新内容**：VO_PIPELINE §四 的缺口表（close/breath 是瓶颈，四个 🔴 主题缺料）
  ② **回收**：`quarantined` 里内容仍有价值的那些。按隔离原因分类处置——

     | 原因 | 数量 | 处置 | 理由 |
     |---|---|---|---|
     | `no_speech` | 432 | **丢** | 是静音，文本是邻句复制过来的，没有内容可回收 |
     | `self-deification` | 11 | **丢** | 神学上被拒，不是录音质量问题，重录也还是要拒 |
     | `text_mismatch` | 64 | **修后重录** | 音频与标签不符；意图文本可还原，内容（22 条经文）价值最高 |
     | `misread_negation_lost` | 1 | **必须重录** | ElevenLabs 漏读 not，句义反转，属可修复的读错 |

预算是**硬约束**，不是估算。ElevenLabs 按字符计费，VO_PIPELINE 记着「约 160 句 /
6,500 字符 = 一个月预算」。这个脚本按优先级装箱，装不下的明确列出被砍掉的部分，
而不是悄悄超支——超支的后果是月中断供，比少录几句糟得多。

用法：
    ./.venv/bin/python scripts/sg/build_g3_script.py --budget 10000
    ./.venv/bin/python scripts/sg/build_g3_script.py --budget 10000 --out g3.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

ATOMS = pathlib.Path.home() / "Studio/Library/sg/atoms/manifest.json"

# ── ② 回收：text_mismatch 的定向修正 ─────────────────────────────────────────
# 只列**能确定意图**的。判据是波形之外的证据：经文有原文可校、习语有唯一合理
# 还原。凡是猜的一律不进这张表——猜错就是把一句错的录成"正式"的。
# 键是隔离原子的原文（whisper 的错听），值是应当录的正确句子；值为 None = 丢弃。
MISMATCH_FIX = {
    # 教义反转，VO_PIPELINE §二.2 记录的那一条。约翰福音 14:1 的 not 被漏读。
    "Let your hearts be troubled.": "Let not your heart be troubled.",
    # 明显错听，意图唯一
    "We place this night in jail.": "We place this night in your hands.",
    "You are our she.": None,              # 无法还原意图
    "You are in his head.": None,          # 无法还原意图
    "You are still alive.": None,          # 语义突兀，不适合助眠语法
    "The one who watches us without sight.": None,
    "I don't need to control the effort.": "I do not need to control the outcome.",
    "But the love of God still shines to us.": "But the love of God still shines on us.",
    # 经文：按 KJV 校正并补全引用
    "35 says, I lay down and slept. I woke again.":
        "Psalm 3:5. I laid me down and slept; I awaked; for the LORD sustained me.",
    "because he trusts in you perfect peace a mind stayed on the lord isaiah":
        "Isaiah 26:3. Thou wilt keep him in perfect peace, whose mind is stayed on thee.",
}

# ── ① 新内容：按缺口表分配。close/breath 是瓶颈，先喂它们 ────────────────────
# 每条都是**可独立成句**的：VO_PIPELINE 的 A1 门禁拒半截句，而 qc08 里 19% 的
# 字幕是残句，根子在采集到的原料本身就有太多不完整句。补录是唯一能从源头改善的
# 环节，所以这里一句都不写成从句或悬空短语。
NEW_LINES = {
    "close": [
        "Sleep now, and let the night keep you.",
        "That is all for tonight. Rest well.",
        "We will be here again tomorrow night.",
        "Close your eyes. Nothing more is asked of you.",
        "Let this be where the day ends.",
        "Go now into sleep, and be kept.",
        "The night will hold what you cannot.",
        "Rest. You have done enough today.",
        "Sleep, and wake to mercy in the morning.",
        "Lay it down now. All of it.",
        "Let the last thing you feel tonight be peace.",
        "You are safe to fall asleep now.",
        "This is the end of the day, and it is well.",
        "Sleep deeply. You are fully known.",
        "Rest in his keeping until morning.",
        "Let go now, and sleep.",
    ],
    "breath": [
        "Breathe in slowly, and let it fill you.",
        "Now let that breath go, all the way out.",
        "Take one more breath, deeper than the last.",
        "Let your shoulders come down as you exhale.",
        "Breathe in peace. Breathe out the day.",
        "One more slow breath, and let it settle.",
        "Let the breath be slower than your thoughts.",
        "Feel your chest rise, and let it fall.",
        "Breathe as though you had nowhere to be.",
        "Let this breath be the one that lets go.",
        "Draw the air in gently. Release it gently.",
        "Let each breath be a little longer than the last.",
    ],
    "guilt": [
        "What you did today is not what you are.",
        "The shame you carry was never yours to keep.",
        "You are not the sum of your worst hour.",
        "Forgiveness has already gone ahead of you.",
        "Lay down what you cannot undo tonight.",
        "You are more loved than you are guilty.",
    ],
    "relationship": [
        "The people you love are held tonight too.",
        "You do not have to fix that relationship tonight.",
        "The words you wish you had said can wait.",
        "Those you miss are not beyond his reach.",
        "You are not the only one holding this family together.",
        "Let the ones you love be carried by someone stronger.",
    ],
    "grief": [
        "Grief is allowed to be here tonight.",
        "What you lost mattered, and so does your sorrow.",
        "You do not have to be finished mourning.",
        "The absence you feel is the size of the love.",
        "He is near to the broken-hearted, and that is you.",
        "Sleep does not betray the one you are missing.",
    ],
    "insomnia": [
        "If sleep has not come, you have not failed.",
        "Lying still is enough. It counts as rest.",
        "The night is long, but it is not empty.",
        "You do not have to make sleep happen.",
        "Being awake here is not being alone.",
        "Rest your body even while your mind is awake.",
    ],
    "bless": [
        "May your sleep be deep and unbroken.",
        "May the peace of God guard your heart tonight.",
        "May you wake gently, and in mercy.",
        "May nothing trouble your rest.",
        "May you be kept through every hour of the night.",
        "May you sleep as one deeply loved.",
    ],
}

# 装箱优先级：修读错 → 瓶颈槽 → 🔴 主题 → 其余。改这个顺序等于改"预算不够时先砍谁"。
PRIORITY = ["fix", "close", "breath", "insomnia", "grief", "guilt",
            "relationship", "bless"]


def load_quarantined() -> dict[str, list[str]]:
    recs = json.loads(ATOMS.read_text())
    recs = recs if isinstance(recs, list) else recs.get("atoms", recs)
    out: dict[str, list[str]] = {}
    for r in recs:
        reason = r.get("quarantined")
        if not reason:
            continue
        out.setdefault(reason, []).append((r.get("text") or "").strip())
    return out


def build(budget: int) -> tuple[dict[str, list[str]], list[str], dict]:
    q = load_quarantined()
    mism = {t for t in q.get("text_mismatch", []) if t}
    mism |= {t for t in q.get("misread_negation_lost", []) if t}

    fixes, unmapped = [], []
    for t in sorted(mism):
        if t in MISMATCH_FIX:
            v = MISMATCH_FIX[t]
            if v:
                fixes.append(v)
        else:
            unmapped.append(t)

    buckets = {"fix": fixes, **NEW_LINES}
    chosen: dict[str, list[str]] = {}
    used, dropped = 0, []
    for slot in PRIORITY:
        for line in buckets.get(slot, []):
            cost = len(line) + 1
            if used + cost <= budget:
                chosen.setdefault(slot, []).append(line)
                used += cost
            else:
                dropped.append((slot, line))
    stats = dict(budget=budget, used=used, lines=sum(len(v) for v in chosen.values()),
                 dropped=len(dropped), unmapped=len(unmapped),
                 quarantine_counts={k: len(v) for k, v in q.items()})
    return chosen, unmapped, dict(stats, dropped_list=dropped)


def render(chosen, unmapped, stats) -> str:
    L = ["# SiG G3 补录稿", ""]
    L.append(f"预算 {stats['budget']} 字符 · 实用 **{stats['used']}** · "
             f"共 **{stats['lines']} 句** · 砍掉 {stats['dropped']} 句")
    L.append("")
    L.append("隔离原子盘点：" + " · ".join(
        f"`{k}` {v}" for k, v in sorted(stats["quarantine_counts"].items())))
    L.append("")
    L.append("> 录制约定：每句独立成句，不留从句和悬空短语——A1 门禁拒半截句，"
             "而现有库里 19% 的字幕是残句，根子在原料。")
    L.append("> 慢读、句间留足停顿；语速本身不设门禁（助眠刻意为之）。")
    L.append("")
    titles = {"fix": "① 修正重录（原音频读错，内容有价值）",
              "close": "② close —— 第一瓶颈（17 条唯一结尾句，解开它才能出更多期）",
              "breath": "③ breath —— 第二瓶颈",
              "insomnia": "④ 失眠本身 🔴", "grief": "⑤ 悲伤/失丧 🔴",
              "guilt": "⑥ 愧疚/羞耻 🔴", "relationship": "⑦ 关系/家庭 🔴",
              "bless": "⑧ bless"}
    for slot in PRIORITY:
        if slot not in chosen:
            continue
        L += [f"## {titles.get(slot, slot)}（{len(chosen[slot])} 句）", ""]
        L += [f"{i}. {t}" for i, t in enumerate(chosen[slot], 1)]
        L.append("")
    if unmapped:
        L += ["## 未纳入：无法确定意图的 text_mismatch", "",
              "这些错听还原不出唯一意图。**猜着录等于把一句错的录成正式的**，"
              "所以留给人工听原音后决定。", ""]
        L += [f"- `{t[:88]}`" for t in unmapped]
        L.append("")
    if stats["dropped_list"]:
        L += ["## 预算砍掉（下一批优先）", ""]
        L += [f"- [{s}] {t}" for s, t in stats["dropped_list"]]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=10000, help="字符预算（硬上限）")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    a = ap.parse_args()
    chosen, unmapped, stats = build(a.budget)
    text = render(chosen, unmapped, stats)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
        print(f"✅ {a.out} · {stats['used']}/{a.budget} 字符 · {stats['lines']} 句 "
              f"· 砍 {stats['dropped']} · 待人工 {stats['unmapped']}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
