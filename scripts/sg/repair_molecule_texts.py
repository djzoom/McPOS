#!/usr/bin/env python3
# coding: utf-8
"""分子库文本复核 —— 对内容门送来的可疑条目重新转写、按证据改库。

来源:content_gate 的 G7 逐词对账。成片转写与库文本不一致时,门会对该
分子的 mp3 做第三次独立转写仲裁;判定「库文本失真、成片无辜」的条目
进 config/sg_molecule_repair_queue.json —— 那是**队列不是判决**,真正
改库要在这里,拿新转写当证据。

为什么必须改库(而不是放着):库文本是选段期的判据依据(尾态完整性、
视角分类、经文识别),也是 G7 下一次对账的基准。留着一条错的,它会
一直制造摩擦,还可能让好段落被误拒。
(2026-08-20 首批三条:「You are being held **low**」「hold us still
**in peace**」「The Lord is near **death**」—— 末一条若漏进字幕是
神学事故,虽然成片字幕取自成片转写、并未受影响。)

  KMP_DUPLICATE_LIB_OK=TRUE ./.venv/bin/python scripts/sg/repair_molecule_texts.py
  加 --apply 才写库;不加只报告。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_whisper import (          # noqa: E402
    resolve_model, transcribe_isolated_runs)
from molecule_quality import books_heard, reject_reason  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "config" / "sg_molecule_repair_queue.json"
MANIFEST = Path.home() / "Studio/Library/sg/molecules/manifest.json"
WORK = Path.home() / "Studio/Workspace/temp/sg_mol_repair"


def transcribe(mp3: Path, model: Path) -> str:
    """逐语音段隔离转写(共用原语,见 harvest_whisper.transcribe_isolated_runs)。"""
    return transcribe_isolated_runs(mp3, model, WORK)


def minimal_tail_fix(old: str, new: str) -> str | None:
    """只截掉老文本尾部多出来的词,其余原样保留。

    三条实测的错都在尾巴(held **low** / still **in peace** / near
    **death**),而老文本正文的标点比逐段重转的更干净 —— 整段覆盖等于
    拿噪声换正确,最小改动才是对的:找出两者对齐的最后一个词,把老文本
    在那里截断并补句号。若差异不在尾部(正文中段也不一致),返回 None
    交给整段替换,不硬凑。
    """
    norm = lambda t: [w.strip(".,;:!?").lower() for w in t.split() if w.strip(".,;:!?")]
    ow, nw = norm(old), norm(new)
    if not ow or not nw:
        return None
    blocks = difflib.SequenceMatcher(None, ow, nw).get_matching_blocks()
    tail = [b for b in blocks if b.size > 0]
    if not tail:
        return None
    last = tail[-1]
    # 新文本在对齐块之后没有内容,老文本却还有 → 老的尾巴是多余的
    if last.b + last.size != len(nw) or last.a + last.size >= len(ow):
        return None
    keep_words = last.a + last.size
    # 在原文里数到第 keep_words 个词为止(保留原标点)
    cnt, cut = 0, 0
    for i, ch in enumerate(old):
        if ch == " " and i and old[i - 1] != " ":
            cnt += 1
            if cnt == keep_words:
                cut = i
                break
    else:
        return None
    return old[:cut].rstrip(" ,;:") .rstrip(".") + "."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写回库")
    a = ap.parse_args()
    if not QUEUE.exists():
        print("队列为空")
        return 0
    ids = json.loads(QUEUE.read_text())
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in man["molecules"]}
    model = resolve_model(None)

    changed, kept = [], []
    for mid in ids:
        m = by_id.get(mid)
        if not m:
            print(f"⏭ {mid} 已不在库中")
            continue
        fresh = transcribe(Path(m["path"]), model)
        if not fresh:
            print(f"⚠ {mid} 重转写失败,保留原文本(不猜)")
            continue
        old = m["text"]
        sim = difflib.SequenceMatcher(None, old.lower(), fresh.lower()).ratio()
        print(f"\n{mid}  相似度 {sim:.2f}")
        print(f"  旧: …{old[-80:]}")
        print(f"  新: …{fresh[-80:]}")
        if fresh.strip() == old.strip():
            kept.append(mid)
            print("  → 一致,原样保留")
            continue
        # 改库前先过库判据:新文本若反而不合格,宁可不改(改坏比不改更糟)
        probe = dict(m, text=fresh, words=len(fresh.split()),
                     books_heard=books_heard(fresh))
        why = reject_reason(probe)
        if why:
            print(f"  → 新文本被库判据拒收[{why}],不改")
            kept.append(mid)
            continue
        minimal = minimal_tail_fix(old, fresh)
        if minimal:
            print(f"  → 最小改动: …{minimal[-56:]}")
            fresh = minimal
        changed.append((mid, old, fresh))
        if a.apply:
            m.update(text=fresh, words=len(fresh.split()),
                     books_heard=books_heard(fresh),
                     text_repaired_at="2026-08-20")
            print("  → 已改库")
        else:
            print("  → 待改(加 --apply 生效)")

    if a.apply:
        MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        QUEUE.write_text(json.dumps([m for m in kept], ensure_ascii=False, indent=1))
        print(f"\n✅ 改库 {len(changed)} 条 · 队列剩 {len(kept)} 条")
    else:
        print(f"\n待改 {len(changed)} 条 · 保留 {len(kept)} 条(--apply 才写)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
