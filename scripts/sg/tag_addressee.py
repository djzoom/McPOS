#!/usr/bin/env python3
# coding: utf-8
"""给原子打 addressee 标签 —— 「你」到底指谁。

2026-08-05 分析发现:含 "you" 的可用原子有 841 条(占六成),而 "you" 的
指代分两种模式,相邻拼接会让指代当场翻转:

  祷告模式 god      "You are faithful."        → you = 上帝,说话人是我/我们
  旁白模式 listener "He is watching over you." → you = 听者,上帝是第三人称

  「他整夜看顾**你**。……**你**是信实的。」← 两句相邻,听者当场迷失

这比人称(I/we)一致重要得多:人称错了是语法瑕疵,addressee 错了是语义崩塌。

判定三步:
  ① 文本自证 —— 有第一人称且无第三人称上帝 → god;反之 → listener
  ② 上下文推断 —— 歧义原子取母带内前后邻居的多数模式(原子在母带里连续)
  ③ 仍无法定 —— neutral,可用作模式切换时的过渡

写入 manifest 与边车的 `addressee` 字段,并给出每期编排可用的统计。

  ./.venv/bin/python scripts/sg/tag_addressee.py --dry-run
  ./.venv/bin/python scripts/sg/tag_addressee.py
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from atom_quality import usable, words

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"

SPEAKER = {"i", "my", "me", "mine", "we", "our", "us", "ours"}
GOD_3RD = {"he", "his", "him", "god's", "lord's", "himself"}
SECOND = {"you", "your", "yours", "thee", "thy"}
# 明确对上帝的呼语 —— 出现即锁定祷告模式
VOCATIVE = re.compile(r"\b(lord|father|god|jesus|christ|holy spirit)\s*[,.]",
                      re.I)
NEUTRAL_HINT = {"amen", "let us pray", "we pray"}
CTX_WINDOW = 3          # 上下文推断的前后邻居数



def by_text(t: str) -> str | None:
    """① 文本自证。返回 god / listener / None(歧义)。"""
    w = set(words(t))
    if not (w & SECOND):
        # 不含第二人称:有第一人称即祷告,只提到上帝第三人称即旁白
        if w & SPEAKER:
            return "god"
        if w & GOD_3RD:
            return "listener"
        return None
    if VOCATIVE.search(t):
        return "god"
    spk, g3 = bool(w & SPEAKER), bool(w & GOD_3RD)
    if spk and not g3:
        return "god"
    if g3 and not spk:
        return "listener"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text())
    atoms = man["atoms"]

    # 按母带 + 时间排序 —— 原子在母带里是连续的,邻居可用于推断
    order: dict[str, list[dict]] = collections.defaultdict(list)
    for x in atoms:
        if x.get("text"):
            order[x.get("source_master", "?")].append(x)
    for v in order.values():
        v.sort(key=lambda x: x.get("t_start", 0))

    stats = collections.Counter()
    for items in order.values():
        base = [by_text(x["text"]) for x in items]
        final = list(base)
        # ② 上下文推断:歧义者取窗口内邻居的多数
        for i, v in enumerate(base):
            if v is not None:
                continue
            lo, hi = max(0, i - CTX_WINDOW), min(len(base), i + CTX_WINDOW + 1)
            votes = collections.Counter(x for x in base[lo:hi] if x)
            if votes:
                final[i] = votes.most_common(1)[0][0]
                stats["由上下文推断"] += 1
        for x, v in zip(items, final):
            w = set(words(x["text"]))
            if any(h in x["text"].lower() for h in NEUTRAL_HINT):
                v = "neutral"          # ③ 过渡语,两边都能接
            x["addressee"] = v or "neutral"
            stats[x["addressee"]] += 1

    print("=== addressee 分布 ===")
    tot = sum(stats[k] for k in ("god", "listener", "neutral"))
    for k in ("god", "listener", "neutral"):
        label = {"god": "祷告(you=上帝)", "listener": "旁白(you=听者)",
                 "neutral": "中性/过渡"}[k]
        print(f"  {label:<22} {stats[k]:>5}  {stats[k]/tot:>5.0%}")
    print(f"  (其中 {stats['由上下文推断']} 条靠母带上下文定夺)")

    # 可用原子(过质量门的)按角色 × addressee,给编排看供给
    grid = collections.Counter(
        (x["role"], x["addressee"]) for x in atoms if x.get("text") and usable(x))
    roles = sorted({r for r, _ in grid})
    print(f"\n=== 可用原子:角色 × addressee ===")
    print(f"  {'角色':<11}{'祷告':>6}{'旁白':>6}{'中性':>6}")
    for r in roles:
        print(f"  {r:<11}{grid[(r,'god')]:>6}{grid[(r,'listener')]:>6}"
              f"{grid[(r,'neutral')]:>6}")

    if a.dry_run:
        print("\n(dry-run,未写入)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d")
    bak = MANIFEST.with_suffix(f".json.bak_addressee_{stamp}")
    if not bak.exists():
        bak.write_text(MANIFEST.read_text())
    man["addressee_tagged"] = {"at": datetime.now(timezone.utc).isoformat(),
                               "context_window": CTX_WINDOW}
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))

    n = 0
    for x in atoms:
        if not x.get("text"):
            continue
        side = Path(x["path"]).with_suffix(".json")
        if side.exists():
            sd = json.loads(side.read_text())
            sd["addressee"] = x["addressee"]
            side.write_text(json.dumps(sd, ensure_ascii=False, indent=1))
            n += 1
    print(f"\n✅ 已写入 manifest 与 {n} 个边车(备份 {bak.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
