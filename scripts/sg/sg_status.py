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
    # 长片吃分子库,短片仍吃原子库 —— 两个数都要报,否则看不出谁在断档
    mol = _j(Path.home() / "Studio/Library/sg/molecules/manifest.json",
             {"molecules": []}).get("molecules", [])
    themes = {m.get("master_slug") for m in mol}
    print(f"║ 素材库   分子 {len(mol)} 条 / {len(themes)} 主题(长片)· "
          f"原子 {len(usable)} 条(短片)")

    # 成品(分子时代:sg_mol_v3_*;旧原子期 sg_gold_* 已停产,不计)
    eps = sorted(SESSIONS.glob("sg_mol_v3_*"))
    passed = ready = 0
    for d in eps:
        meta = _j(d / f"{d.name}_session.json", {})
        if (meta.get("content_gate") or {}).get("pass"):
            passed += 1
        vid = any(d.glob(f"{d.name}_rings.mp4")) or any(d.glob(f"{d.name}_pendulum.mp4"))
        if vid and (d / f"{d.name}.zh-Hant.srt").exists():
            ready += 1
    print(f"║ 成品     {len(eps)} 期 · 内容门放行 {passed} · 视频+三语齐备 {ready}")

    # 长片发布(2026-08-17 起分子时代:未播旧片已撤回,等新管线合格再传)
    master = _j(ROOT / "config/sg_schedule_master.json", {"episodes": []})
    rows = master.get("episodes", [])
    public = [r for r in rows if r.get("published_at_actual")]
    scheduled = [r for r in rows
                 if r.get("video_id") and not r.get("published_at_actual")]
    todo_long = [r for r in rows
                 if not r.get("video_id") and not r.get("hold")
                 and r.get("status") == "ready"]
    pending_recall = [r for r in rows if r.get("recall_needed")]
    nxt = min((r["schedule_date"] for r in scheduled
               if r.get("schedule_date", "") >= today.isoformat()), default=None)
    last = max((r.get("schedule_date", "") for r in rows), default="—")
    print(f"║ 长片     已公开 {len(public)} · 已传待播 {len(scheduled)}"
          f"(下一期 {nxt or '—'}) · 待传 {len(todo_long)} · 排至 {last}")
    if pending_recall:
        print(f"║ ⚠ 撤回   {len(pending_recall)} 条旧视频待删(例行自动处理)")

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
        todo.append(f"删旧视频 {len(pending_recall)} 条(daily_ops 步骤 2 自动)")
    if todo_long:
        todo.append(f"续传长片 {len(todo_long)} 期(daily_ops 步骤 5,按配额)")
    days_left = (date.fromisoformat(last) - today).days if last != "—" else 0
    if days_left < 45:
        todo.append(f"⚠ 长片库存剩 {days_left} 天(排至 {last})—— 该按 "
                    f"ATOM_SUPPLY_PLAN 轨道 B 录新主题母带了")
    if buffer < 3:
        todo.append(f"短片缓冲仅 {buffer} 天:daily_ops.py 会自动补")
    todo.append("日常:daily_ops.py(体检/评论/撤回/短片/字幕/长片/对账/日志)")

    print("\n下一步:")
    for i, t in enumerate(todo, 1):
        print(f"  {i}. {t}")
    print(f"\n详情:scripts/sg/RESUME.md · 管线清单:PIPELINE_FREEZE.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
