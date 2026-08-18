#!/usr/bin/env python3
# coding: utf-8
"""独立内容检测门 —— 只看成片音频,严格放行(2026-08-17 用户令)。

「独立」的含义:本门对**渲染出的 VO 成品**重新转写,检查听者实际听到的
内容;出片器的编排计划、选段逻辑、任何中间产物都不参与判断。它从
session.json 拿的只有两样:音频路径,和「本期主题经文」这一句声明
(声明也要被音频验证,而不是反过来)。

六项检查,全部达标才放行;任何一项不过,本期作废重排:
  G1 块完整   每个发声块(≥6s 静默为界)首字成头、尾有交代 —— 听得懂在说什么
  G2 稀疏     块间距全部 ≥10s 且中位 ≥16s —— 语音必须疏,呼吸感是产品本体
  G3 语音占比 VO 区 ≤60%、全片 ≤40% —— 节制表达,音乐与静默是主角
  G4 一处经文 音频中听到的经文引用全部属于本期声明的主题集,且主经文确被读出
  G5 无混乱   无重复块、无孤词块、块数在节制范围(5–16)
  G6 语速     全局 0.5–2.8 词/秒 —— 睡眠向朗读的合理区间

放行时,本门的转写(真实成品时间戳)回填 session.json 的 plan 并产出
英文 SRT —— 字幕与视频文字直接来自成片音频,音画错位从结构上不可能。

  KMP_DUPLICATE_LIB_OK=TRUE ./.venv/bin/python scripts/sg/content_gate.py \\
      --session ~/Studio/Workspace/outputs/sg/sessions/sg_mol_001
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_session import build_srt                      # noqa: E402
from harvest_whisper import resolve_model, span_phrases, to_wav16k  # noqa: E402
from molecule_quality import perspective, text_complete   # noqa: E402
from sg_media import probe_duration                       # noqa: E402

WORK = Path.home() / "Studio/Workspace/temp/sg_content_gate"
ROOT_CFG = Path(__file__).resolve().parents[2] / "config"

# ── 门槛 ──
# 听感分块阈值 10s 的依据:母带内部停顿实测最长 7.9s(1914 个停顿中
# ≥10s 者为零),而出片器块间距下限 16s —— 10s 恰在两者之间,合并型
# 分子(内含 6–8s 长停)不会被误拆,出片间距必然成为块界。
BLOCK_SPLIT = 10.0
MIN_BLOCK_GAP = 14.0     # 任何两块之间至少 14s(设计值 16s 留 2s 容差)
MIN_MEDIAN_GAP = 20.0    # 块间距中位数至少 20s
MAX_SPEECH_RATIO_VO = 0.60
MAX_SPEECH_RATIO_ALL = 0.40
BLOCKS_MIN, BLOCKS_MAX = 5, 16
RATE_MIN, RATE_MAX = 0.5, 2.8

BOOKS = ("Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
         "Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|"
         "Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|"
         "Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|"
         "Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|"
         "Romans|Corinthians|Galatians|Ephesians|Philippians|Colossians|"
         "Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|"
         "Revelation")
REF_RE = re.compile(rf"\b({BOOKS})\b", re.IGNORECASE)


def norm_book(s: str) -> str:
    return s.lower().rstrip("s") if s.lower().startswith("psalm") else s.lower()


def group_blocks(utts: list[tuple[float, float, str]]
                 ) -> list[dict]:
    """转写条目按 ≥BLOCK_SPLIT 的间隙聚成「听感块」。"""
    blocks: list[dict] = []
    for t0, t1, tx in utts:
        if blocks and t0 - blocks[-1]["end"] < BLOCK_SPLIT:
            b = blocks[-1]
            b["end"] = t1
            b["speech"] += t1 - t0
            b["text"] += " " + tx
            b["utts"].append((t0, t1, tx))
        else:
            blocks.append({"start": t0, "end": t1, "speech": t1 - t0,
                           "text": tx, "utts": [(t0, t1, tx)]})
    return blocks


def _norm_words(t: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", t.lower()).split()


def _tok_close(a: str, b: str) -> bool:
    """两个词是否算「同一个词的 ASR 噪声」:前缀重合 ≥5 或同为数字。

    whisper/whisperer、25/23(引用数字)—— 音频无损,是转写拼写噪声。
    """
    if a == b:
        return True
    if a.isdigit() and b.isdigit():
        return True
    n = min(len(a), len(b))
    return n >= 5 and a[:5] == b[:5]


def _arbitrate(mol_path: str, model, heard: str, lib: str) -> str:
    """三方仲裁:对该分子单独的 mp3 做第三次独立转写,谁与它一致谁是真相。

    返回 'render_bad'(成片真变形,判死刑) / 'library_bad'(库文本失真,
    成片无辜,分子进修复队列) / 'unclear'(裁不动,从严判死刑)。
    """
    import difflib
    p = Path(mol_path)
    if not p.exists():
        return "unclear"
    wav = to_wav16k(p, WORK / (p.stem + "_arb.wav"))
    from harvest_whisper import run as _hrun, WHISPER_CLI
    _hrun([WHISPER_CLI, "-m", str(model), "-nt", "-l", "en", "-otxt", str(wav)])
    txt = Path(str(wav) + ".txt")
    clip = " ".join(txt.read_text(errors="ignore").split()) if txt.exists() else ""
    if not clip:
        return "unclear"
    s_heard = difflib.SequenceMatcher(None, _norm_words(heard),
                                      _norm_words(clip)).ratio()
    s_lib = difflib.SequenceMatcher(None, _norm_words(lib),
                                    _norm_words(clip)).ratio()
    if s_heard - s_lib > 0.05:
        return "library_bad"
    if s_lib - s_heard > 0.05:
        return "render_bad"
    return "unclear"


def judge(blocks: list[dict], vo_ends: float, total: float,
          claimed: list[str], primary: str,
          lib_texts: list[tuple[str, str, str]] | None = None,
          model=None, mix_path=None, mol_plan=None,
          atempo: float = 1.0) -> dict:
    checks: dict[str, dict] = {}
    judge.model = model
    judge.mix_path = mix_path
    judge.mol_plan = mol_plan
    judge.atempo = atempo

    def _occupancy_ok(i: int) -> bool:
        """成片占位与库时长(经 atempo 折算)一致 = 音频物理完整。

        拼接渲染在结构上不可能丢词 —— 占位一致时,任何「不完整」都是
        转写层在成片语境下吞了软尾气声词(2026-08-17 ps16 实测:库尾
        「…before the morning comes.」完整,成片转写却听丢)。
        """
        if not (judge.mol_plan and lib_texts and i < len(lib_texts)
                and i < len(judge.mol_plan)
                and len(blocks) == len(lib_texts)):
            return False
        p = judge.mol_plan[i]
        mdur = lib_texts[i][3]
        if p.get("vo_start_sec") is None or not mdur:
            return False
        occ = p["vo_end_sec"] - p["vo_start_sec"]
        return abs(occ - mdur / max(0.5, judge.atempo)) <= 0.3

    bad, noise = [], []
    for i, b in enumerate(blocks):
        why = text_complete(b["text"])
        if not why:
            continue
        if lib_texts and i < len(lib_texts) \
                and text_complete(lib_texts[i][0]) is None \
                and _occupancy_ok(i):
            noise.append(f"块{i} 转写噪声容忍[{why}](库完整+占位一致)")
            continue
        bad.append((i, why))
    checks["G1_blocks_complete"] = {
        "pass": not bad,
        "detail": [f"块{i}: [{why}] 「{blocks[i]['text'][:60]}」"
                   for i, why in bad] + noise}

    gaps = [round(blocks[i + 1]["start"] - blocks[i]["end"], 1)
            for i in range(len(blocks) - 1)]
    med = sorted(gaps)[len(gaps) // 2] if gaps else 0.0
    checks["G2_sparse"] = {
        "pass": bool(gaps) and min(gaps) >= MIN_BLOCK_GAP and med >= MIN_MEDIAN_GAP,
        "detail": f"块间距 min={min(gaps) if gaps else 0}s 中位={med}s "
                  f"(门槛 ≥{MIN_BLOCK_GAP}/{MIN_MEDIAN_GAP})"}

    speech = sum(b["speech"] for b in blocks)
    r_vo = speech / vo_ends if vo_ends else 1.0
    r_all = speech / total if total else 1.0
    checks["G3_speech_ratio"] = {
        "pass": r_vo <= MAX_SPEECH_RATIO_VO and r_all <= MAX_SPEECH_RATIO_ALL,
        "detail": f"VO 区 {r_vo:.0%}(≤{MAX_SPEECH_RATIO_VO:.0%}) · "
                  f"全片 {r_all:.0%}(≤{MAX_SPEECH_RATIO_ALL:.0%})"}

    all_text = " ".join(b["text"] for b in blocks)
    heard = {norm_book(m.group(1)) for m in REF_RE.finditer(all_text)}
    # claimed 是库级实测的书卷表(采集时对母带全文量出),不是编排的产物;
    # 门用它当白名单,但主经文仍必须在音频里真实读出。
    allowed = {norm_book(b) for b in claimed} if claimed else set()
    prim_books = {norm_book(m.group(1)) for m in REF_RE.finditer(primary)}
    foreign = heard - allowed
    checks["G4_one_scripture"] = {
        "pass": not foreign and bool(heard & prim_books),
        "detail": f"听到 {sorted(heard)} · 声明 {sorted(allowed)} · "
                  f"越界 {sorted(foreign) or '无'} · 主经文读出 {bool(heard & prim_books)}"}

    norm = [re.sub(r"\W+", " ", b["text"].lower()).strip() for b in blocks]
    dups = [t[:50] for i, t in enumerate(norm) if t in norm[:i]]
    orphans = [b["text"] for b in blocks
               if len(b["text"].split()) < 2
               and "amen" not in b["text"].lower()]
    checks["G5_no_confusion"] = {
        "pass": not dups and not orphans and BLOCKS_MIN <= len(blocks) <= BLOCKS_MAX,
        "detail": f"块数 {len(blocks)}({BLOCKS_MIN}–{BLOCKS_MAX}) · "
                  f"重复 {dups or '无'} · 孤词 {orphans or '无'}"}

    words = len(all_text.split())
    rate = words / speech if speech else 0.0
    checks["G6_pace"] = {
        "pass": RATE_MIN <= rate <= RATE_MAX,
        "detail": f"{rate:.2f} 词/秒({RATE_MIN}–{RATE_MAX})"}

    # G7 逐词对账:成片听到的每一块,与库内该段**应该说的词**逐词比对。
    # 库文本是采集时对母带的独立转写(固定事实,不是编排的产物);两次
    # whisper 的噪声用相似度容差吸收,但**首词/尾词缺失零容忍** ——
    # 那正是「词没读完」的直接证据。
    import difflib
    if lib_texts is not None:
        probs: list[str] = []
        suspects: list[str] = []   # 库文本失真的分子(修复队列,不判成片死刑)
        if len(blocks) != len(lib_texts):
            probs.append(f"块数 {len(blocks)} ≠ 选段数 {len(lib_texts)}(成片变形)")
        else:
            for i, (b, (ref, mid, mpath, mdur)) in enumerate(zip(blocks, lib_texts)):
                hw, rw = _norm_words(b["text"]), _norm_words(ref)
                if not rw:
                    continue
                sim = difflib.SequenceMatcher(None, hw, rw).ratio()
                head_bad = hw and rw and not _tok_close(hw[0], rw[0]) \
                    and rw[0] not in hw[:3]
                tail_bad = hw and rw and not _tok_close(hw[-1], rw[-1]) \
                    and rw[-1] not in hw[-3:]
                if sim >= 0.82 and not head_bad and not tail_bad:
                    continue
                # 争议 → 三方仲裁(对该分子 mp3 独立转写)
                verdict = _arbitrate(mpath, judge.model, b["text"], ref)
                if verdict == "library_bad":
                    suspects.append(mid)
                    continue
                # 时长证据:拼接渲染在结构上不可能丢词。分子在成品轨上的
                # 占位与库内时长(经 atempo 折算)一致 → 音频物理完整,分歧
                # 只是转写层噪声(软尾气声词两次转写各执一词),分子进文本
                # 复核队列,不判成片死刑。占位对不上才是真变形。
                occ = exp = None
                if judge.mol_plan and i < len(judge.mol_plan):
                    p = judge.mol_plan[i]
                    if p.get("vo_start_sec") is not None:
                        occ = p["vo_end_sec"] - p["vo_start_sec"]
                        exp = (mdur or 0) / max(0.5, judge.atempo)
                if occ is not None and exp and abs(occ - exp) <= 0.3:
                    suspects.append(mid)
                    continue
                why = (f"相似度 {sim:.2f}" if sim < 0.82 else
                       f"{'首' if head_bad else '尾'}词缺失")
                probs.append(f"块{i} {why}(仲裁:{verdict},占位 {occ} vs {exp})"
                             f"应「…{' '.join(rw[-4:])}」闻「…{' '.join(hw[-4:])}」")
        checks["G7_words_intact"] = {
            "pass": not probs,
            "detail": (probs or [f"{len(blocks)} 块逐词对账全符"])
            + ([f"库文本失真 {len(suspects)} 条(进修复队列,不判成片): "
                + ",".join(suspects)] if suspects else [])}
        if suspects:
            q = ROOT_CFG / "sg_molecule_repair_queue.json"
            old = json.loads(q.read_text()) if q.exists() else []
            q.write_text(json.dumps(sorted(set(old) | set(suspects)),
                                    ensure_ascii=False, indent=1))

    # G8 视角轨迹:Y(对你说)→W(我们祷告)是自然的仪式弧线;来回横跳
    # (Y W Y / W Y W)才是代词混乱。中性块(纯祈使)沿用前一视角。
    traj, cur = [], None
    for b in blocks:
        p = perspective(b["text"])
        if p != "N":
            cur = p
        traj.append(cur or "N")
    flips = sum(1 for i in range(1, len(traj)) if traj[i] != traj[i - 1])
    aba = any(traj[i] != traj[i + 1] and traj[i] == traj[i + 2]
              for i in range(len(traj) - 2))
    checks["G8_perspective"] = {
        "pass": flips <= 3 and not aba,
        "detail": f"轨迹 {''.join(traj)} · 切换 {flips} 次(≤3) · 横跳 {'有' if aba else '无'}"}

    # G9 停顿均匀:间距允许随进度渐长(入睡曲线),不允许突变 ——
    # 相邻间距之比 ≤2.6(设计随机域的最坏值 ~2.25 留余量)。
    gaps2 = [blocks[i + 1]["start"] - blocks[i]["end"]
             for i in range(len(blocks) - 1)]
    jumps = [f"{gaps2[i]:.0f}s→{gaps2[i+1]:.0f}s"
             for i in range(len(gaps2) - 1)
             if max(gaps2[i], gaps2[i + 1]) / max(0.1, min(gaps2[i], gaps2[i + 1])) > 2.6]
    checks["G9_gap_even"] = {
        "pass": not jumps,
        "detail": jumps or f"相邻间距比全部 ≤2.6({len(gaps2)} 个间距)"}

    # G11 礼仪完整(2026-08-18 神职标准审读):
    #  ① 末块必须有正式收尾式(Amen / in the name of Jesus / 三一颂)——
    #     john10 实测整期祷告没有收尾,神职听众必然察觉
    #  ② 三一颂读了「奉父的名」就必须补全子与圣灵 —— 残缺的三一颂
    #     比没有更糟
    #  ③ 字幕层(canon 后)不得残留数字胡话引用(「Psalm 1, 2, 1…」)
    fixed_all = canon_text(all_text).lower()
    fixed_last = canon_text(blocks[-1]["text"]).lower() if blocks else ""
    formula = re.compile(
        r"\bamen\b|in the name of jesus|in jesus'? name|name of the father")
    trin_ok = True
    if "in the name of the father" in fixed_all:
        trin_ok = ("son" in fixed_all and "holy spirit" in fixed_all)
    babble = re.findall(rf"\b({BOOKS})\s+\d,\s*\d", canon_text(all_text))
    checks["G11_liturgy"] = {
        "pass": bool(formula.search(fixed_last)) and trin_ok and not babble,
        "detail": f"收尾式 {'有' if formula.search(fixed_last) else '❌无'} · "
                  f"三一颂完整 {trin_ok} · 引用胡话 {babble or '无'} · "
                  f"末块「…{canon_text(blocks[-1]['text'])[-46:] if blocks else ''}」"}

    # G10 响度:基线 = 已公开 Ep1 实测 -28.0 LUFS / TP -6.6(2026-08-17)。
    # 深夜连听,期与期必须一致;门自己重测成片,不信出片器自报的数。
    if judge.mix_path is not None:
        from sg_media import measure_loudness
        lo = measure_loudness(judge.mix_path)
        if lo is None:
            checks["G10_loudness"] = {"pass": False, "detail": "响度测不出"}
        else:
            checks["G10_loudness"] = {
                "pass": -29.5 <= lo["I"] <= -26.5 and lo["TP"] <= -2.0,
                "detail": f"I={lo['I']:.1f} LUFS(-29.5…-26.5) "
                          f"TP={lo['TP']:.1f}(≤-2.0) LRA={lo['LRA']:.1f}"}

    return {"pass": all(c["pass"] for c in checks.values()), "checks": checks,
            "blocks": len(blocks), "speech_sec": round(speech, 1),
            "judged_at": datetime.now(timezone.utc).isoformat()}


# 规范表 —— 只修**显示文本**(字幕/视频文字),判定用原始转写。
# 2026-08-18 神职标准审读:逐条与分子库文本(独立转写)核验,确认音频
# 全对、是成片语境转写听差之后才入表 —— 每条都有库内证据。
# 最恶劣的一条:三一颂「and of the Son」被听成「End of the Sun」,
# 字幕若带着太阳崇拜既视感上片,神学上是事故。
CANON = [
    (re.compile(r"\bSleep\s+and\s+Grace\b", re.IGNORECASE), "Sleep in Grace"),
    (re.compile(r"\bSleeping\s+Grace\b"), "Sleep in Grace"),
    (re.compile(r"\bEnd of the [Ss]un\b"), "and of the Son"),
    (re.compile(r"\bI have said the Lord\b"), "I have set the Lord"),
    (re.compile(r"\bReplace them in your hands\b"), "We place them in your hands"),
    (re.compile(r"\bA present stronger\b"), "A presence stronger"),
    (re.compile(r"\bNot enjoy\b"), "Not in joy"),
    (re.compile(r"\ba gentle whisperer\b"), "a gentle whisper"),
    (re.compile(r"\bHis eyes remained open\b"), "His eyes remain open"),
]

# 经文引用的读法转写五花八门(「Psalm 1, 2, 1, 1 and 2」「John 14, 27」
# 「Philippians 4-7」),字幕必须还原为标准章节格式 —— 神职读者对引用
# 格式的容忍度为零。先特例后通例,通例只在书卷名后生效。
REF_SPECIAL = [
    (re.compile(r"\bPsalm 1, 2, 1, 1,? and 2\b"), "Psalm 121:1-2"),
    (re.compile(r"\bPhilippians 4-7\b"), "Philippians 4:7"),
    (re.compile(r"\bPsalm 23, 2 and 3\b"), "Psalm 23:2-3"),
    (re.compile(r"\bDeuteronomy 33, 27\b"), "Deuteronomy 33:27"),
]
REF_GENERIC = re.compile(rf"\b({BOOKS})\s+(\d{{1,3}})\s*[.,]?\s+?(\d{{1,3}})\b")
REF_DOT = re.compile(rf"\b({BOOKS})\s+(\d{{1,3}})\s*[.,]\s*(\d{{1,3}})\b")


def canon_text(t: str) -> str:
    for pat, rep in CANON:
        t = pat.sub(rep, t)
    for pat, rep in REF_SPECIAL:
        t = pat.sub(rep, t)
    t = REF_DOT.sub(lambda m: f"{m.group(1)} {m.group(2)}:{m.group(3)}", t)
    t = REF_GENERIC.sub(lambda m: f"{m.group(1)} {m.group(2)}:{m.group(3)}", t)
    return t


def _merge_utts(utts: list[tuple[float, float, str]]
                ) -> list[tuple[float, float, str]]:
    """块内近邻转写条目并成整句字幕 —— 2026-08-17 人耳审听:
    「For you alone, Lord. / make me dwell in safety.」被拆成两条,
    标点也断错。并句只动标点与换行,一个词都不改(字幕迁就音频红线)。
    """
    out: list[tuple[float, float, str]] = []
    for t0, t1, tx in utts:
        if out:
            p0, p1, ptx = out[-1]
            joined = f"{ptx} {tx}"
            if t0 - p1 <= 1.5 and len(joined.split()) <= 16:
                if ptx.rstrip().endswith(".") and tx[:1].islower():
                    joined = f"{ptx.rstrip().rstrip('.')}, {tx}"
                out[-1] = (p0, t1, joined)
                continue
        out.append((t0, t1, tx))
    return out


def utterance_plan(blocks: list[dict]) -> list[dict]:
    """转写条目 → 渲染器/字幕用的 plan(真实成品时间戳)。

    source_sequence_index 的连号规则复用 build_srt 的续句判定:块内间隙
    ≤2.5s 视为同句被停顿切开(小写续排),更大间隙或跨块则断号。
    """
    plan: list[dict] = []
    seq = 0
    for bi, b in enumerate(blocks):
        prev_end = None
        for t0, t1, tx in _merge_utts(b["utts"]):
            seq += 1 if (prev_end is not None and t0 - prev_end <= 2.5) else 10
            plan.append({
                "slot": f"BLOCK_{bi:02d}", "type": "atom",
                "id": f"utt_{len(plan):03d}", "role": "molecule",
                "text": canon_text(tx),
                "vo_start_sec": round(t0, 3), "vo_end_sec": round(t1, 3),
                "start_sec": round(t0, 3), "end_sec": round(t1, 3),
                "duration_sec": round(t1 - t0, 3),
                "pad_after_sec": 0.0,
                "source_master": "content_gate_transcript",
                "source_sequence_index": seq,
            })
            prev_end = t1
    return plan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=Path, required=True)
    ap.add_argument("--report-only", action="store_true",
                    help="只判不写(不回填 plan/不出 SRT)")
    a = ap.parse_args()
    sdir = a.session.expanduser()
    eid = sdir.name
    meta_path = sdir / f"{eid}_session.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    vo = Path(meta["paths"]["vo"])
    claimed = (meta.get("scripture_books_allowed")
               or [m.group(1) for ref in (meta.get("scriptures") or [])
                   for m in [REF_RE.search(ref)] if m])
    primary = meta.get("primary_scripture") or ""

    WORK.mkdir(parents=True, exist_ok=True)
    model = resolve_model(None)
    wav = to_wav16k(vo, WORK / f"{eid}_vo.wav")
    utts = span_phrases(wav, model, WORK, min_sil=0.8, pad=0.12,
                        min_speech=0.4)
    total = meta.get("total_duration_sec") or probe_duration(vo) or 0.0
    vo_ends = meta.get("vo_ends_sec") or total
    blocks = group_blocks(utts)
    # G7 的对账基准:库内(采集时独立转写的)各选段文本,按选段顺序。
    lib_texts = None
    mol_ids = meta.get("molecule_ids")
    if mol_ids:
        man = Path.home() / "Studio/Library/sg/molecules/manifest.json"
        byid = {m["id"]: m
                for m in json.loads(man.read_text())["molecules"]}
        lib_texts = [(byid.get(i, {}).get("text", ""), i,
                      byid.get(i, {}).get("path", ""),
                      byid.get(i, {}).get("duration_sec")) for i in mol_ids]
    mix = meta.get("paths", {}).get("final_mix")
    mol_plan = [p for p in (meta.get("molecule_plan") or meta.get("plan") or [])
                if p.get("type") == "atom"]
    verdict = judge(blocks, vo_ends, total, claimed, primary, lib_texts,
                    model=model, mix_path=Path(mix) if mix else None,
                    mol_plan=mol_plan, atempo=float(meta.get("vo_atempo") or 1.0))

    print(f"═══ 内容门 · {eid} ═══")
    for name, c in verdict["checks"].items():
        mark = "✅" if c["pass"] else "❌"
        print(f" {mark} {name}")
        det = c["detail"]
        for line in (det if isinstance(det, list) else [det]):
            print(f"     {line}")

    meta["content_gate"] = verdict
    if verdict["pass"] and not a.report_only:
        plan = utterance_plan(blocks)
        meta["molecule_plan"] = meta.get("plan")
        meta["plan"] = plan
        srt = sdir / f"{eid}.srt"
        srt.write_text(build_srt(plan), encoding="utf-8")
        meta["paths"]["srt"] = str(srt)
        print(f"✅ 放行:plan 回填 {len(plan)} 条转写 · 字幕 {srt.name}")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    if not verdict["pass"]:
        print("⛔ 不放行 —— 本期作废,换种子重排")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
