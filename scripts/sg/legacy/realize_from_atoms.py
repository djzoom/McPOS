#!/usr/bin/env python3
# coding: utf-8
"""把打磨稿落到真实原子上 — 可实现性门禁 + 逐句剪辑计划。

只有原子库,没有 TTS。因此每一句台词都必须能由 Locke 的真实录音实现,
可用的操作只有三种(都不产生新声音):

  KEEP   一个原子原样用
  SPAN   若干**连续**原子拼接成一句
  TRIM   取某原子(或连续原子)的词序列子段 —— 按词边界切,删掉转写赘语

不可用:凭空加词、换词。凡是打磨稿里出现原录音没有的词,一律判 UNREALIZABLE,
必须把文本改回音频说得出的话 —— 这是硬门禁,不通过不出片。

  ./.venv/bin/python scripts/sg/realize_from_atoms.py --episodes 1     # 审计一期
  ./.venv/bin/python scripts/sg/realize_from_atoms.py --all            # 全批报告
  ./.venv/bin/python scripts/sg/realize_from_atoms.py --episodes 1 --plan  # 出剪辑计划
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BD = Path.home() / ("Studio/Workspace/outputs/sg/sessions/"
                    "sg_toytune_ep1/text_batch_10")
POLISHED = BD / "polished"
PLAN_DIR = POLISHED / "atom_plans"
MAX_SPAN = 6                    # 一句最多由几个连续原子拼成


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()


def realize(sentence: str, atoms: list[dict]) -> dict | None:
    """返回该句的实现方式;无法实现返回 None。"""
    sw = words(sentence)
    if not sw:
        return None
    aw = [words(a["text"]) for a in atoms]

    # 1) KEEP —— 整原子完全一致
    for i, a in enumerate(aw):
        if a == sw:
            return {"op": "KEEP", "atoms": [atoms[i]["id"]], "words": len(sw)}

    # 2) SPAN —— 连续原子拼接完全一致
    for i in range(len(aw)):
        acc: list[str] = []
        for j in range(i, min(i + MAX_SPAN, len(aw))):
            acc += aw[j]
            if acc == sw:
                return {"op": "SPAN", "atoms": [a["id"] for a in atoms[i:j + 1]],
                        "words": len(sw)}
            if len(acc) > len(sw) + 4:
                break

    # 3) TRIM —— 是某段连续原子词序列的连续子段(只删不加)
    for i in range(len(aw)):
        acc: list[str] = []
        for j in range(i, min(i + MAX_SPAN, len(aw))):
            acc += aw[j]
            if len(acc) < len(sw):
                continue
            for off in range(len(acc) - len(sw) + 1):
                if acc[off:off + len(sw)] == sw:
                    return {"op": "TRIM",
                            "atoms": [a["id"] for a in atoms[i:j + 1]],
                            "word_offset": off, "words": len(sw)}
            if len(acc) > len(sw) + 24:
                break
    return None


def audit(n: int, write_plan: bool = False) -> dict:
    src = json.loads((BD / f"sg_text_ep{n:02d}.json").read_text())
    pol = json.loads((POLISHED / f"sg_text_ep{n:02d}.json").read_text())
    atoms = src["plan"]
    by_id = {a["id"]: a for a in atoms}

    rows, bad = [], []
    for sec in ("opening", "prayer", "closing"):
        for s in pol["sentences"][sec]:
            r = realize(s, atoms)
            if r is None:
                bad.append({"section": sec, "text": s})
            else:
                r.update({"section": sec, "text": s})
                rows.append(r)

    total = len(rows) + len(bad)
    ok = not bad
    counts = {op: sum(1 for r in rows if r["op"] == op)
              for op in ("KEEP", "SPAN", "TRIM")}
    dur = sum(sum(by_id[i]["duration_sec"] for i in r["atoms"]) for r in rows)

    if write_plan and ok:
        PLAN_DIR.mkdir(exist_ok=True)
        (PLAN_DIR / f"sg_text_ep{n:02d}.atoms.json").write_text(json.dumps({
            "episode_id": pol["episode_id"], "perspective": pol["perspective"],
            "realizable": True, "sentences": len(rows), "ops": counts,
            "audio_seconds": round(dur, 1),
            "plan": [{**r, "paths": [by_id[i]["path"] for i in r["atoms"]]}
                     for r in rows],
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    return {"episode": n, "ok": ok, "total": total, "counts": counts,
            "unrealizable": bad, "audio_min": dur / 60}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--plan", action="store_true", help="通过则写剪辑计划")
    a = ap.parse_args()
    nums = range(1, 11) if a.all else [a.episodes or 1]

    fails = 0
    for n in nums:
        r = audit(n, write_plan=a.plan)
        c = r["counts"]
        mark = "✅" if r["ok"] else "⛔"
        print(f"{mark} ep{n:02d}  {r['total']:3d} 句  "
              f"KEEP {c['KEEP']:3d} · SPAN {c['SPAN']:2d} · TRIM {c['TRIM']:2d} · "
              f"不可实现 {len(r['unrealizable']):2d}   音频 {r['audio_min']:.1f} 分")
        for b in r["unrealizable"][:8]:
            print(f"      ✗ [{b['section']}] {b['text'][:74]}")
        if len(r["unrealizable"]) > 8:
            print(f"      … 另有 {len(r['unrealizable']) - 8} 句")
        fails += 0 if r["ok"] else 1
    if fails:
        print(f"\n⛔ {fails} 期未过可实现性门禁 —— 把不可实现的句子改回"
              f"原录音说得出的话,再跑一次。")
        return 1
    print("\n✅ 全部可由真实原子实现")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
