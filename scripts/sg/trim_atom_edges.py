#!/usr/bin/env python3
# coding: utf-8
"""修剪原子头尾静音 —— 从母带按修正后的边界重切。

2026-08-05 发现:134 条原子被质量门以「语速过低」剔除,但逐条测量后
真相是**切点没找准**,不是朗读太慢:

    "And he is not going anywhere."  10.1s 的片段里,尾部 6.6s 是空白
    实际语音约 3s → 真实语速 2.0 词/秒,完全正常

原门禁 MIN_DENSITY=0.9 是按正常语速定的。但这是助眠频道,带长停顿的
缓慢朗读**正是想要的效果**,拿正常语速卡它会误杀。真正的缺陷不是
「内部有停顿」,而是「头尾挂着静音」—— 那会让拼接处出现死气,
也让密度数字失真。

修法:silencedetect 找头尾静音 → 修正 t_start/t_end → **从母带重切**。
不就地裁剪 clip,因为母带才是源头,重切不会累积编码损失。
两端各留 PAD 秒室内噪声,避免拼接时听到硬切。

  ./.venv/bin/python scripts/sg/trim_atom_edges.py --dry-run
  ./.venv/bin/python scripts/sg/trim_atom_edges.py
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from atom_quality import words
import harvest_whisper as hw

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
ATOMS = Path.home() / "Studio/Library/sg/atoms"
# 参数一律偏保守 —— 修剪的收益是「拼接更干净」,代价是「可能切掉语音」。
# 两者不对等:少修一点只是留一点空白,多修一点就永久丢字。
NOISE_DB = -45          # 阈值放低。-35dB 会把气声收尾(如轻读的 "And.")当静音吃掉
MIN_SIL = 0.40          # 短于此的停顿不算静音 —— 句中换气必须放过
PAD = 0.25              # 两端保留的室内噪声,拼接时不至于硬切
MIN_TRIM = 0.50         # 少于此的修剪不值得冒险重切


def edges(path: Path, dur: float) -> tuple[float, float]:
    """返回 (头部静音秒, 尾部静音秒)。

    尾部判定必须确认最后一段静音**一直延伸到文件结尾** —— 否则会把
    句中的长停顿当成尾部空白。2026-08-05 第一版就栽在这:
    「Once more, inhale peace.〔3.4s 停顿〕Exhale.」的停顿被当成尾静音,
    修剪后 "Exhale." 整个消失了。语音只能少切,不能多切。
    """
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af",
         f"silencedetect=noise={NOISE_DB}dB:d={MIN_SIL}", "-f", "null", "-"],
        capture_output=True, text=True)
    # 按出现顺序解析,末尾静音可能没有配对的 silence_end(跑到 EOF)
    events = re.findall(r"silence_(start|end): ([-\d.]+)", r.stderr)
    segs: list[tuple[float, float | None]] = []
    for kind, val in events:
        v = float(val)
        if kind == "start":
            segs.append((v, None))
        elif segs and segs[-1][1] is None:
            segs[-1] = (segs[-1][0], v)
    if not segs:
        return 0.0, 0.0

    lead = 0.0
    if segs[0][0] <= 0.05 and segs[0][1] is not None:
        lead = segs[0][1]

    tail = 0.0
    s0, s1 = segs[-1]
    reaches_eof = s1 is None or s1 >= dur - 0.05
    if reaches_eof and s0 > lead:
        tail = max(0.0, dur - s0)
    return lead, tail


def cut_from_master(master: Path, t0: float, t1: float, dst: Path) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
         "-i", str(master), "-c:a", "libmp3lame", "-q:a", "2", str(dst)],
        capture_output=True, text=True)
    return r.returncode == 0 and dst.exists() and dst.stat().st_size > 0


def same_speech(clip: Path, expect: str, model: Path) -> bool:
    """修剪后的片段是否仍包含**完全相同**的话。

    比对归一化词序列而非字符串:whisper 的标点会随上下文变化,
    但词不该变。少一个词就说明切掉了语音,必须回滚。
    """
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(clip),
                            "-ar", "16000", "-ac", "1", str(wav)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return False
        r = subprocess.run(["whisper-cli", "-m", str(model), "-f", str(wav),
                            "-nt", "-l", "en"], capture_output=True, text=True)
        heard = " ".join(r.stdout.split())
    return words(heard) == words(expect)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text())
    todo = [x for x in man["atoms"]
            if x.get("text") and not x.get("quarantined") and Path(x["path"]).exists()]
    if a.limit:
        todo = todo[:a.limit]
    print(f"待检查原子 {len(todo)} 条(已隔离的不处理)\n")

    if not a.dry_run:
        bak = ATOMS.parent / f"atoms_bak_trim_{datetime.now():%Y%m%d_%H%M}"
        print(f"备份原子库 → {bak.name} …")
        shutil.copytree(ATOMS, bak, dirs_exist_ok=True)
        MANIFEST.with_suffix(f".json.bak_trim_{datetime.now():%Y%m%d_%H%M}"
                             ).write_text(MANIFEST.read_text())

    model = hw.resolve_model(None)
    trimmed = failed = skipped = reverted = 0
    recovered = 0
    for i, x in enumerate(todo, 1):
        p, dur = Path(x["path"]), float(x.get("duration_sec") or 0)
        if dur <= 0:
            skipped += 1
            continue
        lead, tail = edges(p, dur)
        cut = max(0.0, lead - PAD) + max(0.0, tail - PAD)
        if cut < MIN_TRIM:
            skipped += 1
            continue
        t0 = float(x["t_start"]) + max(0.0, lead - PAD)
        t1 = float(x["t_end"]) - max(0.0, tail - PAD)
        if t1 - t0 < 0.35:               # 修完只剩气音,不值得留
            skipped += 1
            continue
        master = Path(x["source_master"])
        if not master.exists():
            failed += 1
            continue
        if not a.dry_run:
            if not cut_from_master(master, t0, t1, p):
                failed += 1
                continue
            # 自检:修剪后必须还听得到**一模一样**的话。参数再保守也保不住
            # 每一条 —— 轻读的收尾词会低于噪声阈值被当静音吃掉。
            # 唯一可靠的验收是把修剪结果重新听一遍。
            if not same_speech(p, x["text"], model):
                cut_from_master(master, float(x["t_start"]), float(x["t_end"]), p)
                reverted += 1
                continue
            x["t_start"], x["t_end"] = t0, t1
            x["duration_was"] = dur
            # 时长以**修剪后的文件**为准,不是母带跨度 t1−t0。两者本会因
            # mp3 帧粒度差几十毫秒;而一旦哪天导出失败退回跨度,就是
            # 2026-08-11 那 222 条(最大差 7.66s)的翻版。探不出就不改时长,
            # 让 audit_atom_edges 去发现,不猜。
            real = hw.probe_duration(p)
            x["duration_sec"] = round(real, 3) if real else round(t1 - t0, 3)
            if not real:
                print(f"  ⚠ 修剪后时长探测失败,暂记母带跨度: {x['id']}")
            x["trimmed_at"] = datetime.now(timezone.utc).isoformat()
        trimmed += 1
        n = len(words(x["text"]))
        if n / max(0.01, dur) < 0.9 <= n / max(0.01, t1 - t0):
            recovered += 1
        if i % 200 == 0:
            print(f"  …{i}/{len(todo)}  修剪 {trimmed} · 跳过 {skipped}")

    print(f"\n=== 结果 ===")
    print(f"  修剪切点   {trimmed:>5}")
    print(f"  自检回滚   {reverted:>5}  (修剪会丢字,已还原)")
    print(f"  无需修剪   {skipped:>5}")
    print(f"  失败       {failed:>5}")
    print(f"  ▶ 因此从「语速过低」中救回 {recovered} 条")

    if a.dry_run:
        print("\n(dry-run,未写入)")
        return 0
    man["trimmed"] = {"at": datetime.now(timezone.utc).isoformat(),
                      "count": trimmed, "noise_db": NOISE_DB, "pad": PAD}
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print("\n✅ manifest 已更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
