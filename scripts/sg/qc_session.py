#!/usr/bin/env python3
# coding: utf-8
"""一期节目的完整验收 —— 先验文案,再用 whisper 反查音频。

分两层,顺序不能颠倒:文案不合格就不必渲染音频了。

【A 文案层】只读 plan,秒级完成
  A1 半截句子   原子切在句中却没有后继补完 → 听众听到半句话
  A2 指代硬切   祷告句(you=上帝)紧邻旁白句(you=听者),指代当场翻转
  A3 隔离泄漏   被判自比上帝 / 无语音的原子出现在片中
  A4 重复       同一句话在一期里出现两次
  A5 引导关注   睡前祷告里不该有 CTA
  A6 角色错位   祝福位上不是祝福、结尾位上不是结尾

【B 音频层】whisper 反查,分钟级
  B1 WER        音频真正说出的话 vs 剧本(容忍转写噪声 6%)
  B2 漏句       剧本里有、音频里找不到
  B3 多出       音频里有、剧本里没有 —— 说明某条原子的文本是错的

  ./.venv/bin/python scripts/sg/qc_session.py --session qc01
  ./.venv/bin/python scripts/sg/qc_session.py --session qc01 --text-only
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import harvest_whisper as hw
from atom_quality import words

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
WER_LIMIT = 0.06
CTA = re.compile(r"\b(subscribe|follow the channel|leave a comment|"
                 r"like this video|turn on notifications)\b", re.I)
TERMINAL = re.compile(r"[.!?]\s*[\"”]?\s*$")
BLESS_FORM = re.compile(r"^\s*may\s|\bthe lord bless\b|\bpeace be with you\b", re.I)
# 与 build_session.STRONG_CLOSE_RE 保持同源 —— 两处判据分头演化的话,
# 编排器认可的结尾会被验收判成错位,反之亦然
CLOSE_FORM = re.compile(
    r"\b(amen|peace be with you|good night|sleep in grace|"
    r"in (?:the )?name of jesus|in jesus(?: christ)?'?s name|"
    r"make me dwell in safety|dwell in safety)\b", re.I)


def norm(t: str) -> str:
    return " ".join(words(t))


def check_text(plan: list[dict], quarantined: dict[str, str]) -> list[str]:
    atoms = [p for p in plan if p.get("type") == "atom"]
    bad: list[str] = []

    # A1 半截句子:切在句中的原子,后面必须紧跟母带里的下一条
    for i, p in enumerate(atoms):
        t = (p.get("text") or "").strip()
        if not t or TERMINAL.search(t):
            continue
        nxt = atoms[i + 1] if i + 1 < len(atoms) else None
        # 「相邻」一律用母带序号判定,不用时间戳。采集时相邻原子的切点会有
        # 几十毫秒重叠(实测 −0.09s),按时间戳配容差只会不停调参数;
        # 而编排器与内容审计用的都是 sequence_index + 1,三处必须一致。
        follows = (nxt is not None
                   and nxt.get("source_master") == p.get("source_master")
                   and int(nxt.get("source_sequence_index", -1))
                   == int(p.get("source_sequence_index", -2)) + 1)
        if not follows:
            bad.append(f"A1 半截句子无人接: 「{t[:52]}」")

    # A2 指代硬切:中性句与静默是仅有的合法切换点
    prev = None
    for p in plan:
        if p.get("type") != "atom":
            prev = None
            continue
        if prev:
            a, b = prev.get("addressee", "neutral"), p.get("addressee", "neutral")
            if a != b and "neutral" not in (a, b):
                bad.append(f"A2 指代 {a}→{b}: 「{str(prev.get('text'))[:30]}」"
                           f" ‖ 「{str(p.get('text'))[:30]}」")
        prev = p

    # A3 隔离泄漏
    for p in atoms:
        why = quarantined.get(p.get("id", ""))
        if why:
            bad.append(f"A3 隔离原子入片({why}): 「{str(p.get('text'))[:46]}」")

    # A4 重复
    seen: dict[str, int] = {}
    for p in atoms:
        k = norm(p.get("text") or "")
        if not k:
            continue
        seen[k] = seen.get(k, 0) + 1
    for k, n in seen.items():
        if n > 1:
            bad.append(f"A4 重复 ×{n}: 「{k[:46]}」")

    # A5 CTA
    for p in atoms:
        if CTA.search(p.get("text") or ""):
            bad.append(f"A5 引导关注: 「{str(p.get('text'))[:46]}」")

    # A6 角色错位
    for p in atoms:
        sid = str(p.get("slot", "")).upper()
        t = p.get("text") or ""
        if sid == "BLESS" and not BLESS_FORM.search(t):
            bad.append(f"A6 祝福位不是祝福: 「{t[:46]}」")
        if sid == "CLOSE" and not CLOSE_FORM.search(t):
            bad.append(f"A6 结尾位不是结尾: 「{t[:46]}」")
    return bad


def speech_spans(vo: Path) -> list[tuple[float, float]]:
    """VO 里的语音段(静音的补集)。"""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(vo), "-af",
         "silencedetect=noise=-45dB:d=0.5", "-f", "null", "-"],
        capture_output=True, text=True)
    total = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(vo)], capture_output=True,
        text=True).stdout.strip() or 0)
    sil: list[tuple[float, float]] = []
    cur = None
    for kind, val in re.findall(r"silence_(start|end): ([-\d.]+)", r.stderr):
        v = float(val)
        if kind == "start":
            cur = v
        elif cur is not None:
            sil.append((cur, v))
            cur = None
    if cur is not None:
        sil.append((cur, total))
    out, t = [], 0.0
    for s, e in sil:
        if s > t + 0.05:
            out.append((max(0.0, t - 0.15), min(total, s + 0.15)))
        t = e
    if t < total - 0.05:
        out.append((max(0.0, t - 0.15), total))
    return out


def transcribe(vo: Path, model: Path) -> str:
    """按语音段切开再转写 —— **不能整轨喂给 whisper**。

    这一期的静音是刻意设计的(助眠频道要大间隔),而 whisper 在长静音上
    会复读上一句:整轨转写听出 862 词,剧本只有 640 词,多出的全是
    「peace you are my portion you are my」「christ it does not depend on christ」
    这类复读幻觉。把静音摘掉再转,幻觉源就没了。
    """
    spans = speech_spans(vo)
    parts: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        wavs = []
        for i, (s, e) in enumerate(spans):
            w = d / f"{i:04d}.wav"
            q = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}",
                 "-to", f"{e:.3f}", "-i", str(vo), "-ar", "16000", "-ac", "1",
                 str(w)], capture_output=True, text=True)
            if q.returncode == 0 and w.exists():
                wavs.append((i, w))
        for b in range(0, len(wavs), 120):
            subprocess.run(
                ["whisper-cli", "-m", str(model), "-nt", "-l", "en", "-otxt"]
                + [str(w) for _, w in wavs[b:b + 120]],
                capture_output=True, text=True)
        for i, w in wavs:
            t = Path(str(w) + ".txt")
            if t.exists():
                parts.append(" ".join(t.read_text(errors="ignore").split()))
    print(f"     (VO 切出 {len(spans)} 个语音段,静音不送转写)")
    return " ".join(p for p in parts if p)


def wer(ref: list[str], hyp: list[str]) -> float:
    sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    same = sum(b.size for b in sm.get_matching_blocks())
    return 1.0 - same / max(1, len(ref))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--text-only", action="store_true")
    a = ap.parse_args()

    D = SESSIONS / a.session
    meta = json.loads((D / f"{a.session}_session.json").read_text())
    plan = meta.get("plan") or []
    man = json.loads(MANIFEST.read_text())
    quarantined = {x["id"]: x["quarantined"] for x in man["atoms"]
                   if x.get("quarantined")}

    atoms = [p for p in plan if p.get("type") == "atom"]
    print(f"=== {a.session}:{len(atoms)} 条原子 ===\n")

    print("【A 文案层】")
    bad = check_text(plan, quarantined)
    if not bad:
        print("  ✅ A1–A6 全通过")
    else:
        by = {}
        for b in bad:
            by.setdefault(b[:2], []).append(b)
        for k in sorted(by):
            print(f"  ❌ {k} 共 {len(by[k])} 处")
            for b in by[k][:5]:
                print(f"       {b[3:]}")
    if a.text_only:
        return 1 if bad else 0
    if bad:
        print("\n文案未过,不渲染音频反查 —— 先修文案。")
        return 1

    print("\n【B 音频层】whisper 反查中…")
    vo = D / f"{a.session}_vo.mp3"
    if not vo.exists():
        print(f"  ✗ 找不到 {vo.name}")
        return 1
    model = hw.resolve_model(None)
    heard = transcribe(vo, model)
    ref = words(" ".join(p.get("text") or "" for p in atoms))
    hyp = words(heard)
    w = wer(ref, hyp)
    print(f"  B1 WER {w:.1%}   (剧本 {len(ref)} 词 / 听到 {len(hyp)} 词)")

    hay = " " + " ".join(hyp) + " "
    missing = []
    for p in atoms:
        sw = words(p.get("text") or "")
        if not sw:
            continue
        if " " + " ".join(sw) + " " in hay:
            continue
        sm = difflib.SequenceMatcher(a=sw, b=hyp, autojunk=False)
        blocks = sm.get_matching_blocks()
        best = max(blocks, key=lambda b: b.size, default=None)
        cov = (best.size / len(sw)) if best else 0.0
        if cov < 0.8:
            # 附上音频里最接近的那段 —— 只报「漏了」而不报「听到的是什么」,
            # 没法判断是真漏、还是转写差异导致的误报。
            ctx = " ".join(hyp[max(0, best.b - 3): best.b + len(sw) + 3]) if best else ""
            missing.append((p, cov, ctx))
    # 「这句在音频里找不到」是个强断言,报出来之前先核实**那条原子本身**。
    # 整轨按语音段切开转写时,段边界可能把一句话劈成两半,于是词序列不连续 ——
    # 但原子文件单独转写是对的,节目其实没问题。只有原子自己的音频都对不上,
    # 才是真的漏。(实测:1.2s 的 tail_cut 原子最容易触发这种误报)
    real, artifact = [], []
    if missing:
        with tempfile.TemporaryDirectory() as td:
            d2 = Path(td)
            ws = []
            for i, (p, _, _) in enumerate(missing):
                wv = d2 / f"{i:03d}.wav"
                q = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-i", p["path"],
                     "-ar", "16000", "-ac", "1", str(wv)],
                    capture_output=True, text=True)
                if q.returncode == 0 and wv.exists():
                    ws.append((i, wv))
            if ws:
                subprocess.run(
                    ["whisper-cli", "-m", str(model), "-nt", "-l", "en", "-otxt"]
                    + [str(wv) for _, wv in ws], capture_output=True, text=True)
            heard_one = {}
            for i, wv in ws:
                t = Path(str(wv) + ".txt")
                heard_one[i] = (" ".join(t.read_text(errors="ignore").split())
                                if t.exists() else "")
        for i, (p, cov, ctx) in enumerate(missing):
            h = heard_one.get(i, "")
            if words(h) == words(p.get("text") or ""):
                artifact.append((p, cov, ctx))
            else:
                real.append((p, cov, ctx, h))
    print(f"  B2 漏句 {len(real)}   (另有 {len(artifact)} 条经复核为分段误报)")
    for p, cov, ctx, h in real[:8]:
        print(f"       ✗ 剧本 「{str(p.get('text'))[:52]}」")
        print(f"         原子 「{h[:52]}」")
        print(f"         整轨 「{ctx[:52]}」  (最长匹配 {cov:.0%})")
    for p, cov, ctx in artifact[:5]:
        print(f"       ~ 误报 「{str(p.get('text'))[:52]}」  原子音频核对无误")
    missing = real

    sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    extra = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace") and j2 - j1 >= 3:
            extra.append(" ".join(hyp[j1:j2]))
    print(f"  B3 音频多出剧本没有的片段 {len(extra)}")
    for e in extra[:6]:
        print(f"       + {e[:60]}")

    ok = w <= WER_LIMIT and not missing and not extra
    print(f"\n{'✅ 全部通过 —— 可冻结' if ok else '❌ 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
