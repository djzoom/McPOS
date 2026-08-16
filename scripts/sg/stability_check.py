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
GRAMMAR = Path.home() / "Studio/Library/sg/catalog/grammars/evening_prayer_v0.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=20)
    ap.add_argument("--keep-history", action="store_true",
                    help="不清空出片历史(默认清空,从干净状态起算)")
    a = ap.parse_args()

    # —— 历史沙箱:测试绝不能动生产状态 ——
    # 连排要从干净的 cooldown 起算,所以要清历史;每期又要记历史,cooldown
    # 才真的被测到。但此前清了就不还:跑一次连排,episode_history 里四期
    # 正式成片的记录就被 day001–day008 覆盖 —— 下一期真实出片会回避测试期
    # 用过的原子,却忘了已交付的期次用过什么(2026-08-13 实查:历史里只剩
    # 测试数据)。备份、跑、恢复,连排崩溃也得恢复,故放 finally。
    saved = HISTORY.read_text(encoding="utf-8") if HISTORY.exists() else None
    if not a.keep_history and HISTORY.exists():
        HISTORY.unlink()
    try:
        return _run_check(a)
    finally:
        if saved is not None:
            HISTORY.write_text(saved, encoding="utf-8")
        elif HISTORY.exists() and not a.keep_history:
            HISTORY.unlink()


def _run_check(a) -> int:
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
                plans.append((i, out))

        n = a.episodes
        print(f"\n=== 稳定性({n} 期连排)===")
        print(f"  出片成功  {len(plans):>3} / {n}")
        print(f"  门禁拦下  {gated:>3}")
        print(f"  程序崩溃  {crashed:>3}")
        if not plans:
            print("\n❌ 没有任何一期产出,无法评估")
            return 1

        # (期号, 文案集合) —— 期号必须一路带着。被门禁拦下的期次不进这个
        # 列表,若改用列表下标当期号,报出来的「第 10 期」其实是第 10 个**成功**
        # 的计划,拿着这个号去查现场会查到另一期身上。
        eps: list[tuple[int, set[str]]] = []
        bad = 0
        for epno, p in plans:
            plan = json.loads(p.read_text())["plan"]
            r = check_text(plan, quarantined)
            if r:
                bad += 1
                print(f"  第{epno}期 ❌ {r[0][:74]}")
            eps.append((epno, {key(x["text"]) for x in plan
                               if x.get("type") == "atom" and x.get("text")}))
        print(f"  独立 A 层  {len(plans)-bad} 通过 / {bad} 失败")

        # 记下**是哪一对** —— 只报一个最高值,下次还得重跑 20 期才知道去查谁。
        # 分母取两期中较短的那个:短期次与长期次撞车时,对短的那一期伤害更大。
        pair_rows = [(len(x & y) / max(1, min(len(x), len(y))), i, j,
                      len(x), len(y), len(x & y))
                     for (i, x), (j, y) in itertools.combinations(eps, 2)]
        pairs = [r[0] for r in pair_rows]
        allt: collections.Counter = collections.Counter()
        for _, s in eps:
            allt.update(s)
        print(f"\n=== 期间重复度 ===")
        print(f"  平均重叠 {sum(pairs)/len(pairs):.1%}   最高 {max(pairs):.1%}")
        for ov, i, j, li, lj, shared in sorted(pair_rows, reverse=True)[:3]:
            print(f"    第{i}期({li}句) ∩ 第{j}期({lj}句) = {shared} 句  {ov:.1%}")
        print(f"  共用唯一文案 {len(allt)} 句   "
              f"每期平均 {sum(len(s) for _, s in eps)//len(eps)} 句")
        print(f"  出现在 ≥6 期的 {len([t for t, c in allt.items() if c >= 6])} 句")

        # —— 供给压力:重叠率高到底是编排器的错,还是池子本来就不够 ——
        # cooldown 窗口内要做到不重样,需要「窗口期数 × 每期句数」条不同文案。
        # 一旦需求超过池子,窗口里几乎每条原子都带着罚分,惩罚就失去区分力,
        # 编排器只能退回角色/续接分去挑 —— 于是相隔 8 期的两期照样撞车。
        # 这时再怎么调罚分权重都是徒劳,该做的是补录素材。
        avg_lines = sum(len(s) for _, s in eps) // len(eps)
        window = int(((json.loads(GRAMMAR.read_text()).get("cooldown") or {})
                      .get("same_atom_days")) or 12)
        need = window * avg_lines
        have = len(allt)
        print(f"\n=== 供给压力 ===")
        print(f"  cooldown 窗口 {window} 期 × 每期 {avg_lines} 句 = 需要 {need} 条不同文案")
        print(f"  实际用到的唯一文案 {have} 条 —— 缺口 {max(0, need - have)} 条"
              f"(供需比 {have/max(1,need):.2f})")
        starved = have < need

        avg_ov, max_ov = sum(pairs) / len(pairs), max(pairs)
        ok = (len(plans) == n and bad == 0 and avg_ov < 0.25 and max_ov < 0.60)
        print(f"\n{'✅ 稳定' if ok else '❌ 未达稳定标准'}"
              f"  (门槛:全期出片 · A 层零失败 · 平均重叠<25% · 最高<60%)")
        if not ok and starved and max_ov >= 0.60:
            print(f"  ⚠ 但请注意:池子只够 {have//max(1,avg_lines)} 期不重样,"
                  f"本次却连排了 {n} 期。")
            print(f"    重叠超标此时是**素材不足**的必然结果,不是编排器的缺陷 ——")
            print(f"    调罚分权重救不了,要么补录素材,要么把连排期数降到 "
                  f"{have//max(1,avg_lines)} 以内再评。")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
