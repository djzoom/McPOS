#!/usr/bin/env python3
# coding: utf-8
"""连排 N 期,验证管线的**稳定性**而不是单期能不能过。

一期通过不等于稳定。日更频道要看两件事:
  ① 每一期都过门禁(不是碰巧某个种子过了)
  ② 期与期之间不重样(每期单独看合格,但连看两晚是同一篇稿子,一样不能上线)

2026-08-05 实测:重复度修复前 12 期两两平均重叠 74.4%,6 句每期都出现。

**这个脚本必须能发现被测程序崩溃。** 之前用 shell 循环 grep "gate failed"
来判定通过 —— 脚本崩溃时既没有这个字符串、也没生成方案,于是报「20/20 全过」。
一个检不出自己失效的检查,比被检代码的 bug 更危险。这里按**退出码 + 方案文件
是否真的产出**双重判定。

  ./.venv/bin/python scripts/sg/stability_check.py --episodes 20
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atom_quality import key
from qc_session import check_text

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "scripts/sg/build_session.py"
PY = ROOT / ".venv/bin/python"
MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
HISTORY = Path.home() / "Studio/Library/sg/catalog/episode_history.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=20)
    ap.add_argument("--keep-history", action="store_true",
                    help="不清空出片历史(默认清空,从干净状态起算)")
    a = ap.parse_args()

    if not a.keep_history and HISTORY.exists():
        HISTORY.unlink()

    man = json.loads(MANIFEST.read_text())
    quarantined = {x["id"]: x["quarantined"] for x in man["atoms"]
                   if x.get("quarantined")}

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        plans: list[Path] = []
        crashed = gated = 0
        for i in range(1, a.episodes + 1):
            out = d / f"p{i:03d}.json"
            r = subprocess.run(
                [str(PY), str(BUILD), "--plan-only", "--plan-output", str(out),
                 "--episode-id", f"day{i:03d}", "--seed", str(i * 7919 % 100003)],
                capture_output=True, text=True)
            if "gate failed" in (r.stdout + r.stderr):
                gated += 1
                why = [l for l in (r.stdout + r.stderr).splitlines()
                       if "gate failed" in l]
                print(f"  第{i:>3}期 ❌ 门禁 {why[0].split('failed:')[-1].strip()[:56]}")
            elif r.returncode != 0 or not out.exists():
                crashed += 1
                tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or [""]
                print(f"  第{i:>3}期 💥 崩溃(exit {r.returncode}) {tail[0][:60]}")
            else:
                plans.append(out)

        n = a.episodes
        print(f"\n=== 稳定性({n} 期连排)===")
        print(f"  出片成功  {len(plans):>3} / {n}")
        print(f"  门禁拦下  {gated:>3}")
        print(f"  程序崩溃  {crashed:>3}")
        if not plans:
            print("\n❌ 没有任何一期产出,无法评估")
            return 1

        eps: list[set[str]] = []
        bad = 0
        for p in plans:
            plan = json.loads(p.read_text())["plan"]
            r = check_text(plan, quarantined)
            if r:
                bad += 1
                print(f"  {p.stem} ❌ {r[0][:74]}")
            eps.append({key(x["text"]) for x in plan
                        if x.get("type") == "atom" and x.get("text")})
        print(f"  独立 A 层  {len(plans)-bad} 通过 / {bad} 失败")

        pairs = [len(x & y) / max(1, min(len(x), len(y)))
                 for x, y in itertools.combinations(eps, 2)]
        allt: collections.Counter = collections.Counter()
        for s in eps:
            allt.update(s)
        print(f"\n=== 期间重复度 ===")
        print(f"  平均重叠 {sum(pairs)/len(pairs):.1%}   最高 {max(pairs):.1%}")
        print(f"  共用唯一文案 {len(allt)} 句   每期平均 {sum(len(s) for s in eps)//len(eps)} 句")
        print(f"  出现在 ≥6 期的 {len([t for t, c in allt.items() if c >= 6])} 句")

        ok = (len(plans) == n and bad == 0
              and sum(pairs) / len(pairs) < 0.25 and max(pairs) < 0.60)
        print(f"\n{'✅ 稳定' if ok else '❌ 未达稳定标准'}"
              f"  (门槛:全期出片 · A 层零失败 · 平均重叠<25% · 最高<60%)")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
