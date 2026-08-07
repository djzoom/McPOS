#!/usr/bin/env python3
# coding: utf-8
"""用波形审计原子边界 —— 切点是落在静音里,还是切穿了正在说的话。

为什么不能用 whisper 判:2026-08-05 我用「向前多听 2 秒再转写」来找被切掉的
前导词,whisper 在一段**纯数字静音**上补出了 "Do not",因为约翰福音 14:1
的原文就是这么写的。照那个结论去修,会把 2 秒静音接进原子里。

    波形真相   165.45–168.45  −99 dBFS(纯数字静音,根本没有音频)
    语音起点   168.55  突然开始
    whisper    "Do not let your hearts be troubled."   ← 幻听补的

whisper 会脑补它熟悉的经文;波形不会。**边界问题只能看波形。**

判据:取母带的 RMS 包络(20ms 一格),阈值以上算发声。
  · 起点切穿   t_start 前 80ms 仍在发声 → 首词可能被削掉
  · 终点切穿   t_end 后 80ms 仍在发声   → 尾词可能被削掉
  · 空转       整条原子都在阈值以下     → 无语音(应已被隔离)

  ./.venv/bin/python scripts/sg/audit_boundaries.py
  ./.venv/bin/python scripts/sg/audit_boundaries.py --extend   # 把切穿的边界推到静音处
"""
from __future__ import annotations

import argparse
import array
import collections
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from atom_quality import usable

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
CONF = Path(__file__).resolve().parents[2] / "config"
SR = 16000
HOP = 0.020             # 包络分辨率 20ms
SPEECH_DB = -50.0       # 高于此算发声。Locke 的室内噪声约 −90dB,留足余量
GUARD = 0.080           # 边界外看这么久;仍在发声就是切穿
PAD = 0.060             # 外推时留的余量


def envelope(path: Path) -> tuple[list[float], float]:
    """整轨 RMS 包络(dBFS),每 HOP 秒一格。"""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
         "-ar", str(SR), "-f", "s16le", "-"], capture_output=True)
    a = array.array("h")
    a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    w = int(SR * HOP)
    out: list[float] = []
    for i in range(0, len(a) - w + 1, w):
        ch = a[i:i + w]
        s = 0
        for v in ch:
            s += v * v
        rms = math.sqrt(s / len(ch))
        out.append(20 * math.log10(rms / 32768) if rms > 0 else -99.0)
    return out, len(a) / SR


def loud(env: list[float], t: float) -> bool:
    i = int(t / HOP)
    return 0 <= i < len(env) and env[i] > SPEECH_DB


def scan_out(env: list[float], t: float, step: float, limit: float) -> float:
    """从 t 起按 step 方向找到连续静音的位置,最多走 limit 秒。"""
    n = int(limit / HOP)
    for k in range(1, n + 1):
        tt = t + step * k * HOP
        if not loud(env, tt):
            return tt
    return t + step * limit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extend", action="store_true",
                    help="把切穿的边界外推到最近的静音处并从母带重切")
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text())
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for x in man["atoms"]:
        if usable(x):
            by[x.get("source_master", "?")].append(x)

    head_cut: list[dict] = []
    tail_cut: list[dict] = []
    fixes: dict[str, tuple[float, float]] = {}
    print(f"逐母带计算 RMS 包络({int(HOP*1000)}ms 分辨率)…\n")
    for m, items in sorted(by.items()):
        p = Path(m)
        if not p.exists():
            continue
        env, total = envelope(p)
        nh = nt = 0
        for x in items:
            t0, t1 = float(x["t_start"]), float(x["t_end"])
            # 起点前 GUARD 秒仍在发声 → 切穿
            if loud(env, t0) and loud(env, max(0.0, t0 - GUARD)):
                head_cut.append(x)
                nh += 1
            if loud(env, max(0.0, t1 - HOP)) and loud(env, t1 + GUARD):
                tail_cut.append(x)
                nt += 1
            if a.extend:
                n0 = t0
                if loud(env, t0) and loud(env, max(0.0, t0 - GUARD)):
                    n0 = max(0.0, scan_out(env, t0, -1.0, 1.2) - PAD)
                n1 = t1
                if loud(env, max(0.0, t1 - HOP)) and loud(env, t1 + GUARD):
                    n1 = min(total, scan_out(env, t1, 1.0, 1.2) + PAD)
                if abs(n0 - t0) > 0.02 or abs(n1 - t1) > 0.02:
                    fixes[x["id"]] = (n0, n1)
        print(f"  {p.name[:52]}")
        print(f"    原子 {len(items):>4}   起点切穿 {nh:>3}   终点切穿 {nt:>3}")

    print(f"\n=== 合计 ===")
    print(f"  起点切穿(首词可能被削) {len(head_cut):>5}")
    print(f"  终点切穿(尾词可能被削) {len(tail_cut):>5}")

    if head_cut:
        print(f"\n--- 起点切穿样本 ---")
        for x in head_cut[:10]:
            print(f"  {x['text'][:62]}")

    # 把结论写回 manifest。**不改音频** —— 切穿是既成事实,
    # 外推边界会让相邻两条重叠(同一句话在一期里播两遍)。
    # 正确的处理是标记出来,由编排器约束用法:
    #   head_cut 的原子只能紧跟它在母带里的前一条
    #   tail_cut 的原子后面必须跟上它的后一条
    hid = {x["id"] for x in head_cut}
    tid = {x["id"] for x in tail_cut}
    stamp0 = datetime.now(timezone.utc).isoformat()
    for x in man["atoms"]:
        x["head_cut"] = x["id"] in hid
        x["tail_cut"] = x["id"] in tid
    man["boundary_audited"] = {"at": stamp0, "speech_db": SPEECH_DB,
                               "guard": GUARD, "hop": HOP}
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(f"\n✅ 已把 head_cut / tail_cut 标记写入 manifest")

    CONF.mkdir(exist_ok=True)
    (CONF / "sg_boundary_audit.json").write_text(json.dumps(
        {"generated": datetime.now(timezone.utc).isoformat(),
         "speech_db": SPEECH_DB, "guard": GUARD,
         "head_cut": [{"id": x["id"], "text": x["text"]} for x in head_cut],
         "tail_cut": [{"id": x["id"], "text": x["text"]} for x in tail_cut]},
        ensure_ascii=False, indent=1))
    print(f"\n明细 → config/sg_boundary_audit.json")

    if not a.extend or not fixes:
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    MANIFEST.with_suffix(f".json.bak_bounds_{stamp}").write_text(MANIFEST.read_text())
    done = 0
    for x in man["atoms"]:
        if x["id"] not in fixes:
            continue
        n0, n1 = fixes[x["id"]]
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{n0:.3f}", "-to", f"{n1:.3f}",
             "-i", x["source_master"], "-c:a", "libmp3lame", "-q:a", "2",
             x["path"]], capture_output=True, text=True)
        if r.returncode != 0:
            continue
        x["t_start_was"], x["t_end_was"] = x["t_start"], x["t_end"]
        x["t_start"], x["t_end"] = round(n0, 3), round(n1, 3)
        x["duration_sec"] = round(n1 - n0, 3)
        x["boundary_fixed_at"] = datetime.now(timezone.utc).isoformat()
        done += 1
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(f"✅ 外推并重切 {done} 条(备份 manifest.json.bak_bounds_{stamp})")
    print("   注意:文本未改 —— 重切只补回被削掉的音,须再跑一次转写核对文本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
