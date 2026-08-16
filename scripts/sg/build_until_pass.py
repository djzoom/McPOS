#!/usr/bin/env python3
# coding: utf-8
"""换种子重排,直到这一期真的过门禁 —— 严苛标准的配套,不是绕过它。

编排里有刻意的随机(抖动 ±4 分、vo_goal 在 10–22 分钟间抽、静默长度抽样),
所以「同一套规则、不同种子」出来的期次质量本就有分布。实测 8 期连排里
约 1 期会卡在 94–95 之间(多为 T3 后半程降速差一点)。

面对这种情况有两条路:
  ① 把门槛从 95 调到 94 —— 标准就此松一格,而且松了还会有 93 的
  ② 保持 95,换个种子重排 —— 标准不动,让生成端去满足它
这个脚本走第二条。**它不改任何判据**,只是先用 --plan-only 快速试排
(秒级,不渲染音频),挑出第一个过关的种子,再拿它跑完整出片。

  ./.venv/bin/python scripts/sg/build_until_pass.py --episode-id ep01
  ./.venv/bin/python scripts/sg/build_until_pass.py --episode-id ep01 --tries 12 --plan-only
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = ROOT / ".venv/bin/python"
BUILD = HERE / "build_session.py"


def try_seed(seed: int, episode_id: str, extra: list[str]) -> tuple[bool, float, str]:
    """试排一次,返回 (是否过关, 分数, 摘要)。"""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "plan.json"
        r = subprocess.run(
            [str(PY), str(BUILD), "--plan-only", "--no-history",
             "--episode-id", f"{episode_id}_probe", "--seed", str(seed),
             "--plan-output", str(out)] + extra,
            capture_output=True, text=True)
        if not out.exists():
            why = "内容门禁未过" if "gate failed" in (r.stdout + r.stderr) else "崩溃"
            for line in (r.stdout + r.stderr).splitlines():
                if "vo score gate failed" in line:
                    why = line.split("failed:")[-1].strip()[:60]
                elif "content quality gate failed" in line:
                    why = "内容门禁: " + line.split("failed:")[-1].strip()[:48]
            return False, 0.0, why
        doc = json.loads(out.read_text(encoding="utf-8"))
        v = doc.get("vo_score") or {}
        note = (v.get("notes") or [""])[0][:56]
        return bool(v.get("pass")), float(v.get("score") or 0), note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-id", required=True)
    ap.add_argument("--tries", type=int, default=10)
    ap.add_argument("--seed0", type=int, default=None, help="起始种子(默认随机)")
    ap.add_argument("--plan-only", action="store_true",
                    help="只找出过关的种子,不做最终出片")
    a, extra = ap.parse_known_args()

    rng = random.Random(a.seed0 if a.seed0 is not None else None)
    seeds = ([a.seed0 + i for i in range(a.tries)] if a.seed0 is not None
             else [rng.randrange(1, 100003) for _ in range(a.tries)])

    print(f"试排 {a.episode_id}:最多 {a.tries} 个种子,取第一个 ≥95 的\n")
    best = (0.0, None, "")
    for i, s in enumerate(seeds, 1):
        ok, score, note = try_seed(s, a.episode_id, extra)
        mark = "✅" if ok else "  "
        print(f"  {mark} 种子 {s:<7} {score:>5.1f} 分  {note}")
        if score > best[0]:
            best = (score, s, note)
        if ok:
            if a.plan_only:
                print(f"\n✅ 过关种子 {s}({score} 分)。"
                      f"出片:build_session.py --seed {s} --episode-id {a.episode_id}")
                return 0
            print(f"\n用种子 {s} 正式出片…\n")
            r = subprocess.run(
                [str(PY), str(BUILD), "--episode-id", a.episode_id,
                 "--seed", str(s)] + extra)
            return r.returncode
    print(f"\n❌ {a.tries} 个种子都没过。最好的是种子 {best[1]}({best[0]} 分):{best[2]}")
    print("   连续多次卡在同一处,说明那是判据与编排的系统性矛盾,该去改管线,"
          "不是继续摇种子。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
