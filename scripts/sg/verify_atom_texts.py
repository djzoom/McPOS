#!/usr/bin/env python3
# coding: utf-8
"""逐条核对原子的文本与音频是否一致 —— 全库,不抽样。

抽样会骗人:2026-08-05 抽 20 条全对,以为文本已经干净,结果验收时
「May your spirit be blessed.」被听成「May your spirit be pleased with you.」。
1.2 秒的音频配 5 个词的文本,单看密度也不算离谱 —— 只有真的听一遍才知道。

与 audit_atom_library --relabel 的区别:
  · 批量调用 whisper(一次传 120 个文件),不再每条重新加载 1.5GB 模型
  · 听不出内容时**不沿用旧文本**,标记为无语音 —— 旧版在这里选择保留,
    结果 418 条静音永久钉着相邻句的文本
  · 不自动改写文本。短原子上 whisper 本身就不可靠(会按语感补词),
    自动改写等于用一个不确定的结果覆盖另一个 —— 只标记,交人工定夺

  ./.venv/bin/python scripts/sg/verify_atom_texts.py
  ./.venv/bin/python scripts/sg/verify_atom_texts.py --mark
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import harvest_whisper as hw
from atom_quality import usable, words
from sg_media import backup_with_retention

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
CONF = Path(__file__).resolve().parents[2] / "config"
BATCH = 120
HALLUC = {"you", "thank you", "bye", "so", "thanks for watching", "", "u"}
NEAR = 0.90            # 词序列相似度低于此算不符


def sim(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mark", action="store_true",
                    help="把结论写回 manifest(text_mismatch / no_speech)")
    ap.add_argument("--write-whitelist", action="store_true",
                    help="按本次复核结果重建 config/sg_atom_whitelist.json"
                         "(完全一致 + 仅转写差异 = 放行)")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    model = hw.resolve_model(None)
    man = json.loads(MANIFEST.read_text())
    todo = [x for x in man["atoms"] if usable(x) and Path(x["path"]).exists()]
    if a.limit:
        todo = todo[:a.limit]
    print(f"核对 {len(todo)} 条可用原子(批量 {BATCH} 条/次)…\n")

    heard: dict[str, str] = {}
    for b in range(0, len(todo), BATCH):
        chunk = todo[b:b + BATCH]
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            wavs = []
            for x in chunk:
                w = d / f"{len(wavs):05d}.wav"
                r = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-i", x["path"],
                     "-ar", "16000", "-ac", "1", str(w)],
                    capture_output=True, text=True)
                if r.returncode == 0 and w.exists():
                    wavs.append((x["id"], w))
            subprocess.run(
                ["whisper-cli", "-m", str(model), "-nt", "-l", "en", "-otxt"]
                + [str(w) for _, w in wavs], capture_output=True, text=True)
            for k, w in wavs:
                t = Path(str(w) + ".txt")
                heard[k] = (" ".join(t.read_text(errors="ignore").split())
                            if t.exists() else "")
        print(f"  …{min(b + BATCH, len(todo))}/{len(todo)}")

    exact, near, mismatch, silent = [], [], [], []
    for x in todo:
        h = heard.get(x["id"], "")
        hw_, xw = words(h), words(x["text"])
        if h.strip().lower().rstrip(".") in HALLUC or not hw_:
            silent.append((x, h))
        elif hw_ == xw:
            exact.append(x)
        elif sim(hw_, xw) >= NEAR:
            near.append((x, h))
        else:
            mismatch.append((x, h))

    n = len(todo)
    print(f"\n=== 结果({n} 条)===")
    print(f"  ✅ 完全一致        {len(exact):>5}  {len(exact)/n:.1%}")
    print(f"  🟢 仅转写差异      {len(near):>5}  {len(near)/n:.1%}  (相似度≥{NEAR})")
    print(f"  🔴 文本与音频不符  {len(mismatch):>5}  {len(mismatch)/n:.1%}")
    print(f"  ⚫️ 听不出内容      {len(silent):>5}  {len(silent)/n:.1%}")

    if mismatch:
        print(f"\n--- 不符样本(前 20)---")
        for x, h in mismatch[:20]:
            print(f"  文本: {x['text'][:58]}")
            print(f"  实际: {h[:58]}")
        by = collections.Counter(x["role"] for x, _ in mismatch)
        print(f"\n  按角色: {dict(by)}")

    CONF.mkdir(exist_ok=True)
    (CONF / "sg_text_audio_verify.json").write_text(json.dumps(
        {"generated": datetime.now(timezone.utc).isoformat(), "checked": n,
         "exact": len(exact), "near": len(near),
         "mismatch": [{"id": x["id"], "text": x["text"], "heard": h,
                       "role": x["role"], "sec": x.get("duration_sec")}
                      for x, h in mismatch],
         "silent": [{"id": x["id"], "text": x["text"]} for x, _ in silent]},
        ensure_ascii=False, indent=1))
    print(f"\n明细 → config/sg_text_audio_verify.json")

    if not a.mark:
        print("(未写回。加 --mark 标记 text_mismatch / no_speech)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_with_retention(MANIFEST, "verify")
    mm = {x["id"]: h for x, h in mismatch}
    sl = {x["id"] for x, _ in silent}
    now = datetime.now(timezone.utc).isoformat()
    for x in man["atoms"]:
        if x["id"] in sl:
            x["quarantined"] = "no_speech"
            x["quarantined_at"] = now
        elif x["id"] in mm:
            x["quarantined"] = "text_mismatch"
            x["quarantined_at"] = now
            x["heard"] = mm[x["id"]]
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(f"🔒 已隔离 {len(mm)} 条文本不符 + {len(sl)} 条无语音"
          f"(备份 manifest.json.bak_verify_{stamp})")

    if a.write_whitelist:
        # 白名单 = 本次**逐条听过**且文本对得上的原子(完全一致 + 仅转写差异)。
        # 它必须与本次复核同批产生:2026-08-05 那份白名单只覆盖 1818 条中的
        # 827 条,却被当成全库判据用了一周,把可用池压到 728 —— 期间重叠率
        # 因此长期超标,根因不是素材少,是这份名单陈旧且偏保守。
        wl_path = CONF / "sg_atom_whitelist.json"
        if wl_path.exists():
            wl_path.with_suffix(f".json.bak_{stamp}").write_text(
                wl_path.read_text(encoding="utf-8"), encoding="utf-8")
        ids = [x["id"] for x in exact] + [x["id"] for x, _ in near]
        wl_path.write_text(json.dumps({
            "generated": now,
            "criterion": f"verify_atom_texts 逐条转写复核:完全一致 或 相似度≥{NEAR}",
            "checked": n, "whitelisted": len(ids), "ids": ids,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"📋 白名单已重建:{len(ids)}/{n} 条放行 → {wl_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
