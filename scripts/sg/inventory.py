#!/usr/bin/env python3
# coding: utf-8
"""原子库盘点 —— 能出多少期不重样的节目。

所有门禁走 atom_quality,与 build_tts_batch / 编排器同一套判据,
避免「盘点说够 24 期、编排时发现不够」这类矛盾。

期数按**唯一文本**算而不是原子数:同一句话录了 4 遍仍然只是一句,
听众听两期就会发现重复。

  ./.venv/bin/python scripts/sg/inventory.py
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from atom_quality import fragment_reason, key, load_whitelist, reject_reason, usable
from build_session import is_blessing_text, is_strong_close_text

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
GRAMMAR = Path.home() / "Studio/Library/sg/catalog/grammars/evening_prayer_v0.json"


def slot_demand() -> list[tuple[str, tuple[str, ...], float]]:
    """每个槽位的 (id, 可用角色集合, 每期取几条) —— 从语法文件推算。

    必须按**槽位**算,不能按角色摊派。一个槽位写 roles=[scripture, poetic]
    意思是「这两类都能填这个位置」,编排器从二者的并集里挑;若按角色均摊
    需求,poetic 会被算成每期要 6.3 条,于是盘点报「只够 4 期」——
    而真实约束是 scripture+poetic 的并集够不够填这些位置。
    """
    g = json.loads(GRAMMAR.read_text())
    out = []
    for s in g.get("slots", []):
        roles = tuple(r for r in (s.get("roles") or []) if r != "silence")
        if not roles:
            continue
        pick = s.get("pick", 1)
        n = (pick[0] + pick[1]) / 2 if isinstance(pick, list) else float(pick)
        out.append((str(s.get("id")), roles, n))
    return out

THEMES = [
    ("孤独", r"\balone\b|\blonely\b|\bloneliness\b|\bby yourself\b"),
    ("焦虑/恐惧", r"\banxi|\bafraid\b|\bfear\b|\bworry\b|\bpanic\b|\bdread\b"),
    ("同在/保护", r"\bwith you\b|\bwatch(es|ing)? over\b|\bkeeps? you\b|\bshelter\b"),
    ("信靠/交托", r"\btrust\b|\bcommit\b|\bsurrender\b|\binto your hands\b"),
    ("盼望/未来", r"\bhope\b|\btomorrow\b|\bmorning\b|\bfuture\b|\bplans\b"),
    ("疲惫/耗竭", r"\btired\b|\bweary\b|\bexhaust|\bworn\b|\bspent\b|\bdrained\b"),
    ("愧疚/羞耻", r"\bguilt\b|\bshame\b|\bforgive\b|\bfailed?\b|\bregret\b"),
    ("悲伤/失丧", r"\bgrief\b|\bgrieving\b|\bsorrow\b|\bmourn|\bloss\b|\bbrokenhearted\b|\btears\b"),
    ("疾病/身体", r"\bpain\b|\bsick\b|\bbody\b|\bheal(ing)?\b|\bill(ness)?\b|\bache\b"),
    ("工作/供应", r"\bwork\b|\bprovide\b|\bprovision\b|\bmoney\b|\bjob\b|\bneeds?\b"),
    ("关系/家庭", r"\bfamily\b|\bchild\b|\bmarriage\b|\bfriend\b|\bthose you love\b"),
    ("感恩", r"\bthank\b|\bgrateful\b|\bgratitude\b|\bpraise\b"),
    ("失眠本身", r"\bawake\b|\bsleepless\b|\bcannot sleep\b|\brestless\b|\bstill awake\b"),
]


def main() -> int:
    man = json.loads(MANIFEST.read_text())
    atoms = man["atoms"]
    wl = load_whitelist()   # 盘点与编排器同一套门禁,白名单也不能少
    ok = [x for x in atoms if usable(x, wl)]

    print(f"=== 库存实况 ===")
    print(f"  原子总数        {len(atoms):>5}")
    rej = collections.Counter()
    for x in atoms:
        r = reject_reason(x, wl)
        if r:
            rej[re.sub(r"[\d.]+", "N", r)] += 1
    for r, n in rej.most_common():
        print(f"    ✗ {r:<32}{n:>5}")
    print(f"  **可用原子**    {len(ok):>5}")
    uniq = {key(x['text']) for x in ok}
    print(f"  **唯一文案**    {len(uniq):>5}   (重复录制 {len(ok)-len(uniq)} 条)")
    free = [x for x in ok if fragment_reason(x) is None]
    nfree = len({key(x["text"]) for x in free})
    print(f"    其中自由可用  {nfree:>5}")
    print(f"    仅可作续接    {len(uniq)-nfree:>5}   (句法不完整,须紧跟前句播放)")

    # 编排器按**角色或标签**匹配槽位,盘点也必须 —— 否则同一个槽位两处算出
    # 两个数。2026-08-12 实测:BLESS 盘点报「池 0、可出 0 期」,编排器却用
    # 带 bless 标签的 close 原子填了它。
    # 只索引**被槽位用到的**那些标签:库里还有 psalm121 / welcome 这类内容
    # 标签,全都当角色索引会把「无槽位」清单淹掉,反而看不见真正无处安放的料。
    slot_roles = {r for _, rs, _ in slot_demand() for r in rs}
    byrole = collections.defaultdict(set)
    for x in free:
        byrole[x["role"]].add(key(x["text"]))
        for t in (x.get("tags") or []):
            if t != x["role"] and t in slot_roles:
                byrole[t].add(key(x["text"]))

    print(f"\n=== 槽位供需(**自由可用**唯一文案计)===")
    print(f"  {'槽位':<15}{'每期取':>7}{'可选池':>8}{'可撑期数':>9}  角色")
    eps = []
    # 终末槽位在编排器里还有一道**语言形态**门(_eligible 里的 is_blessing_text /
    # is_strong_close_text):祝福位上必须真是祝福,结尾位上必须真是结尾。
    # 盘点漏掉这道门就会把池子报大,而真正卡住期数的恰恰是这两个槽。
    form_gate = {"BLESS": is_blessing_text, "CLOSE": is_strong_close_text}
    text_of: dict[str, str] = {}
    for x in free:
        text_of.setdefault(key(x["text"]), x["text"])
    for sid, roles, need in slot_demand():
        pool = set().union(*(byrole.get(r, set()) for r in roles)) if roles else set()
        gate = form_gate.get(sid.upper())
        if gate:
            pool = {k for k in pool if gate(text_of.get(k, ""))}
        n = int(len(pool) // need) if need else 0
        eps.append((n, sid))
        flag = "🔴" if n < 10 else "🟡" if n < 30 else "🟢"
        print(f"  {sid:<15}{need:>7.1f}{len(pool):>8}{n:>8} {flag}  {'+'.join(roles)}")
    used = {r for _, rs, _ in slot_demand() for r in rs}
    for r in sorted(set(byrole) - used):
        print(f"  {'(无槽位)':<15}{'—':>7}{len(byrole[r]):>8}{'':>8}     {r}")
    eps.sort()
    print(f"\n  ▶ **可出 {eps[0][0]} 期完全不重样**,瓶颈槽位 = {eps[0][1]}")

    print(f"\n=== 主题覆盖(唯一文案计)===")
    for name, pat in THEMES:
        rx = re.compile(pat, re.I)
        n = len({key(x["text"]) for x in ok if rx.search(x["text"])})
        flag = "🔴" if n < 15 else "🟡" if n < 40 else "🟢"
        print(f"  {name:<12}{n:>5} {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
