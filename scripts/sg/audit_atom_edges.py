#!/usr/bin/env python3
# coding: utf-8
"""原子**自身**的尾部是否停在满音量 —— 写入 tail_hard_cut。

⚠ 这项单独**不作数**。它与 audit_boundaries 的 tail_cut 两项证据同时成立,
才算确凿的「尾词被削」(判据见 atom_quality.tail_truncated)。实测已知收音
干净的 584 条里仍有 19 条尾部电平高于阈值 —— 单靠电平会误杀。

⚠ 没有对应的头部判据。**语音的起音本来就陡**,重读的第一个音节 120ms 内
就能逼近全局峰值;照搬同一套量法,第一个被判「首词被削」的是频道招牌
「Welcome to Sleep in Grace.」。物理不成立的测量不能当门禁。


与 audit_boundaries.py 的分工(2026-08-11 分家):

    audit_boundaries  量**母带**在原子边界之外还在不在发声
                      → 证明「采集丢了话」,但不证明这条原子自己残缺
    audit_atom_edges  量**原子文件自己**的首尾能量
                      → 证明「这个词被削掉了半个」,是听感缺陷的直接证据

分家的由来:sg_gold_001 里 "set apart for restoration." 被 tail_cut 标记,
文本却是完整句;实测它自己的尾部已衰减到 −13 dB,听不出问题。
而 "Do not be afraid or terrified." 的尾部停在 **−0.0 dB(满音量)** ——
那才是真的被拦腰截断。拿前者当后者用,会白白砍掉大批可用素材。

实测分离度(2026-08-11,白名单可用池抽样):

    tail_cut 标记组   末尾相对整体  平均 −4.4 dB(最高 +0.0)
    未标记对照组      末尾相对整体  平均 −15.7 dB(最高 −10.4)

阈值取 −8 dB:落在两组之间的空档里,对照组无一误伤。

  ./.venv/bin/python scripts/sg/audit_atom_edges.py            # 全量,写回 manifest
  ./.venv/bin/python scripts/sg/audit_atom_edges.py --dry-run  # 只报告
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atom_quality import load_whitelist, reject_reason

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
EDGE_WIN = 0.12         # 首尾各取这么长来量
# 阈值取自**对照组的实测分布**,不是拍脑袋:
# 已知收音干净的 584 条(母带无续声且文本是完整句)尾部相对整体
#   中位 −16.0 dB · 90 分位 −9.9 dB · **最高 −2.6 dB**
# 取 −3.0 落在这条分布之外 —— 干净的原子从不出现这种收尾。
# 早先试过 −8.0,那是凭直觉定的,会把 19 条干净原子一并划进去。
HARD_CUT_DB = -3.0
_VOL_RE = re.compile(r"max_volume:\s*(-?[\d.]+) dB")


def peak_db(path: str, ss: float | None = None, dur: float | None = None) -> float | None:
    """一段音频的峰值电平。**-ss 必须在 -i 之前**(输出端定位对 volumedetect
    不生效,首尾会量出同一个数,看着像「全库无差异」)。"""
    cmd = ["ffmpeg", "-v", "info"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", path, "-af", "volumedetect", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = _VOL_RE.search(r.stderr)
    return float(m.group(1)) if m else None


def real_duration(path: str) -> float | None:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def measure(atom: dict) -> dict:
    """量首尾能量。时长**必须现探**,不能信 manifest。

    2026-08-11 实测:白名单可用池里 35% 的原子,manifest 的 duration_sec
    与文件实际时长对不上,最大差 6.74s(标称 10.05s / 实际 3.31s)。
    按标称时长去定位末尾会落到文件之外,ffmpeg 什么都不输出 —— 第一版
    就这样静默跳过了 30% 的原子,还报告说「测得 506 条」。
    """
    p = atom["path"]
    d = real_duration(p)
    if d is None or d <= EDGE_WIN * 2:
        return {"id": atom["id"], "ok": False, "why": "过短或读不出时长"}
    full = peak_db(p)
    head = peak_db(p, 0.0, EDGE_WIN)
    tail = peak_db(p, max(0.0, d - EDGE_WIN))
    if None in (full, head, tail):
        return {"id": atom["id"], "ok": False, "why": "电平测量失败"}
    return {"id": atom["id"], "ok": True, "full": full, "real_dur": d,
            "manifest_dur": float(atom.get("duration_sec") or 0),
            "head_rel": head - full, "tail_rel": tail - full}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="量全库(默认只量白名单可用池 —— 其余进不了片)")
    ap.add_argument("--fix-duration", action="store_true",
                    help="把 manifest 的 duration_sec 校正为文件实际时长")
    ap.add_argument("--jobs", type=int, default=0)
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    wl = load_whitelist()
    pool = man["atoms"] if a.all else [x for x in man["atoms"]
                                       if reject_reason(x, wl) is None]
    jobs = a.jobs or max(2, (os.cpu_count() or 4) - 2)
    print(f"量 {len(pool)} 条原子的首尾 {int(EDGE_WIN*1000)}ms 能量({jobs} 并行)…")

    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        all_rows = list(ex.map(measure, pool))
    rows = [r for r in all_rows if r.get("ok")]
    skipped = [r for r in all_rows if not r.get("ok")]

    tail_hard = {r["id"] for r in rows if r["tail_rel"] > HARD_CUT_DB}
    print(f"  测得 {len(rows)} 条")
    if skipped:
        # 跳过必须逐条报出来。静默跳过 30% 还报告「测得 506 条」,
        # 与只数条数的假 PASS 是同一种病。
        why = {}
        for r in skipped:
            why[r.get("why", "?")] = why.get(r.get("why", "?"), 0) + 1
        print(f"  ⚠ 跳过 {len(skipped)} 条:"
              + " · ".join(f"{k} {v}" for k, v in why.items()))
    print(f"  终点停在满音量 {len(tail_hard):>4}(单独不作数,须与 tail_cut 双证)")

    # —— 顺带查时长漂移:选片打分、语速门、密度填充都拿它当输入 ——
    drift = [r for r in rows if abs(r["manifest_dur"] - r["real_dur"]) > 0.3]
    if drift:
        worst = max(drift, key=lambda r: abs(r["manifest_dur"] - r["real_dur"]))
        print(f"\n⚠ manifest 时长与文件不符 {len(drift)}/{len(rows)} 条"
              f"(最大差 {abs(worst['manifest_dur']-worst['real_dur']):.2f}s:"
              f"标称 {worst['manifest_dur']:.2f}s / 实际 {worst['real_dur']:.2f}s)")
        print("   影响:score_atom 的时长偏好、vo_score 的语速门、密度填充的长度估算")
        print("   修复:--fix-duration")

    old_tail = {x["id"] for x in pool if x.get("tail_cut")}
    both, only_old, only_new = old_tail & tail_hard, old_tail - tail_hard, tail_hard - old_tail
    print(f"\n与 audit_boundaries 的 tail_cut 对照(母带续声 vs 自身硬切):")
    print(f"  两者都判为切穿 {len(both):>4}  ← 确凿")
    print(f"  只有母带续声   {len(only_old):>4}  ← 采集丢了话,但这条自己收得干净")
    print(f"  只有自身硬切   {len(only_new):>4}  ← 母带那边没声了,自己却停在满音量")

    if only_new:
        print("\n  只有自身硬切的例子:")
        by_id = {x["id"]: x for x in pool}
        for i in list(only_new)[:5]:
            r = next(r for r in rows if r["id"] == i)
            print(f"    尾部 {r['tail_rel']:+.1f} dB  「{by_id[i].get('text','')[:52]}」")

    if a.dry_run:
        print("\n(dry-run,未写回 manifest)")
        return 0

    n = 0
    for x in man["atoms"]:
        if x["id"] in tail_hard:
            n += 1
        x["tail_hard_cut"] = x["id"] in tail_hard
        x.pop("head_hard_cut", None)   # 头部判据已证伪,清掉早期写入的残留
    fixed = 0
    if a.fix_duration:
        real = {r["id"]: r["real_dur"] for r in rows}
        for x in man["atoms"]:
            rd = real.get(x["id"])
            if rd and abs(float(x.get("duration_sec") or 0) - rd) > 0.01:
                # 保留原值:t_start/t_end 是母带坐标,续接判定全靠它们,不能动;
                # 这里改的只是「这个文件有多长」。
                x.setdefault("duration_sec_declared", x.get("duration_sec"))
                x["duration_sec"] = round(rd, 3)
                fixed += 1
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✅ head_hard_cut / tail_hard_cut 已写入 manifest({n} 条被标记)")
    if a.fix_duration:
        print(f"✅ duration_sec 已按实际文件校正 {fixed} 条(原值存入 duration_sec_declared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
