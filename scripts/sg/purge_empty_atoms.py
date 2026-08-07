#!/usr/bin/env python3
# coding: utf-8
"""清查「有文本但没语音」的原子 —— 合成时会变成有字幕却无声。

2026-08-05 发现:397 条原子的语速 >6 词/秒,物理上不可能。逐条转写后确认
它们是**静音片段**,whisper 在静音上幻听出 "you" / "Thank you.",而
`audit_atom_library.py --relabel` 检测到幻听后选择**保留原文本** ——
于是相邻句子的文本被永久钉在了一段静音上。

  错在哪:幻听 ≠「转写失败,沿用旧文本」,而是「这段音频没有语音」。

检测靠语速密度做粗筛(文本词数 / 音频时长),再逐条转写做终判:
  · 密度 > MAX_DENSITY  → 文本与音频不匹配,进入复核
  · 复核转写为空或幻听词 → no_speech,隔离
  · 复核转写有实词       → 用新文本纠正(和 --relabel 同样的修法)

  ./.venv/bin/python scripts/sg/purge_empty_atoms.py --dry-run
  ./.venv/bin/python scripts/sg/purge_empty_atoms.py --quarantine
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import harvest_whisper as hw

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
MAX_DENSITY = 4.0        # 词/秒。正常朗读 2–3,冥想语速更慢
HALLUCINATION = {"you", "thank you", "bye", "so", "thanks for watching",
                 "thank you for watching", "u", "the", "yeah", ""}


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()


def density(x: dict) -> float:
    return len(words(x["text"])) / max(0.01, x.get("duration_sec", 0.01))


def hear(path: Path, model: Path) -> str:
    """单条转写。返回归一化后的听写文本。"""
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                            "-ar", "16000", "-ac", "1", str(wav)],
                           capture_output=True, text=True)
        if r.returncode != 0 or not wav.exists():
            return ""
        r = subprocess.run(["whisper-cli", "-m", str(model), "-f", str(wav),
                            "-nt", "-l", "en"], capture_output=True, text=True)
        return " ".join(r.stdout.split()).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quarantine", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    model = hw.resolve_model(None)
    man = json.loads(MANIFEST.read_text())
    atoms = [x for x in man["atoms"] if x.get("text")
             and not x.get("quarantined")]

    susp = [x for x in atoms if density(x) > MAX_DENSITY]
    if a.limit:
        susp = susp[:a.limit]
    print(f"密度 > {MAX_DENSITY} 词/秒的可疑原子:{len(susp)} / {len(atoms)}")
    print("逐条转写复核中(静音片段会听成 you / Thank you.)…\n")

    empty, fixed, kept = [], [], []
    for i, x in enumerate(susp, 1):
        p = Path(x["path"])
        heard = hear(p, model) if p.exists() else ""
        norm = re.sub(r"[^a-z ]", "", heard.lower()).strip()
        if norm in HALLUCINATION or len(words(heard)) < 2:
            empty.append((x, heard))
        elif norm != re.sub(r"[^a-z ]", "", x["text"].lower()).strip():
            fixed.append((x, heard))
        else:
            kept.append(x)
        if i % 50 == 0:
            print(f"  …{i}/{len(susp)}  无语音 {len(empty)} · "
                  f"待纠正 {len(fixed)} · 正常 {len(kept)}")

    print(f"\n=== 复核结果 ===")
    print(f"  🔴 无语音(静音带假文本)  {len(empty):>5}")
    print(f"  🟡 有语音但文本错          {len(fixed):>5}")
    print(f"  🟢 文本正确(密度误报)    {len(kept):>5}")

    if empty:
        print(f"\n--- 无语音原子按角色 ---")
        for r, n in collections.Counter(x["role"] for x, _ in empty).most_common():
            print(f"  {r:<12}{n:>5}")
        print(f"\n--- 被错钉在静音上的文本 top5 ---")
        for t, n in collections.Counter(x["text"] for x, _ in empty).most_common(5):
            print(f"  ×{n:<4} {t[:56]}")

    if a.dry_run or not a.quarantine:
        print("\n(未写入。加 --quarantine 执行隔离与纠正)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    bak = MANIFEST.with_suffix(f".json.bak_purge_{stamp}")
    bak.write_text(MANIFEST.read_text())
    ids_empty = {x["id"] for x, _ in empty}
    new_text = {x["id"]: h for x, h in fixed}
    now = datetime.now(timezone.utc).isoformat()
    for x in man["atoms"]:
        if x["id"] in ids_empty:
            x["quarantined"] = "no_speech"
            x["quarantined_at"] = now
            x["text_was"] = x["text"]
        elif x["id"] in new_text:
            x["text_was"] = x["text"]
            x["text"] = new_text[x["id"]]
            x["relabeled_at"] = now
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(f"\n🔒 隔离 {len(ids_empty)} 条无语音 · 纠正 {len(new_text)} 条文本"
          f"(备份 {bak.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
