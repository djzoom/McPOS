#!/usr/bin/env python3
# coding: utf-8
"""分子采集 —— 母带按段落停顿(≥6s)整块入库,段内绝不切。

复用 harvest_whisper 已验证的机器(span_phrases:silencedetect 找边界、
逐段送 whisper、静音不进解码器所以无幻觉路径),只把静音阈值从句级
0.8s 换成段级 6.0s(依据见 molecule_quality 模块头)。

母带表是显式的:哪支母带有段落结构、主题经文是什么,写死在这里 ——
13 支母带,显式列表胜过聪明解析;G1/G2(逐句录制清单)与台标不在表内。

  KMP_DUPLICATE_LIB_OK=TRUE ./.venv/bin/python scripts/sg/harvest_molecules.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_whisper import (          # noqa: E402
    export_clip, resolve_model, span_phrases, to_wav16k)
from molecule_quality import (         # noqa: E402
    MAX_DUR, MIN_SPEECH, PARA_SILENCE, SPAN_PAD, books_heard,
    edge_peak_db, reject_reason, tail_state)
from sg_media import probe_duration    # noqa: E402

LOCKE = Path.home() / "Studio/Library/sg/assets/vo/Locke"
OUT = Path.home() / "Studio/Library/sg/molecules"
WORK = Path.home() / "Studio/Workspace/temp/sg_molecule_work"

# 主题母带表:文件名关键片段 → (slug, 主经文, 全部经文)
# 每支母带就是一场围绕一处经文的完整祷告 —— 这正是「每期一处经文」的天然单位。
THEMED = [
    ("0906Fall_Asleep_Knowing",      "deut31",   "Deuteronomy 31:6",
     ["Deuteronomy 31:6"]),   # 母带实读 31:6(曾按文件名猜 31:8)
    ("0908_Peace_That_Surpasses",    "john14",   "John 14:27",
     ["John 14:27", "Philippians 4:7"]),
    ("God_Is_Still_Speaking",        "ps121a",   "Psalm 121",
     ["Psalm 121", "Lamentations 3:22-23"]),
    ("Peace_Beyond_Understanding",   "phil4",    "Philippians 4:6-7",
     ["Philippians 4:6-7"]),
    ("Rest_Secure_in_God",           "ps4a",     "Psalm 4:8",
     ["Psalm 4:8", "Isaiah 41:10"]),
    ("Isaiah26_Philippians4_Psalm4", "isa26",    "Isaiah 26:3",
     ["Isaiah 26:3", "Philippians 4:7", "Psalm 4:8"]),
    ("John10_Psalm62",               "john10",   "John 10:28",
     ["John 10:28", "Psalm 62:1-2"]),
    ("Psalm121_Lamentations3",       "ps121b",   "Psalm 121:4",
     ["Psalm 121:3-4", "Lamentations 3:22-23"]),
    ("Psalm16_Matthew28",            "ps16",     "Psalm 16:8",
     ["Psalm 16:8-9", "Matthew 28:20"]),
]


def role_of(pos: float, text: str) -> str:
    low = text.lower()
    if "welcome to sleep in grace" in low:
        return "open"
    if pos > 0.9 and ("amen" in low.split()[-1:] or "amen." in low[-8:].lower()):
        return "close"
    if low.startswith(("may you", "may the", "may his")):
        return "bless"
    if pos < 0.08:
        return "open"
    if pos > 0.92:
        return "close"
    return "body"


def main() -> int:
    model = resolve_model(None)
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    masters = sorted(LOCKE.glob("*.mp3"))
    mols: list[dict] = []
    skipped: list[dict] = []
    for master in masters:
        hit = next(((slug, prim, refs) for key, slug, prim, refs in THEMED
                    if key in master.name), None)
        if hit is None:
            print(f"⏭  非主题母带(逐句清单/台标),不采分子: {master.name[:60]}")
            continue
        slug, primary, refs = hit
        print(f"\n▶ {slug}  {master.name[:64]}")
        wav = to_wav16k(master, WORK / f"{master.stem}.wav")
        spans = span_phrases(wav, model, WORK, min_sil=PARA_SILENCE,
                             pad=SPAN_PAD, min_speech=MIN_SPEECH)
        total = probe_duration(wav) or 1.0

        # 悬空合并环:尾巴悬空(句子跨过 ≥6s 长停)或下一段小写起头的,
        # 与下一段合并成一个更大的分子 —— 合并后仍是母带连续原声,
        # 表达完整性靠合并挽回,不靠拒收牺牲。收敛为止。
        merged = True
        while merged:
            merged = False
            for i in range(len(spans) - 1):
                t0, t1, tx = spans[i]
                n0, n1, nx = spans[i + 1]
                dangle = tail_state(tx) == "dangling"
                cont_head = nx.strip()[:1].islower()
                if (dangle or cont_head) and (n1 - t0) <= MAX_DUR:
                    spans[i] = (t0, n1, f"{tx} {nx}".strip())
                    del spans[i + 1]
                    print(f"  ⤞ 合并段 {i}+{i+1}"
                          f"({'悬空尾' if dangle else '小写头'},{n1-t0:.0f}s)")
                    merged = True
                    break
        for i, (t0, t1, text) in enumerate(spans):
            pos = (t0 + t1) / 2 / total
            hid = hashlib.sha1(f"{master.name}:{t0:.3f}".encode()).hexdigest()[:10]
            mid = f"mol_{slug}_{i:03d}_{hid}"
            dst = OUT / slug / f"{mid}.mp3"
            if not export_clip(master, t0, t1, dst):
                print(f"  ⚠ 导出失败 {t0:.1f}–{t1:.1f}")
                continue
            dur = probe_duration(dst)
            if dur is None:
                dur = probe_duration(dst)
            if dur is None or dur <= 0:
                print(f"  ⚠ 时长探测失败,不入库: {mid}")
                continue
            mol = {
                "id": mid,
                "path": str(dst),
                "source_master": str(master),
                "master_slug": slug,
                "primary_scripture": primary,
                "scriptures": refs,
                "span_index": i,
                "span_count": len(spans),
                "pos": round(pos, 3),
                "t_start": round(t0, 3),
                "t_end": round(t1, 3),
                "duration_sec": round(dur, 3),
                "text": text,
                "words": len(text.split()),
                "books_heard": books_heard(text),
                "role": role_of(pos, text),
                "edge_head_db": edge_peak_db(dst, head=True),
                "edge_tail_db": edge_peak_db(dst, head=False),
                "method": "span6s_whisper_large_v3_turbo",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            why = reject_reason(mol)
            if why:
                mol["reject"] = why
                skipped.append(mol)
                print(f"  ✗ {mid} [{why}] {dur:5.1f}s 「{text[:44]}」")
            else:
                mols.append(mol)
                print(f"  ✓ {mid} {dur:5.1f}s {mol['role']:<5} 「{text[:44]}」")

    OUT.joinpath("manifest.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(),
         "para_silence": PARA_SILENCE,
         "molecules": mols, "rejected": skipped},
        ensure_ascii=False, indent=1), encoding="utf-8")
    themes = {m["master_slug"] for m in mols}
    print(f"\n✅ 分子 {len(mols)} 条(拒 {len(skipped)})· 主题 {len(themes)} 个"
          f" → {OUT/'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
