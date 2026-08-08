#!/usr/bin/env python3
"""原子音频库全量健康体检。

起因（2026-08-08）：成片里听到语音与文字对不上。既有的 sg_atom_audit.json 只做了
whisper 复核相似度，1818 个原子里 986 个 MISMATCH——但那份审计只告诉你「不匹配」，
不告诉你**为什么**。本工具把三个来源对齐后给出可行动的分类：

  manifest.json  ← 切分真源（t_start / t_end / text / role / source_master）
  sg_atom_audit.json ← whisper 复核（verdict / sim / heard）
  文件系统       ← 实测时长与响度（ffprobe / volumedetect）

已知的三种坏法（抽样实测得出，本工具就是来量清它们各占多少的）：

1. **句中切断**——音频有正常响度的人声，但只是半句（heard='into our lives.'）。
   切分按固定长度而非语音边界，于是片段与它挂的 text 完全无关。
   这是「语音文字混乱」的主因。
2. **静音片段**——max 音量低于 -40 dB，whisper 只能吐出幻觉词（'you' / 'Thank you.'）。
3. **文字塌缩**——数百个原子共享同一句 text（403 个共享一句，328 个共享另一句），
   说明 text 赋值环节把一批原子写成了同一行。

用法:
    python scripts/sg/audit_atom_health.py                # 全量体检
    python scripts/sg/audit_atom_health.py --limit 200    # 快速抽查
    python scripts/sg/audit_atom_health.py --json out.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LIB = Path(os.path.expanduser("~/Studio/Library/sg/atoms"))
MANIFEST = LIB / "manifest.json"
AUDIT = Path(os.path.expanduser("~/Studio/Projects/McPOS/config/sg_atom_audit.json"))
SESSIONS = Path(os.path.expanduser("~/Studio/Workspace/outputs/sg/sessions"))

# 判据。都是从抽样实测里读出来的，不是拍脑袋：
SILENT_MAX_DB = -40.0    # OK 组的 max 在 -9~-12 dB；低于 -40 基本没有可听内容
TINY_SEC = 0.5           # 半秒以下装不下一个完整短句
FIXED_LEN_SEC = 1.09     # 反复出现的固定切长签名
FIXED_LEN_TOL = 0.03
DUP_TEXT_MIN = 5         # 同一句 text 被这么多原子共享即视为文字塌缩


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def probe(path: str) -> dict:
    """实测时长与响度。文件不存在返回 missing。"""
    if not os.path.exists(path):
        return dict(missing=True)
    dur = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "csv=p=0", path]).strip()
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                          "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    def grab(key):
        m = re.search(rf"{key}:\s*(-?[\d.]+|-inf) dB", err)
        if not m:
            return None
        return -999.0 if m.group(1) == "-inf" else float(m.group(1))
    return dict(missing=False,
                dur=float(dur) if dur else None,
                mean_db=grab("mean_volume"),
                max_db=grab("max_volume"))


def classify(a: dict) -> list[str]:
    """一个原子可能同时中多条，全都记下——修的时候要知道它坏在几处。"""
    flags = []
    if a.get("missing"):
        return ["MISSING"]
    dur, mx = a.get("dur"), a.get("max_db")
    if mx is not None and mx < SILENT_MAX_DB:
        flags.append("SILENT")
    if dur is not None and dur < TINY_SEC:
        flags.append("TINY")
    if dur is not None and abs(dur - FIXED_LEN_SEC) < FIXED_LEN_TOL:
        flags.append("FIXED_LEN")
    if a.get("verdict") == "MISMATCH" and "SILENT" not in flags:
        # 有声音、但 whisper 听到的与挂的 text 不符 → 句中切断
        flags.append("MIDCUT")
    if a.get("verdict") == "EMPTY":
        flags.append("EMPTY_VERDICT")
    if a.get("text_dup_count", 0) >= DUP_TEXT_MIN:
        flags.append("TEXT_COLLAPSE")
    if a.get("verdict") is None:
        flags.append("UNAUDITED")
    return flags or ["OK"]


def main() -> int:
    ap = argparse.ArgumentParser(description="原子音频库全量健康体检")
    ap.add_argument("--limit", type=int, default=0, help="只查前 N 个（快速抽查）")
    ap.add_argument("--json", default=None, help="把完整结果写到这个 JSON")
    ap.add_argument("--workers", type=int, default=4, help="并发 ffmpeg 数（默认 4，渲染同时在跑时别调高）")
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text())
    atoms = {x["id"]: x for x in man["atoms"]}
    audit = {r["id"]: r for r in json.loads(AUDIT.read_text())["rows"]} if AUDIT.exists() else {}

    # 文件系统才是最终事实：manifest 可能记着已删的，也可能漏记新增的
    on_disk = {p.stem: p for p in LIB.rglob("*.mp3")}

    ids = sorted(set(atoms) | set(on_disk))
    if a.limit:
        ids = ids[:a.limit]

    text_count = collections.Counter(x.get("text") for x in atoms.values() if x.get("text"))

    recs = []
    for i in ids:
        m = atoms.get(i, {})
        au = audit.get(i, {})
        path = m.get("path") or (str(on_disk[i]) if i in on_disk else "")
        recs.append(dict(
            id=i, path=path, role=m.get("role"),
            in_manifest=i in atoms, on_disk=i in on_disk,
            t_start=m.get("t_start"), t_end=m.get("t_end"),
            declared_dur=m.get("duration_sec"),
            source_master=os.path.basename(m.get("source_master") or ""),
            text=m.get("text") or au.get("text"),
            text_dup_count=text_count.get(m.get("text"), 0),
            verdict=au.get("verdict"), sim=au.get("sim"), heard=au.get("heard"),
        ))

    print(f"体检 {len(recs)} 个原子（manifest {len(atoms)} · 磁盘 {len(on_disk)} · "
          f"已审计 {len(audit)}）…", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r, pr in zip(recs, ex.map(lambda r: probe(r["path"]), recs)):
            r.update(pr)
            r["flags"] = classify(r)

    # ── 报告 ────────────────────────────────────────────────
    W = 74
    print("\n" + "═" * W)
    print("  原子音频库健康体检")
    print("═" * W)
    print(f"  manifest 记录 {len(atoms)} · 磁盘实有 {len(on_disk)} · 本次体检 {len(recs)}")
    orphan_disk = set(on_disk) - set(atoms)
    orphan_man = set(atoms) - set(on_disk)
    if orphan_disk:
        print(f"  ⚠ 磁盘有、manifest 没有：{len(orphan_disk)} 个（不会被选中，等于白占空间）")
    if orphan_man:
        print(f"  ⚠ manifest 有、磁盘没有：{len(orphan_man)} 个（选中就会崩）")

    flat = collections.Counter(f for r in recs for f in r["flags"])
    print("\n── 病症分布（一个原子可同时中多条）──")
    NAME = {
        "OK": "健康",
        "MIDCUT": "句中切断：有人声但与 text 不符 ← 语音文字混乱主因",
        "SILENT": f"静音：max < {SILENT_MAX_DB} dB",
        "FIXED_LEN": f"固定切长 {FIXED_LEN_SEC}s：按长度切而非按语音边界",
        "TINY": f"过短：< {TINY_SEC}s",
        "TEXT_COLLAPSE": f"文字塌缩：该 text 被 ≥{DUP_TEXT_MIN} 个原子共享",
        "EMPTY_VERDICT": "审计判为 EMPTY",
        "UNAUDITED": "从未被 whisper 复核",
        "MISSING": "文件不存在",
    }
    for f, c in flat.most_common():
        pct = c / len(recs) * 100
        print(f"  {f:<16} {c:>5} ({pct:>5.1f}%)  {NAME.get(f,'')}")

    healthy = [r for r in recs if r["flags"] == ["OK"]]
    print(f"\n── 结论 ──")
    print(f"  完全健康（无任何标记）：{len(healthy)} / {len(recs)}"
          f"  = {len(healthy)/len(recs)*100:.1f}%")

    print("\n── 按 role 分组的健康率 ──")
    by_role = collections.defaultdict(lambda: [0, 0])
    for r in recs:
        k = r["role"] or "?"
        by_role[k][1] += 1
        if r["flags"] == ["OK"]:
            by_role[k][0] += 1
    for role, (ok, tot) in sorted(by_role.items(), key=lambda kv: -kv[1][1]):
        bar = "█" * int(ok / tot * 24) if tot else ""
        print(f"  {role:<12} {ok:>4}/{tot:<5} {ok/tot*100:>5.1f}%  {bar}")

    print("\n── 文字塌缩：被最多原子共享的 text ──")
    for t, c in text_count.most_common(5):
        if c < DUP_TEXT_MIN:
            break
        print(f"  {c:>4} 个 ← {t[:58]!r}")

    print("\n── 切长分布（前 8）——固定值扎堆 = 按长度切 ──")
    dur_bins = collections.Counter(round(r["dur"], 2) for r in recs if r.get("dur"))
    for d, c in dur_bins.most_common(8):
        print(f"  {d:>6.2f}s  {c:>5} 个  {'█'*int(c/25)}")

    # ── 追到成片：哪几期用了病态原子 ──
    print("\n── 受影响的成片（session 的 plan 引用了病态原子）──")
    sick = {r["id"] for r in recs if r["flags"] != ["OK"]}
    hits = []
    for sj in sorted(SESSIONS.glob("*/*_session.json")):
        try:
            plan = json.loads(sj.read_text()).get("plan", [])
        except Exception:
            continue
        used = [p.get("id") for p in plan if p.get("type") == "atom" and p.get("id")]
        bad = [u for u in used if u in sick]
        if used:
            hits.append((sj.parent.name, len(bad), len(used)))
    for name, bad, tot in sorted(hits, key=lambda x: -x[1] / max(x[2], 1)):
        pct = bad / tot * 100 if tot else 0
        mark = "🔴" if pct > 30 else ("🟡" if pct > 5 else "🟢")
        print(f"  {mark} {name:<22} 病态 {bad:>3}/{tot:<3} 原子 ({pct:>5.1f}%)")
    if not hits:
        print("  （没找到带 plan 的 session）")

    if a.json:
        Path(a.json).write_text(json.dumps(
            dict(generated=None, counts=dict(flat), records=recs),
            ensure_ascii=False, indent=1))
        print(f"\n完整结果 → {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
