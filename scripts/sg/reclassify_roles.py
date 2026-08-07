#!/usr/bin/env python3
# coding: utf-8
"""用当前分类规则对全库重跑角色判定 —— 不重新转写,只用 manifest 里的文本。

为什么需要独立一步:采集器是「转写+切分+分类」三合一,规则一改就得重跑
whisper(几十分钟)。但分类只依赖文本,而文本已经在 manifest 里了。

2026-08-05 起因:G2 写了 45 句 safety,采集器只认出 7 条,83 条掉进
`dur >= 3.0 → poetic` 的兜底分支。和之前 bless 那次是同一个病根 ——
**按位置/时长兜底,而不是按语言形态判断**。

只改 manifest 与边车里的 `role`/`tags`;**不动 id 和文件路径**。
id 前缀(如 `poetic_ab12cd`)是采集当时的快照,已被其他产物引用
(隔离清单、发音复检清单)。改 id 会让那些引用全部失效。
→ **manifest 的 role 字段是权威**,目录与 id 前缀是历史痕迹。

  ./.venv/bin/python scripts/sg/reclassify_roles.py --dry-run
  ./.venv/bin/python scripts/sg/reclassify_roles.py
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import harvest_whisper as hw

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text())
    atoms = man["atoms"]

    # pos 需要母带总长 —— 取该母带内最大 t_end
    span: dict[str, float] = collections.defaultdict(float)
    for x in atoms:
        m = x.get("source_master", "?")
        span[m] = max(span[m], x.get("t_end", 0.0))

    moved = collections.Counter()
    before, after = collections.Counter(), collections.Counter()
    for x in atoms:
        before[x["role"]] += 1
        if not x.get("text"):
            after[x["role"]] += 1
            continue
        m = x.get("source_master", "?")
        pos = x.get("t_start", 0.0) / max(0.01, span[m])
        stags = hw.source_tags(m)
        positional = not re.search(r"_G\d+_", m)
        role, tags = hw.role_from_text(
            x["text"], pos, x.get("duration_sec", 0.0), stags, positional,
            addressee=x.get("addressee", ""))
        after[role] += 1
        if role != x["role"]:
            moved[(x["role"], role)] += 1
            if not a.dry_run:
                x["role_was"] = x["role"]
                x["role"] = role
                x["tags"] = tags

    print("=== 角色分布 变化 ===")
    print(f"  {'角色':<12}{'原':>6}{'新':>6}{'差':>7}")
    for r in sorted(set(before) | set(after)):
        d = after[r] - before[r]
        print(f"  {r:<12}{before[r]:>6}{after[r]:>6}{d:>+7}")

    print(f"\n=== 主要迁移(共 {sum(moved.values())} 条重分类)===")
    for (f, t), n in moved.most_common(12):
        print(f"  {f:>10} → {t:<10} {n:>4}")

    if a.dry_run:
        print("\n(dry-run,未写入)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    bak = MANIFEST.with_suffix(f".json.bak_reclassify_{stamp}")
    bak.write_text(MANIFEST.read_text())
    man["reclassified"] = {"at": datetime.now(timezone.utc).isoformat(),
                           "moved": sum(moved.values())}
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))

    n = 0
    for x in atoms:
        side = Path(x["path"]).with_suffix(".json")
        if side.exists():
            sd = json.loads(side.read_text())
            sd["role"] = x["role"]
            sd["tags"] = x.get("tags", [])
            side.write_text(json.dumps(sd, ensure_ascii=False, indent=1))
            n += 1
    print(f"\n✅ 已写入 manifest 与 {n} 个边车(备份 {bak.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
