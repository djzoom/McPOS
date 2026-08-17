#!/usr/bin/env python3
# coding: utf-8
"""分子(段落级语音块)的唯一权威判据 —— 采集、盘点、出片共用这一份。

「分子」是 2026-08-17 用户令的产物:原子(句级)拼接的成片太碎太密,
单句常不知所云。分子按母带的**段落停顿**整块保留,段内是 Locke 原生
连续朗读 —— 句间距、语气、呼吸全是录音时的真实节奏,拼接只决定
段落顺序与段落间距,不再有句级拼接的一切失败模式(结巴/悬空/重叠)。

判据依据(全部来自 2026-08-17 对 13 支母带 1914 个停顿的实测分布):
  · 0.5–2.0s(826 个)= 句内/句间停顿,段内保留,不切
  · 2.0–6.0s(720 个)= 冥想式句间长停,段内保留,不切
  · 6.0–10.0s(211 个)= 独立族群,是录音时刻意的分段呼吸 → 段界
  · 10 支主题母带按 6.0s 切:每支 20–25 段,中位段长 ~34s —— 完整意义块
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# ── 经文书卷识别(库与内容门共用这一份;两处各写一份迟早漂移)──
# 2026-08-17 首次实弹:john10 母带朗读中引用了 Deuteronomy 33:27,
# 文件名推导的声明里没有 → 内容门 G4 拦下。教训:母带实际引用什么
# 只能靠转写实测,声明是**库级事实**(采集时量),不是文件名的猜测。
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


def books_heard(text: str) -> list[str]:
    """文本中听到的经文书卷(去重排序)。"""
    return sorted({norm_book(m.group(1)) for m in REF_RE.finditer(text or "")})

# ── 切割(采集端用,依据见模块头)──────────────────────────────
PARA_SILENCE = 6.0      # 段界:静音 ≥6s(实测 6–10s 族群独立存在,n=211)
SPAN_PAD = 0.35         # 边界向静音内各让 0.35s 软肩(切点本就在长静默中央)
MIN_SPEECH = 1.2        # 语音段最短 1.2s 才成段(“Amen.”慢读约 1.5–2s)

# ── 分子准入 ─────────────────────────────────────────────
MIN_DUR = 2.5           # 短于此不成段(容纳独立的 “Amen.” 收束)
MAX_DUR = 120.0         # 长于此说明母带没有段落结构(如 G1/G2 逐句清单),不入库
MIN_RATE = 0.25         # 词/秒下限:再慢的段落也不该低于此 —— 低于即转写脱靶
MAX_RATE = 3.2          # 上限:睡眠向朗读不可能这么快 —— 高于即转写或切割出错
EDGE_WIN = 0.15         # 边缘检测窗(秒):首尾此窗内应近乎无声(切点在长静默里)
EDGE_MAX_DB = -30.0     # 边缘窗内最大电平上限;超过=切进了语音,判废
TERMINALS = ('.', '!', '?', '"', '”', '’')   # 完整段落的合法收尾

# 以下判据的依据(2026-08-17 首轮采集 27 条拒收逐条复核):
#  · 8 条 head_cut 全部 t_start=0.00 —— 母带真实开头,不是切伤。台标开场
#    第四次差点被处决 → t_start 在软肩内的分子豁免头部电平检测。
#  · 16 条 tail_incomplete 实为三类:whisper 掉标点(「…restores my soul」),
#    经文引用收尾(「Psalm 4:8」数字尾),真悬空(「…will not leave the」)。
#    真悬空是朗读者把一句话跨过了 ≥6s 长停 —— 正确处理是与下一段**合并**
#    (合并后仍是母带连续原声),不是拒收。
DANGLING_TAIL_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at",
    "with", "for", "as", "so", "if", "than", "that", "into", "onto",
    "is", "are", "was", "were", "be", "will", "shall", "would", "may",
    "let", "even", "now,", "he", "she", "they", "we", "i", "his", "her",
    "your", "my", "our", "its",
}


def tail_state(text: str) -> str:
    """段落收尾三态:complete / dangling(该并入下一段) / empty。"""
    t = text.strip()
    if not t:
        return "empty"
    if t.endswith(TERMINALS) or t[-1].isdigit():
        # 数字收尾 = 朗读出的经文引用(「Psalm 4:8」),意义完整
        tail_ok = True
    elif t.endswith(","):
        return "dangling"               # 逗号收尾 = 句子跨长停,后半在下一段
    else:
        last = t.split()[-1].lower().rstrip(",;:")
        tail_ok = last not in DANGLING_TAIL_WORDS   # 实词收尾多半是 whisper 掉标点
    if not tail_ok:
        return "dangling"
    # 「…for stillness. you」:终止符之后拖一个孤词 = 下一句刚起头就被切 → 悬空
    if "." in t:
        after = t.rsplit(".", 1)[-1].strip()
        if after and len(after.split()) < 3 and not after.endswith(TERMINALS) \
                and not after[-1:].isdigit():
            return "dangling"
    return "complete"


# 首词属于此表 + 小写开头,双证齐全才判「切进上一段」。单凭小写不拒:
# whisper 的大小写是随机的(2026-08-17 连排实测:同一分子库内转写大写、
# 成片转写小写),单一不可靠证据不定罪 —— 与 tail_truncated 双证同理。
CONTINUATION_HEAD_WORDS = {
    "and", "but", "or", "nor", "so", "for", "yet", "because", "which",
    "who", "whom", "whose", "that", "of", "in", "on", "at", "to", "with",
    "into", "onto", "than", "as", "if", "while", "when", "where",
}


def text_complete(text: str) -> str | None:
    """段落文本必须首字成头、尾有交代 —— 不完整就说不清要表达什么。"""
    t = text.strip()
    if not t:
        return "empty_text"
    head = t[0]
    if not (head.isupper() or head.isdigit() or head in ('"', '“', '‘')):
        first = t.split()[0].lower().strip(",.;")
        if first in CONTINUATION_HEAD_WORDS:
            # 第三重判别(2026-08-17 deut31 实测):排比修辞常以从属句
            # 开头(「When X. When Y. God is still near.」),主句在块内
            # 落地,意义完整 —— 只有短块(<12 词)或全块无内部终止标点
            # (主句不在块内)才定罪。判据只看本块文本,不偷看库。
            words = len(t.split())
            has_internal_terminal = any(ch in t[:-1] for ch in ".!?")
            if words < 12 or not has_internal_terminal:
                return "head_incomplete"
    if tail_state(t) == "dangling":
        return "tail_dangling"
    return None


def edge_peak_db(path: Path, head: bool) -> float | None:
    """量测首/尾 EDGE_WIN 秒窗内的峰值电平(dBFS)。探测失败返 None,不猜。"""
    dur_r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        dur = float(dur_r.stdout.strip())
    except ValueError:
        return None
    ss = 0.0 if head else max(0.0, dur - EDGE_WIN)
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", f"{ss:.3f}", "-t", f"{EDGE_WIN:.3f}",
         "-i", str(path), "-af", "astats=metadata=1:measure_perchannel=none",
         "-f", "null", "-"], capture_output=True, text=True)
    import re
    m = re.findall(r"Peak level dB:\s*(-?[\d.]+|-inf)", r.stderr)
    if not m:
        return None
    return float("-999" if m[-1] == "-inf" else m[-1])


def reject_reason(mol: dict) -> str | None:
    """分子能否入库/上场的唯一裁决。None = 通过。"""
    dur = mol.get("duration_sec") or 0
    if dur < MIN_DUR:
        return "too_short"
    if dur > MAX_DUR:
        return "no_paragraph_structure"
    words = len((mol.get("text") or "").split())
    rate = words / dur if dur else 0
    if rate < MIN_RATE:
        return "rate_low_transcript_miss"
    if rate > MAX_RATE:
        return "rate_high_cut_error"
    t = text_complete(mol.get("text") or "")
    if t:
        return t
    at_master_head = (mol.get("t_start") or 0) <= SPAN_PAD + 0.05
    for k, reason, waived in (
            ("edge_head_db", "head_cut_into_speech", at_master_head),
            ("edge_tail_db", "tail_cut_into_speech", False)):
        if waived:
            continue        # 母带 0 秒即开口:没有更早的音频可被切掉
        v = mol.get(k)
        if v is None:
            return f"{k}_unmeasured"    # 量不出就不放行 —— 绝不静默兜底
        if v > EDGE_MAX_DB:
            return reason
    return None
