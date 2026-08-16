#!/usr/bin/env python3
# coding: utf-8
"""Precise speech-atom harvest using local whisper.cpp (word timestamps).

Uses:
  whisper-cli + ggml-large-v3-turbo (Metal on Apple Silicon)

Pipeline:
  master mp3 → 16k mono wav → whisper JSON (word-level) →
  group into phrase atoms by punctuation + pause gaps →
  export mp3 + json (with text!) → manifest

Usage:
  KMP_DUPLICATE_LIB_OK=TRUE python3 scripts/sg/harvest_whisper.py --clean
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LOCKE = Path.home() / "Studio/Library/sg/assets/vo/Locke"
ATOMS = Path.home() / "Studio/Library/sg/atoms"
WHISPER_CLI = "whisper-cli"
DEFAULT_MODEL = Path.home().parents[0]  # dummy
MODEL_CANDIDATES = [
    Path("/Users/z/Projects/whisper.cpp/models/ggml-large-v3-turbo.bin"),
    Path.home() / "Projects/whisper.cpp/models/ggml-large-v3-turbo.bin",
    Path("/opt/homebrew/Cellar/whisper-cpp/1.8.6/share/whisper-cpp/for-tests-ggml-tiny.bin"),
]

ROLE_DIRS = [
    "open", "breath", "safety", "release", "deepen",
    "scripture", "poetic", "bless", "close",
    # 2026-08-05 新增:331 条好内容原本全落在 misc,因为语法没有能装它们的槽。
    # 主题盘点说「悲伤/失丧 11 条 🔴」,但 misc 里躺着 "Lord, you know the loss
    # I carry." —— 内容一直都在,只是没槽位。这两个角色按 addressee 划分:
    "comfort",    # 旁白式安慰:you=听者,"You don't need to be strong."
    "petition",   # 祷告式倾诉/代求:you=上帝,"Hold the people I love tonight."
    "misc",
]

# text → role hints
TEXT_ROLE_RULES: list[tuple[str, list[str]]] = [
    (r"\bwelcome to sleep in grace\b", ["open", "brand"]),
    (r"\bwelcome\b", ["open"]),
    (r"\bbreathe\b|\binhale\b|\bexhale\b", ["breath"]),
    (r"\blet go\b|\brelease\b|\bcast\b|\banxi", ["release"]),
    (r"\bamen\b|\bgood night\b|\bsleep in grace\b|\bpeace be with you\b", ["close", "bless"]),
    (r"\bthe lord bless\b|\bgive you peace\b", ["bless", "close"]),
    (r"\bpsalm\b|\bmatthew\b|\bjohn\b|\bisaiah\b|\bphilippians\b|\bromans\b|\bproverbs\b|\blamentations\b|\bexodus\b|\bdeuteronomy\b|\bnehemiah\b|\bpeter\b|\bnumbers\b", ["scripture"]),
    # safety = 保护/看守/无危险的**语义场**,不只是 "do not fear" 三种说法。
    # 2026-08-05:G2 写了 45 句 safety,只认出 7 条,其余落进 poetic 兜底。
    (r"\bdo not (be )?(afraid|fear|anxious)\b|"
     r"\byou are (not alone|safe|held|kept|secure|guarded|watched)\b|\bwith you\b|"
     r"\bkeeps? you\b|\bkeeping you\b|\bwatch(es|ing)? over\b|\bwatching (this|you)\b|"
     r"\bnever (once )?(slumber|sleep)s?\b|\bno (harm|danger|evil)\b|\bsafe(ty|ly)?\b|"
     r"\bshelter\b|\brefuge\b|\bprotect\w*\b|\bhis hold\b|\bin his hand\b|"
     r"\bnothing can (reach|touch|harm|separate|undo)\b|\bguard(s|ed|ing)? (you|your)\b",
     ["safety"]),
    (r"\bdeeper\b|\bdrift\b|\bedge of sleep\b|\bsoft(er|ly)?\b|\bsink\b", ["deepen"]),
    # open = 到达/门槛/一天收束的语义场
    (r"\bcome in\b|\bthis hour\b|\bthe day is (over|done|complete|behind|finished)\b|"
     r"\blay(ing)? down (the|what) \w*\s?day\b|\bstep (out|into)\b|\bthreshold\b|"
     r"\bthis (is the|hour of)\b|\bcome as\b|\broom for you\b|\bthe lamp\b|"
     r"\bnothing more is required\b|\bthe evening\b|\bthe house is still\b",
     ["open"]),
    # poetic 必须是**正面**判定(明喻/意象),不能当兜底垃圾桶
    (r"\blike a\b|\bas a \w+ (does|would)\b|\briver\b|\bwings\b|\bshepherd\b|"
     r"\bpastures\b|\bwaters\b|\bfortress\b|\banchor\b|\bharbor\b|\blantern\b|"
     r"\btide\b|\bember\b", ["poetic"]),
]

SOURCE_THEME = [
    (r"welcome", ["open", "welcome", "brand"]),
    (r"deuteronomy|0906", ["scripture", "deuteronomy", "presence"]),
    (r"0908|surpasses|john.?14", ["scripture", "john14", "philippians", "peace"]),
    (r"still_speaking|god_is_still", ["scripture", "psalm121", "lamentations"]),
    (r"peace_beyond|philippians_4_6", ["scripture", "philippians", "peace", "release"]),
    (r"rest_secure", ["scripture", "psalm4", "isaiah41", "safety"]),
    (r"isaiah26", ["scripture", "isaiah26", "peace"]),
    (r"john10|psalm62", ["scripture", "john10", "psalm62"]),
    (r"psalm121_lamentations3_2025-09-02", ["scripture", "psalm121", "lamentations"]),
    (r"psalm16|matthew28|fall_asleep_in_god", ["scripture", "psalm16", "matthew28"]),
]


@dataclass
class Word:
    start: float  # sec
    end: float
    text: str


@dataclass
class Atom:
    id: str
    path: str
    source_master: str
    voice: str
    t_start: float
    t_end: float
    duration_sec: float
    role: str
    tags: list[str] = field(default_factory=list)
    text: str | None = None
    method: str = "whisper_cpp"
    created_at: str = ""


def run(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    e["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    if env:
        e.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=e)


from sg_media import probe_duration  # noqa: E402,F401  契约:测不出返回 None


def parse_ts(ts: str) -> float:
    """HH:MM:SS,mmm → seconds."""
    ts = ts.strip().replace(".", ",")
    if "," not in ts:
        parts = ts.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        return float(ts)
    hms, ms = ts.split(",")
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def resolve_model(path: Path | None) -> Path:
    if path and path.exists():
        return path
    for c in MODEL_CANDIDATES:
        if c.exists() and c.stat().st_size > 50_000_000:  # skip tiny test model
            return c
    for c in MODEL_CANDIDATES:
        if c.exists():
            return c
    raise FileNotFoundError("No whisper ggml model found")


def to_wav16k(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst
    r = run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-ar", "16000", "-ac", "1", str(dst),
    ])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg wav failed: {r.stderr[-300:]}")
    return dst


def span_phrases(wav: Path, model: Path, work: Path,
                 min_sil: float = 0.8, pad: float = 0.12,
                 min_speech: float = 0.9) -> list[tuple[float, float, str]]:
    """按静音切段、逐段转写 —— 幻觉母带的专用采集路径。

    词级路径(whisper -ml 1 全轨转写)在超慢、长静默的母带上必然幻觉:
    whisper 把静音听成成串的 you / Thank you。两个「便宜方案」都实测失败:
      · --vad:幻觉是没了,但句间静音被从解码器眼前拿掉,分组器失去切分
        依据,产出中位 13.7s 的逗号连读大块团(48 条,粒度废了)
      · -nth 0.30:词数 3109/4086,与幻觉原值分毫不差 —— 该阈值只在
        logprob 联动失败时生效,对自信的幻觉毫无作用
    这里用 qc_session B 层验证过的第三条路:silencedetect 找语音段
    (边界是**真实母带时间戳**),每段单独送 whisper —— 静音根本不进解码器,
    幻觉无从发生;段间静音 ≥0.8s 天然就是句界,粒度即句子。
    """
    total = probe_duration(wav) or 0.0
    r = run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af",
             f"silencedetect=noise=-45dB:d={min_sil}", "-f", "null", "-"])
    sil, cur = [], None
    for kind, val in re.findall(r"silence_(start|end): ([-\d.]+)", r.stderr):
        v = float(val)
        if kind == "start":
            cur = v
        elif cur is not None:
            sil.append((cur, v))
            cur = None
    if cur is not None:
        sil.append((cur, total))
    spans, t = [], 0.0
    for s, e in sil:
        if s - t >= min_speech:
            spans.append((max(0.0, t - pad), min(total, s + pad)))
        t = e
    if total - t >= min_speech:
        spans.append((max(0.0, t - pad), total))
    print(f"  span 模式:语音段 {len(spans)} 个(静音≥{min_sil}s 为界)")

    out: list[tuple[float, float, str]] = []
    d = work / (wav.stem + "_spans")
    d.mkdir(exist_ok=True)
    clips = []
    for i, (t0, t1) in enumerate(spans):
        w = d / f"{i:04d}.wav"
        rr = run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.3f}",
                  "-to", f"{t1:.3f}", "-i", str(wav), str(w)])
        if rr.returncode == 0 and w.exists():
            clips.append((t0, t1, w))
    for b in range(0, len(clips), 120):
        run([WHISPER_CLI, "-m", str(model), "-nt", "-l", "en", "-otxt"]
            + [str(w) for _, _, w in clips[b:b + 120]])
    halluc = {"you", "thank you", "bye", "so", "thanks for watching", "", "u"}
    for t0, t1, w in clips:
        f = Path(str(w) + ".txt")
        text = " ".join(f.read_text(errors="ignore").split()) if f.exists() else ""
        if text.strip().lower().rstrip(".") in halluc:
            continue
        out.append((round(t0, 3), round(t1, 3), text))
    return out


def whisper_words(wav: Path, model: Path, work: Path,
                  nth: float | None = None,
                  vad_model: Path | None = None) -> list[Word]:
    """Run whisper-cli word-level; return Word list."""
    # 缓存名带上参数指纹:换了阈值/VAD 必须重转写,否则「重采」只是重读旧缓存,
    # 幻觉一个不少 —— 看起来做了事,实际什么都没变。
    tag = ""
    if nth is not None:
        tag += f"_nth{nth:g}"
    if vad_model is not None:
        tag += "_vad"
    out_base = work / (wav.stem + "_w" + tag)
    json_path = Path(str(out_base) + ".json")
    # Reuse cache if present and newer than wav
    if json_path.exists() and json_path.stat().st_mtime >= wav.stat().st_mtime:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        cmd = [
            WHISPER_CLI,
            "-m", str(model),
            "-l", "en",
            "-sow",
            "-ml", "1",  # force short segments → near word-level
            "-oj",
            "-of", str(out_base),
            "-t", "6",
        ]
        if nth is not None:
            cmd += ["-nth", f"{nth:g}"]
        if vad_model is not None:
            cmd += ["--vad", "--vad-model", str(vad_model)]
        cmd.append(str(wav))
        print(f"  whisper… {wav.name}")
        r = run(cmd)
        if r.returncode != 0 and not json_path.exists():
            print(r.stderr[-800:], file=sys.stderr)
            raise RuntimeError(f"whisper-cli failed on {wav}")
        data = json.loads(json_path.read_text(encoding="utf-8"))

    words: list[Word] = []
    for seg in data.get("transcription") or []:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        off = seg.get("offsets") or {}
        try:
            a = float(off.get("from", 0)) / 1000.0
            b = float(off.get("to", 0)) / 1000.0
        except (TypeError, ValueError):
            ts = seg.get("timestamps") or {}
            a = parse_ts(str(ts.get("from", "0")))
            b = parse_ts(str(ts.get("to", "0")))
        if b < a:
            a, b = b, a
        if b - a < 0.01 and text:
            b = a + 0.12
        words.append(Word(start=a, end=b, text=text))
    return words


MIN_ATOM_WORDS = 3          # 少于 3 词的不成句,不入库
MIN_SPEECH_DENSITY = 0.9    # 词/秒下限;低于此说明大部分时长是静默


def group_phrases(
    words: list[Word],
    *,
    max_gap: float = 0.55,
    max_sec: float = 12.5,
    min_sec: float = 0.9,
    punct_break: bool = True,
) -> list[tuple[float, float, str]]:
    """Group words into phrases without treating max_sec as a blind knife.

    ``max_sec`` is a soft target. A phrase may run longer to reach a pause or
    clause boundary; only the 1.8x hard ceiling can force a split. This keeps
    atoms reusable while greatly reducing dangling heads and tails.
    """
    if not words:
        return []
    phrases: list[tuple[float, float, str]] = []
    buf: list[Word] = [words[0]]

    def flush():
        """落一条原子。除时长外还要过两道语音质量门 —— 2026-08-05 复审发现
        库里 46.5% 的原子是"长静默里挂着一两个词"(7.5s 只说了 Lord.),
        它们当不了台词,应在采集阶段就不产生。"""
        nonlocal buf
        if not buf:
            return
        text = " ".join(w.text for w in buf)
        text = re.sub(r"\s+", " ", text).strip()
        # fix spaced punctuation from word split
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
        t0, t1 = buf[0].start, buf[-1].end

        nwords = len(re.sub(r"[^A-Za-z0-9' ]", " ", text).split())
        span = max(1e-6, t1 - t0)
        if nwords < MIN_ATOM_WORDS:
            return                                    # 词片
        if nwords / span < MIN_SPEECH_DENSITY:
            return                                    # 大部分是静音
        # 首尾静音收紧:以首尾词为界,只留很小的呼吸余量
        if t1 - t0 >= min_sec * 0.7 and text:
            # pad slightly
            t0p = max(0.0, t0 - 0.03)
            t1p = t1 + 0.06
            phrases.append((t0p, t1p, text))
        buf = []

    for w in words[1:]:
        gap = w.start - buf[-1].end
        dur = w.end - buf[0].start
        last = buf[-1].text.rstrip()
        should_break = False
        if gap >= max_gap:
            should_break = True
        if punct_break and last and last[-1] in ".!?":
            should_break = True
        soft_gap = min(0.30, max_gap * 0.55)
        clause_boundary = bool(last and last[-1] in ",;:")
        if dur >= max_sec and (gap >= soft_gap or clause_boundary):
            should_break = True
        if dur >= max_sec * 1.8:
            should_break = True
        if should_break:
            flush()
            buf = [w]
        else:
            buf.append(w)
    flush()
    return phrases


def source_tags(name: str) -> list[str]:
    low = name.lower().replace(" ", "_")
    tags: list[str] = []
    for pat, ts in SOURCE_THEME:
        if re.search(pat, low, re.I):
            tags.extend(ts)
    out = []
    for t in tags:
        if t not in out:
            out.append(t)
    return out


def role_from_text(text: str, pos: float, dur: float, src_tags: list[str],
                   positional: bool = True,
                   addressee: str = "") -> tuple[str, list[str]]:
    """positional=False 用于 TTS 批次母带 —— 那里的「位置」只是我写稿的行序,
    不带任何语义。真实节目母带里位置有意义(开场在前、祝福在后),才可用。

    addressee 作为**最后的兜底信号**:关键词判不出角色时,「你」指谁本身
    就是最可靠的分类依据 —— 对听者说是安慰,对上帝说是祈求。
    采集阶段还没打 addressee 标签,所以传空;reclassify_roles 会补上。"""
    low = text.lower()
    tags = list(src_tags)
    hits: list[str] = []
    for pat, rs in TEXT_ROLE_RULES:
        if re.search(pat, low, re.I):
            hits.extend(rs)
    for h in hits:
        if h not in tags:
            tags.append(h)

    # bless 按**语言形态**识别,不看在母带里的位置 —— 祝福语的标志是
    # 祈愿式 "May the Lord…" / "May you…"。2026-08-05 之前只在 pos>0.75
    # 才判 bless,导致整批 57 条祝福语散落到 7 个角色,bless 始终为 0。
    is_benediction = bool(re.match(r"\s*may\s+(the\s+)?(lord|god|he|his|"
                                   r"you|your|every|christ|the)", low)) or \
        bool(re.search(r"\bthe lord bless you\b|\bpeace of christ be with\b", low))
    if is_benediction:
        role = "bless"
    elif "open" in hits or (pos < 0.06 and "welcome" in low):
        role = "open"
    elif "close" in hits or ("bless" in hits and pos > 0.75):
        role = "close" if "close" in hits or pos > 0.88 else "bless"
    elif "breath" in hits and dur <= 3.5:
        role = "breath"
    elif "scripture" in hits or re.search(r"\bpsalm\b|\bmatthew\b|\bjohn\b|\bisaiah\b", low):
        role = "scripture"
    elif "release" in hits:
        role = "release"
    elif "deepen" in hits:
        role = "deepen"
    elif "safety" in hits:
        role = "safety"
    elif "poetic" in hits:
        role = "poetic"
    elif positional and dur <= 2.0:
        role = "breath"
    elif positional and pos < 0.08:
        role = "open"
    elif positional and pos > 0.92:
        role = "close"
    elif dur >= 3.0 and "scripture" in src_tags:
        role = "scripture"
    elif positional and 0.3 <= pos <= 0.55:
        role = "release"
    elif positional and 0.55 < pos <= 0.85:
        role = "deepen"
    elif addressee == "listener":
        role = "comfort"      # 对听者说的完整句 —— 安慰/确据
    elif addressee == "god":
        role = "petition"     # 对上帝说的完整句 —— 祈求/倾诉
    else:
        # 无语言证据、addressee 也无法定夺 → misc。**不要**兜底进
        # poetic/deepen:错标的 deepen 是隐形毒药(拼进节目才发现语义不对),
        # 而 misc 是显式的「待定规则」,盘点时看得见。
        role = "misc"

    if role not in tags:
        tags.append(role)
    return role, tags


def _emit_atom(master: Path, t0: float, t1: float, text: str, pos: float,
               stags: list[str], positional: bool,
               root: Path, all_atoms: list["Atom"]) -> None:
    """一条短语 → 一条原子(导出音频 + 边车 + 入 all_atoms)。

    词级路径与 span 路径共用 —— 此前这段只在词级循环里,span 模式若另抄一份,
    时长探测的「绝不退回母带跨度」等保命细节就会分头演化。
    """
    dur = t1 - t0
    role, tags = role_from_text(text, pos, dur, stags, positional)
    hid = hashlib.sha1(f"{master.name}:{t0:.3f}:{text}".encode()).hexdigest()[:10]
    aid = f"{role}_{hid}"
    out = root / role / f"{aid}.mp3"
    if not export_clip(master, t0, t1, out):
        print(f"  export fail {t0:.1f}-{t1:.1f} {text[:40]}")
        return
    # 时长以**导出文件**为准,探测不出就重试一次;仍失败则整条不入库。
    # 绝不退回母带跨度 (t1-t0):两者能差出 7 秒,而下游拿它算语速、
    # 排停顿、估长度 —— 与其入库一个错数,不如少一条原子。
    real_dur = probe_duration(out)
    if real_dur is None:
        real_dur = probe_duration(out)
    if real_dur is None or real_dur <= 0:
        print(f"  ⚠ 时长探测失败,该原子不入库: {aid} 「{text[:40]}」")
        return
    atom = Atom(
        id=aid,
        path=str(out),
        source_master=str(master),
        voice="Locke",
        t_start=round(t0, 3),
        t_end=round(t1, 3),
        duration_sec=round(real_dur, 3),
        role=role,
        tags=tags,
        text=text,
        method="whisper_cpp_large_v3_turbo",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    out.with_suffix(".json").write_text(
        json.dumps(asdict(atom), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    all_atoms.append(atom)


def export_clip(src: Path, t0: float, t1: float, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    length = max(0.05, t1 - t0)
    fad = min(0.035, length / 10)
    af = f"afade=t=in:st=0:d={fad:.3f},afade=t=out:st={max(0.0, length - fad):.3f}:d={fad:.3f}"
    r = run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", str(src),
        "-af", af, "-ac", "1", "-ar", "44100",
        "-c:a", "libmp3lame", "-b:a", "192k", str(dst),
    ])
    return r.returncode == 0 and dst.exists() and dst.stat().st_size > 400


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locke", type=Path, default=LOCKE)
    ap.add_argument("--atoms-root", type=Path, default=ATOMS)
    ap.add_argument("--model", type=Path, default=None)
    ap.add_argument("--work", type=Path, default=Path("/tmp/sg_whisper_work"))
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--max-gap", type=float, default=0.55)
    ap.add_argument("--min-sec", type=float, default=0.95)
    ap.add_argument("--max-sec", type=float, default=12.5)
    ap.add_argument("--limit", type=int, default=0, help="process only first N masters (debug)")
    ap.add_argument("--only", action="append", default=None,
                    help="只采集文件名含该子串的母带(可多次);增量采集用,"
                         "避免覆盖已重标注的旧原子")
    ap.add_argument("--nth", type=float, default=None,
                    help="whisper 无语音阈值(-nth,默认 0.60)。调低更易把静音判为"
                         "静音 —— 压幻觉用,重采幻觉母带时建议 0.30")
    ap.add_argument("--vad-model", type=Path, default=None,
                    help="silero VAD 模型路径;给了就开 --vad,静音段根本不进解码器"
                         "(比 -nth 更根治:幻觉多发于长静音)")
    ap.add_argument("--span-mode", action="store_true",
                    help="按静音切段、逐段转写(幻觉母带专用)。静音不进解码器,"
                         "段边界即真实句界;--vad 与 -nth 两条路都实测失败后所立")
    args = ap.parse_args()

    model = resolve_model(args.model)
    print(f"model: {model}")
    masters = sorted(args.locke.glob("*.mp3"))
    if args.only:
        masters = [x for x in masters if any(k in x.name for k in args.only)]
        print(f"增量采集:{len(masters)} 个母带")
    if args.limit:
        masters = masters[: args.limit]
    if not masters:
        print("No masters", file=sys.stderr)
        return 1

    root = args.atoms_root
    root.mkdir(parents=True, exist_ok=True)
    for d in ROLE_DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
        if args.clean:
            for p in (root / d).glob("*"):
                if p.suffix in {".mp3", ".json"}:
                    p.unlink(missing_ok=True)

    args.work.mkdir(parents=True, exist_ok=True)
    all_atoms: list[Atom] = []

    for mi, master in enumerate(masters, 1):
        mdur = probe_duration(master)
        print(f"\n[{mi}/{len(masters)}] {master.name} "
              f"({mdur/60:.1f} min)" if mdur else f"(时长未知)")
        wav = to_wav16k(master, args.work / f"{master.stem}.wav")
        if args.span_mode:
            try:
                phrases = span_phrases(wav, model, args.work)
            except Exception as e:
                print(f"  SPAN FAIL: {e}", file=sys.stderr)
                continue
            print(f"  phrases={len(phrases)}")
            stags = source_tags(master.name)
            positional = not re.search(r"_G\d+_", master.name)
            n = max(len(phrases) - 1, 1)
            for i, (t0, t1, text) in enumerate(phrases):
                _emit_atom(master, t0, t1, text, i / n, stags, positional,
                           root, all_atoms)
            continue
        try:
            words = whisper_words(wav, model, args.work,
                                  nth=args.nth, vad_model=args.vad_model)
        except Exception as e:
            print(f"  WHISPER FAIL: {e}", file=sys.stderr)
            continue
        print(f"  words={len(words)}")
        phrases = group_phrases(
            words,
            max_gap=args.max_gap,
            max_sec=args.max_sec,
            min_sec=args.min_sec,
        )
        print(f"  phrases={len(phrases)}")
        stags = source_tags(master.name)
        # TTS 批次母带(ElevenLabs_G1_… / _G2_…)里的位置 = 我写稿的行序,无语义
        positional = not re.search(r"_G\d+_", master.name)
        n = max(len(phrases) - 1, 1)
        for i, (t0, t1, text) in enumerate(phrases):
            _emit_atom(master, t0, t1, text, i / n, stags, positional,
                       root, all_atoms)

    roles = Counter(a.role for a in all_atoms)
    with_text = sum(1 for a in all_atoms if a.text)
    manifest = {
        "version": 3,
        "voice": "Locke",
        "method": "whisper_cpp_word_group",
        "model": str(model),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(args.locke),
        "masters": [str(m) for m in masters],
        "count": len(all_atoms),
        "with_text": with_text,
        "roles": dict(roles),
        "params": {
            "max_gap": args.max_gap,
            "min_sec": args.min_sec,
            "max_sec": args.max_sec,
        },
        "atoms": [asdict(a) for a in all_atoms],
    }
    man = root / "manifest.json"
    if args.only and man.exists():
        # —— 增量采集必须**合并**,不能覆写 ——
        # manifest 里躺着全库的隔离标记、边界审计、addressee、时长校正,
        # 是几天审计工作的唯一载体。此前 --only 的帮助文案写着「避免覆盖」,
        # 写盘却只写本次的原子 —— 跑一次就会把 2214 条记录抹成几十条。
        # 合并规则:被重采母带的旧记录整体退场(新旧 id 因切点不同对不上,
        # 留着只会新旧混杂),其余母带的记录原样保留。
        old = json.loads(man.read_text(encoding="utf-8"))
        redone = {str(m) for m in masters}
        kept = [x for x in old.get("atoms", [])
                if x.get("source_master") not in redone]
        dropped = len(old.get("atoms", [])) - len(kept)
        manifest["atoms"] = kept + manifest["atoms"]
        manifest["count"] = len(manifest["atoms"])
        print(f"  合并:保留其它母带 {len(kept)} 条,替换被重采母带旧记录 {dropped} 条")
        print(f"  ⚠ 新原子未经审计,不在白名单 —— 须走完审计链后"
              f" verify_atom_texts --mark --write-whitelist")
    man.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # also keep transcripts index
    tx = root / "transcripts_index.jsonl"
    with tx.open("w", encoding="utf-8") as f:
        for a in all_atoms:
            f.write(json.dumps({"id": a.id, "role": a.role, "text": a.text, "path": a.path}, ensure_ascii=False) + "\n")
    print(f"\nDONE atoms={len(all_atoms)} with_text={with_text}")
    print("roles:", dict(roles))
    print("manifest:", man)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
