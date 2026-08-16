#!/usr/bin/env python3
# coding: utf-8
"""VO 检测门 —— 对一期计划打分(0–100),≥95 视为通过。

只读 plan(秒级),不渲染音频;定位是**编排质量的量化门**,
与 qc_session 的关系:
  · A 层判据(A1–A6)直接 `from qc_session import check_text` 复用 ——
    同一概念一处判据,这里只负责把违规折算成扣分;
  · B 层(whisper 反查)仍归 qc_session,那是渲染后的事。

三个维度(与频道定位对齐:睡前祷告,节奏须随进度放缓):

【T 时序与停顿 40】
  T1  8  停顿深化:后 1/3 平均停顿 ≥ 前 1/3 × 1.25(听者入睡,间隔应变大)
  T2 10  语音密度:全期 speech/total ∈ [0.35, 0.55]
  T3  8  后半程降速:后半 speech 密度 ≤ 前半 × 0.9
  T4  8  异常停顿:整句后停顿 <1.2s(赶)或原子 pad >40s(死气)逐处扣
  T5  6  祝福前静默:BLESS 首原子前累计间隔 ≥5s,且 REST_BEFORE_BLESS
         与 BLESS 之间不得夹语音原子(静默才是规则认可的切换点)

【C 表述清晰度 30】
  A1 半截句无人接 −6/处 · A2 指代硬切 −5/处 · A3 隔离泄漏 −10/处
  C4 句法碎片(连词开头/虚词结尾/波形切穿)出现在非续接位 −3/处
  C5 语速 >3.5 词/秒(念太快,睡前听不清) −2/处
  C6 重词结巴(相邻原子时间重叠且共用边界词,同一个词念两遍) −3/处
  C7 悬空句(停在 does not/to/and 上却另起新句,念头永远没说完) −8/处

【S 行文结构 30】
  S1 弧线:开场在前、CLOSE 收尾、BLESS 紧邻其前 −4/违规
  A4 期内重复 −4/处 · A5 CTA −6/处 · A6 角色错位 −5/处
  S5 同角色连跑 >4 条 −2/段(单一角色霸屏,行文单调)
  S6 视角/指代违规(audit) −5/处

  ./.venv/bin/python scripts/sg/vo_score.py --plan out.json
  ./.venv/bin/python scripts/sg/vo_score.py --session qc01 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atom_quality import (FLOW_GAP, MAX_OVERLAP, SYNTAX_REPAIR_GAP,
                          WAVEFORM_REPAIR_GAP,
                          completes_dangling, dangling_tail,
                          head_fragment_reason, tail_fragment_reason,
                          tail_truncated, words)
from qc_session import CLOSE_FORM, TERMINAL, check_text

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
PASS_SCORE = 95.0

# A 层违规 → (维度, 单处扣分)。判据在 qc_session,这里只定价。
A_PRICE = {
    "A1": ("C", 6.0), "A2": ("C", 5.0), "A3": ("C", 10.0),
    "A4": ("S", 4.0), "A5": ("S", 6.0), "A6": ("S", 5.0),
}


# 间隔判据一律来自 atom_quality —— 出片端与验收端共用一份,不得在此另行定义。


def _is_continuation(prev: dict | None, cur: dict, max_gap: float = FLOW_GAP) -> bool:
    """与编排器/审计同一定义:同母带、sequence_index + 1、且间隔在容差内。

    容差分两档:语流续接 18s(管行文),波形修复 0.35s(管完整性)。
    只查序号不查间隔的话,间隔 4.91s 的两条也算「已补完」——
    sg_gold_001 原 cue47/48 就是这样漏过去的。
    """
    if not (prev is not None
            and prev.get("source_master") == cur.get("source_master")
            and int(cur.get("source_sequence_index", -1))
            == int(prev.get("source_sequence_index", -2)) + 1):
        return False
    gap = float(cur.get("source_t_start") or 0) - float(prev.get("source_t_end") or 0)
    return MAX_OVERLAP <= gap <= max_gap


def _timing(plan: list[dict]) -> tuple[float, list[str]]:
    notes: list[str] = []
    atoms = [p for p in plan if p.get("type") == "atom"]
    if len(atoms) < 6:
        return 0.0, ["T 原子过少,无法评时序"]
    score = 0.0

    # T1 停顿深化
    pads = [float(p.get("pad_after_sec") or 0) for p in atoms]
    third = max(1, len(pads) // 3)
    early, late = sum(pads[:third]) / third, sum(pads[-third:]) / third
    ratio = late / max(0.1, early)
    t1 = 8.0 * min(1.0, max(0.0, (ratio - 1.0) / 0.25))
    if t1 < 8.0:
        notes.append(f"T1 停顿深化不足:后/前 = {ratio:.2f}(目标 ≥1.25) −{8-t1:.1f}")
    score += t1

    # 全期时长与语音量
    end = 0.0
    for p in plan:
        if p.get("type") == "atom":
            end = max(end, float(p.get("end_sec") or 0) + float(p.get("pad_after_sec") or 0))
        else:
            end = max(end, float(p.get("start_sec") or 0) + float(p.get("sec") or 0))
    speech = sum(float(p.get("duration_sec") or 0) for p in atoms)
    dens = speech / max(1.0, end)

    # T2 语音密度
    if 0.35 <= dens <= 0.55:
        t2 = 10.0
    else:
        dev = (0.35 - dens) if dens < 0.35 else (dens - 0.55)
        t2 = max(0.0, 10.0 - dev / 0.05 * 2.0)
        notes.append(f"T2 语音密度 {dens:.2f} 出带(0.35–0.55) −{10-t2:.1f}")
    score += t2

    # T3 后半程降速
    half = end / 2.0
    s1 = sum(float(p.get("duration_sec") or 0) for p in atoms
             if float(p.get("start_sec") or 0) < half)
    s2 = speech - s1
    d1, d2 = s1 / max(1.0, half), s2 / max(1.0, end - half)
    rr = d2 / max(0.01, d1)
    t3 = 8.0 if rr <= 0.9 else max(0.0, 8.0 - (rr - 0.9) / 0.1 * 4.0)
    if t3 < 8.0:
        notes.append(f"T3 后半程未降速:后/前密度 = {rr:.2f}(目标 ≤0.9) −{8-t3:.1f}")
    score += t3

    # T4 异常停顿
    t4 = 8.0
    for i, p in enumerate(atoms):
        pad = float(p.get("pad_after_sec") or 0)
        text = str(p.get("text") or "")
        nxt = atoms[i + 1] if i + 1 < len(atoms) else None
        if pad > 40.0:
            t4 -= 2.0
            notes.append(f"T4 死气停顿 {pad:.0f}s: 「{text[:36]}」 −2")
        elif (nxt is not None and TERMINAL.search(text) and pad < 1.2
              and not _is_continuation(p, nxt)):
            t4 -= 2.0
            notes.append(f"T4 整句后仅停 {pad:.1f}s: 「{text[:36]}」 −2")
    score += max(0.0, t4)

    # T5 祝福前静默
    t5 = 6.0
    bless_idx = next((i for i, p in enumerate(plan)
                      if p.get("type") == "atom"
                      and str(p.get("slot", "")).upper() == "BLESS"), None)
    if bless_idx is not None:
        gap, j = 0.0, bless_idx - 1
        while j >= 0:
            q = plan[j]
            if q.get("type") == "silence":
                gap += float(q.get("sec") or 0)
                j -= 1
                continue
            gap += float(q.get("pad_after_sec") or 0)
            break
        if gap < 5.0:
            t5 = 0.0
            notes.append(f"T5 BLESS 前间隔仅 {gap:.1f}s(目标 ≥5s) −6")
        rest_idx = next((i for i, p in enumerate(plan)
                         if "REST_BEFORE_BLESS" in str(p.get("slot", "")).upper()), None)
        if rest_idx is not None and any(
                p.get("type") == "atom" for p in plan[rest_idx + 1:bless_idx]):
            t5 = 0.0
            notes.append("T5 REST_BEFORE_BLESS 与 BLESS 之间夹了语音原子 −6")
    score += t5
    return min(40.0, score), notes


def _clarity(plan: list[dict], a_bad: list[str]) -> tuple[float, list[str]]:
    notes: list[str] = []
    score = 30.0
    for b in a_bad:
        dim, price = A_PRICE.get(b[:2], (None, 0.0))
        if dim == "C":
            score -= price
            notes.append(f"{b[:64]} −{price:g}")
    atoms = [p for p in plan if p.get("type") == "atom"]
    # 碎片分两向:头部残缺(head_cut/连词开头)须**紧跟前句**;
    # 尾部残缺(tail_cut/无句末标点/虚词结尾)须**被后继接上**。
    for i, p in enumerate(atoms):
        # 只有**双证确凿被削**的尾部才要求紧邻补救(0.35s):那半个词就躺在
        # 下一条里。其余(母带续声、句法碎片)语流完整,普通续接(18s)即可。
        hw = head_fragment_reason(p)
        if hw:
            if not _is_continuation(atoms[i - 1] if i else None, p, FLOW_GAP):
                score -= 3.0
                notes.append(f"C4 碎片无前句({hw}): 「{str(p.get('text'))[:36]}」 −3")
        tw = tail_fragment_reason(p)
        if tw:
            if tail_truncated(p):
                gap = WAVEFORM_REPAIR_GAP
            elif "无句末标点" in tw or "以虚词结尾" in tw:
                gap = SYNTAX_REPAIR_GAP
            else:
                gap = FLOW_GAP
            if not (i + 1 < len(atoms) and _is_continuation(p, atoms[i + 1], gap)):
                score -= 3.0
                notes.append(f"C4 碎片无后继({tw}): 「{str(p.get('text'))[:36]}」 −3")
    # C7 悬空句没被接上:句子停在 does not / to / and 这类必须带补语的词上,
    # 后面却另起了一个大写开头的新句 —— 那个念头永远没说完。
    # 光看间隔查不出来:实测有一对只隔 1.67s,序号也相邻,门禁一路放行,
    # 听感却是「…the Spirit of God dwells in you and he does not ／
    # You can rest because he watches over you.」
    for i, p in enumerate(atoms):
        t = str(p.get("text") or "")
        d = dangling_tail(t)
        if not d:
            continue
        nxt = atoms[i + 1] if i + 1 < len(atoms) else None
        if not nxt or not completes_dangling(t, str(nxt.get("text") or "")):
            # 扣 8 分而非 5:一句话永远没说完,听感上比结巴(−3)严重得多,
            # 接近隔离原子泄漏(−10)。扣 5 分会让这种片子正好落在 95.0 擦边
            # 通过 —— 门槛旁边的巧合不该决定能不能发。
            score -= 8.0
            notes.append(f"C7 悬空句「…{d}」无人接续: 「{t[-34:]}」 −8")

    # C6 重词结巴:两条原子在母带里**时间上重叠**,且前一条的末词等于后一条的
    # 首词 —— 那个词在两个文件里各存了一份,会被念两遍(「Now, Lord, as ／
    # As I lie down」「Let me lie. ／ Lie down…」)。
    # 判据靠**间隔为负**,不能只看重词:「…surrounds you.」接「You are invited…」
    # 也重了个 you,但两句间隔 6 秒、各自完整,那是正常衔接;
    # 「You can rest… ／ You can sleep…」更是刻意的排比。
    for i in range(len(atoms) - 1):
        a, b = atoms[i], atoms[i + 1]
        wa, wb = words(str(a.get("text") or "")), words(str(b.get("text") or ""))
        if not (wa and wb and wa[-1] == wb[0]):
            continue
        if a.get("source_master") != b.get("source_master"):
            continue
        if float(b.get("source_t_start") or 0) - float(a.get("source_t_end") or 0) >= 0:
            continue
        score -= 3.0
        notes.append(f"C6 重词结巴「…{wa[-1]}」+「{wb[0]}…」: "
                     f"「{str(b.get('text'))[:32]}」 −3")

    for p in atoms:
        # 时长一律用**成品轨实测**(vo_end − vo_start)。manifest 的 duration_sec
        # 有 30% 与文件对不上(最大差 7.66s),拿它算语速会算出三倍的偏差。
        dur = float(p.get("vo_end_sec") or 0) - float(p.get("vo_start_sec") or 0)
        if dur <= 0:
            dur = float(p.get("duration_sec") or p.get("source_duration_sec") or 0)
        n = len(words(str(p.get("text") or "")))
        if dur > 0 and n / dur > 3.5:
            score -= 2.0
            notes.append(f"C5 语速 {n/dur:.1f} 词/秒: 「{str(p.get('text'))[:36]}」 −2")
    return max(0.0, score), notes


def _structure(plan: list[dict], a_bad: list[str], audit: dict) -> tuple[float, list[str]]:
    notes: list[str] = []
    score = 30.0
    for b in a_bad:
        dim, price = A_PRICE.get(b[:2], (None, 0.0))
        if dim == "S":
            score -= price
            notes.append(f"{b[:64]} −{price:g}")
    atoms = [p for p in plan if p.get("type") == "atom"]
    if atoms:
        # S1 弧线
        first = str(atoms[0].get("slot", "")).upper()
        if first not in ("COLD_OPEN", "OPEN"):
            score -= 4.0
            notes.append(f"S1 开场槽位是 {first} −4")
        last = str(atoms[-1].get("slot", "")).upper()
        if last != "CLOSE":
            score -= 4.0
            notes.append(f"S1 收尾槽位是 {last} −4")
        slots = [str(p.get("slot", "")).upper() for p in atoms]
        if "BLESS" in slots and "CLOSE" in slots:
            if slots.index("CLOSE") < len(slots) - slots[::-1].index("BLESS") - 1:
                score -= 4.0
                notes.append("S1 CLOSE 出现在 BLESS 之前 −4")
        # S1 强结尾形态出现在中段:结尾语一响听者以为节目完了。
        # 品牌开场(COLD_OPEN/OPEN 的 "…Sleep in Grace")按槽位豁免。
        for p in atoms:
            sid = str(p.get("slot", "")).upper()
            if sid in ("COLD_OPEN", "OPEN", "BLESS", "CLOSE"):
                continue
            if CLOSE_FORM.search(str(p.get("text") or "")):
                score -= 4.0
                notes.append(f"S1 强结尾形态出现在 {sid}: "
                             f"「{str(p.get('text'))[:36]}」 −4")
        # S5 同角色连跑。母带续接链算**一个单元**:五条原子连成的一段
        # 完整经文诵读不是单调,是一次朗读。
        run_role, run_len = None, 0
        prev_atom = None
        for p in atoms + [{}]:
            r = p.get("role")
            if r == run_role:
                if not _is_continuation(prev_atom, p):
                    run_len += 1
                prev_atom = p if p else None
                continue
            if run_role is not None and run_len > 4:
                score -= 2.0
                notes.append(f"S5 角色 {run_role} 连跑 {run_len} 段 −2")
            run_role, run_len = r, 1
            prev_atom = p if p else None
    # S6 视角/指代(audit 已算好,不重算)
    for k in ("perspective_violations", "addressee_violations"):
        for v in (audit.get(k) or []):
            score -= 5.0
            notes.append(f"S6 {k}: {str(v)[:48]} −5")
    return max(0.0, score), notes


def score_plan(doc: dict) -> dict:
    plan = doc.get("plan") or []
    audit = doc.get("audit") or {}
    man = json.loads(MANIFEST.read_text())
    quarantined = {x["id"]: x["quarantined"] for x in man["atoms"]
                   if x.get("quarantined")}
    a_bad = check_text(plan, quarantined)
    t, tn = _timing(plan)
    c, cn = _clarity(plan, a_bad)
    s, sn = _structure(plan, a_bad, audit)
    total = round(t + c + s, 1)
    return {
        "episode_id": doc.get("episode_id"),
        "seed": doc.get("seed"),
        "score": total,
        "pass": total >= PASS_SCORE,
        "timing": round(t, 1), "clarity": round(c, 1), "structure": round(s, 1),
        "notes": tn + cn + sn,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", type=Path, help="build_session --plan-output 产物")
    g.add_argument("--session", help="sessions 目录里的期号")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    p = a.plan if a.plan else SESSIONS / a.session / f"{a.session}_session.json"
    doc = json.loads(Path(p).read_text())
    r = score_plan(doc)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        mark = "✅" if r["pass"] else "❌"
        print(f"{mark} {r['episode_id']}  总分 {r['score']}  "
              f"(时序 {r['timing']}/40 · 清晰 {r['clarity']}/30 · 结构 {r['structure']}/30)")
        for n in r["notes"]:
            print(f"   · {n}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
