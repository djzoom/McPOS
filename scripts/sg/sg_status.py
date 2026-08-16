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

    # 长片发布
    master = _j(ROOT / "config/sg_schedule_master.json", {"episodes": []})
    rows = master.get("episodes", [])
    live = [r for r in rows if r.get("video_id")]
    future = sorted(r["schedule_date"] for r in rows
                    if r.get("schedule_date", "") >= today.isoformat())
    print(f"║ 长片     已上线 {len(live)}/{len(rows)} · "
          f"下一期 {future[0] if future else '—'} · 排至 {rows[-1]['schedule_date'] if rows else '—'}")

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
    if len(live) < len(rows):
        todo.append(f"传剩余 {len(rows)-len(live)} 期长片:sg_batch_upload.py")
    if buffer < 3:
        todo.append(f"短片缓冲仅 {buffer} 天:daily_ops.py 会自动补")
    last = rows[-1]["schedule_date"] if rows else today.isoformat()
    days_left = (date.fromisoformat(last) - today).days
    if days_left < 45:
        todo.append(f"⚠ 长片库存仅剩 {days_left} 天(排至 {last})——"
                    f"该启动补料了:见 ATOM_SUPPLY_PLAN.md 轨道 B")
    todo.append("日常:daily_ops.py(评论/短片/字幕/长片/日志 五步)")

    print("\n下一步:")
    for i, t in enumerate(todo, 1):
        print(f"  {i}. {t}")
    print(f"\n详情:scripts/sg/RESUME.md · 管线清单:PIPELINE_FREEZE.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
