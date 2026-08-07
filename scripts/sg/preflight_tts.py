#!/usr/bin/env python3
# coding: utf-8
"""待录文本预检 —— 录之前先算清楚:这些句子录出来能进哪个槽?

最贵的失败不是写得不好,是**写了、录了、付了钱,却进不了需要它的槽位**:

  · close 槽要求文本含结尾标记(amen / peace be with you / good night /
    in the name of Jesus / dwell in safety),否则 is_strong_close_text 挡下
  · bless 槽要求祈愿式("May …"),否则 is_blessing_text 挡下
  · breath 角色要求时长 ≤3.5s,写太长会掉进别的角色
  · 采集器按语言形态判角色,写法不对就归错类

这个脚本用**与生产完全相同的判定函数**(harvest_whisper.role_from_text、
build_session.is_strong_close_text / is_blessing_text)跑一遍待录文本,
给出预期角色分布与槽位可用性。

  ./.venv/bin/python scripts/sg/preflight_tts.py ~/Studio/Library/sg/catalog/scripts/tts_g3.txt
"""
from __future__ import annotations

import argparse
import collections
from pathlib import Path

import build_session as B
import harvest_whisper as hw
import tag_addressee as TA
from atom_quality import fragment_reason, words

WPS = 2.0          # 冥想语速约 2 词/秒,用于估算时长


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    a = ap.parse_args()

    lines = [l.strip() for l in a.path.read_text().splitlines() if l.strip()]
    roles: collections.Counter = collections.Counter()
    rows: list[tuple[str, str, float]] = []
    for l in lines:
        dur = len(words(l)) / WPS
        # 必须把 addressee 一并模拟:采集后会跑 tag_addressee,归不了类的句子
        # 靠「你指谁」落到 comfort(旁白)或 petition(祷告)。不模拟它,
        # 预检会把一大批好句子误报成「无槽位 misc」。
        addressee = TA.by_text(l) or "neutral"
        # 待录文本没有母带位置可言,一律 positional=False
        role, _ = hw.role_from_text(l, 0.5, dur, [], positional=False,
                                    addressee=addressee)
        roles[role] += 1
        rows.append((l, role, dur))

    print(f"=== 预期角色分布({len(lines)} 句)===")
    for r, n in roles.most_common():
        print(f"  {r:<10}{n:>4}")

    close_ok = [l for l, r, _ in rows if B.is_strong_close_text(l)]
    bless_ok = [l for l, r, _ in rows if B.is_blessing_text(l)]
    print(f"\n=== 槽位可用性(用生产判定函数)===")
    print(f"  能进 CLOSE 槽  {len(close_ok):>4}   (须含结尾标记)")
    print(f"  能进 BLESS 槽  {len(bless_ok):>4}   (须为祈愿式 May…)")

    long_breath = [(l, d) for l, r, d in rows if r == "breath" and d > 3.5]
    if long_breath:
        print(f"\n  ⚠️ {len(long_breath)} 句想做 breath 但估算超 3.5s,会掉进别的角色:")
        for l, d in long_breath[:5]:
            print(f"       {d:.1f}s  {l[:56]}")

    frags = [l for l, _, _ in rows
             if fragment_reason({"text": l})]
    if frags:
        print(f"\n  ⚠️ {len(frags)} 句句法不完整,录出来只能作续接:")
        for l in frags[:5]:
            print(f"       {l[:60]}")

    miscs = [l for l, r, _ in rows if r == "misc"]
    if miscs:
        print(f"\n  ⚠️ {len(miscs)} 句归不了类(会落 misc,无槽位):")
        for l in miscs[:8]:
            print(f"       {l[:60]}")

    print(f"\n字符 {sum(len(l) for l in lines) + len(lines)}"
          f"   预计录制 {sum(d for _, _, d in rows)/60:.1f} 分钟")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
