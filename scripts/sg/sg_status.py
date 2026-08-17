#!/usr/bin/env python3
# coding: utf-8
"""一屏看清「现在到哪了、下一步做什么」—— 新会话的接力棒。

不写死状态数字(会过时),全部现场汇总:素材库、成品、发布、配额,
最后给出**下一步建议**(按依赖与截止日排序)。

新会话第一条命令就跑它,不必翻旧对话。

  ./.venv/bin/python scripts/sg/sg_status.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quota                                                  # noqa: E402
from atom_quality import load_whitelist, reject_reason        # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
TOYTUNE = Path.home() / "Projects/TOYTUNE"


def _j(p: Path, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d


def main() -> int:
    today = date.today()
    print(f"╔═ Sleep in Grace · {today} ═══════════════════════")

    # 素材库
    man = _j(MANIFEST, {"atoms": []})
    try:
        wl = load_whitelist()
    except Exception:
        wl = None
    usable = [a for a in man.get("atoms", []) if reject_reason(a, wl) is None]
    print(f"║ 素材库   可用 {len(usable)} 条 / 全库 {len(man.get('atoms', []))}")

    # 成品
    eps = sorted(SESSIONS.glob("sg_gold_*"))
    ready = [d for d in eps if (d / f"{d.name}_rings.mp4").exists()
             and (d / f"{d.name}.zh-Hans.srt").exists()]
    print(f"║ 成品     {len(eps)} 期 · 六件齐备 {len(ready)} 期")

    # 长片发布(2026-08-17 起分子时代:未播旧片已撤回,等新管线合格再传)
    master = _j(ROOT / "config/sg_schedule_master.json", {"episodes": []})
    rows = master.get("episodes", [])
    public = [r for r in rows if r.get("published_at_actual")]
    held = [r for r in rows if r.get("hold")]
    pending_recall = [r for r in rows if r.get("recall_needed")]
    print(f"║ 长片     已公开 {len(public)} · 已撤回 {len(held)}"
          + (f" · 待撤 {len(pending_recall)}" if pending_recall else "")
          + " · 新片等分子管线")

    # 短片发布
    st = _j(TOYTUNE / "publish_state.json", {"uploaded": {}}).get("uploaded", {})
    sched = _j(TOYTUNE / "shorts_schedule.json", {"episodes": []}).get("episodes", [])
    now = datetime.now(timezone.utc).isoformat()
    buffer = sum(1 for v in st.values() if v.get("publish_at", "") > now)
    print(f"║ 短片     已传 {len(st)}/{len(sched)} · 未公开缓冲 {buffer} 天")

    # 配额
    print(f"║ 配额     今日已用 {quota.spent_today()}u · 可用 {quota.remaining()}u")
    print("╚" + "═" * 50)

    # —— 下一步建议:按「会不会断档」排序,不是按事情大小 ——
    todo: list[str] = []
    if pending_recall:
        todo.append(f"撤回续跑剩 {len(pending_recall)} 期(daily_ops 会自动续)")
    if held:
        todo.append("分子管线联调:build_molecule_session → content_gate "
                    "稳定放行 → 重制期次 → 重新排播(见 RESUME.md)")
    if buffer < 3:
        todo.append(f"短片缓冲仅 {buffer} 天:daily_ops.py 会自动补")
    todo.append("日常:daily_ops.py(评论/撤回/短片/字幕/长片/日志 六步)")

    print("\n下一步:")
    for i, t in enumerate(todo, 1):
        print(f"  {i}. {t}")
    print(f"\n详情:scripts/sg/RESUME.md · 管线清单:PIPELINE_FREEZE.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
