#!/usr/bin/env python3
# coding: utf-8
"""Build infinite Christian evening-prayer sessions from speech atoms + music bed.

Usage:
  ./.venv/bin/python scripts/sg/build_session.py --theme night_of_peace --minutes 18
  ./.venv/bin/python scripts/sg/build_session.py --seed 42 --out ~/Studio/Workspace/outputs/sg/sessions
"""
from __future__ import annotations

import argparse
import difflib
import json
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atom_quality import (FLOW_GAP, MAX_OVERLAP, SYNTAX_REPAIR_GAP,
                          WAVEFORM_REPAIR_GAP, completes_dangling,
                          head_fragment_reason, load_whitelist, reject_reason,
                          words as aq_words)
from sg_media import probe_duration as sg_probe

DEFAULT_ATOMS = Path.home() / "Studio/Library/sg/atoms"
DEFAULT_GRAMMAR = Path.home() / "Studio/Library/sg/catalog/grammars/evening_prayer_v0.json"
DEFAULT_OUT = Path.home() / "Studio/Workspace/outputs/sg/sessions"
DEFAULT_VIDEO_DIR = Path.home() / "Studio/Library/sg/assets/video"
MUSIC_SOURCES = [
    Path.home() / "Studio/Library/sg/songs/instrumental",
    Path.home() / "Studio/Library/chl/CHL500",
]


@dataclass
class AtomRec:
    id: str
    path: Path
    role: str
    tags: list[str]
    duration_sec: float
    source_master: str
    t_start: float = 0.0
    t_end: float = 0.0
    text: str = ""
    addressee: str = "neutral"     # god / listener / neutral —— 「你」指谁
    head_cut: bool = False         # 母带:起点处仍在发声(采集丢词)
    tail_cut: bool = False         # 母带:终点处仍在发声(采集丢词)
    head_hard_cut: bool = False    # 实测:原子自己的起点停在满音量,首词被削
    tail_hard_cut: bool = False    # 实测:原子自己的终点停在满音量,尾词被削
    sequence_index: int = -1


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def probe_duration(path: Path) -> float:
    """时长(秒);读不出返回 0.0。

    ⚠ 兜底值 0.0 是为了兼容既有调用点,**新代码请直接用 sg_media**:
    `probe_duration` 返回 None、`probe_duration_or_die` 直接停。
    返回 0.0 的坑见 sg_media 模块开头 —— 222 条时长漂移就是这么来的。
    """
    return sg_probe(path) or 0.0


def load_atoms(manifest_path: Path) -> list[AtomRec]:
    """载入**可用**原子。

    2026-08-05 之前这里不设任何门禁,于是:
      · 11 条已隔离的「自比上帝」原子照样能被选进节目(神学红线)
      · ~400 条静音原子带着相邻句的假文本,渲染出有字幕却无声的段落
    隔离字段与质量门都存在,只是编排器从来没读过 —— 加字段不等于设门禁。

    2026-08-10 加第三道门:whisper 复核白名单 08-05 就生成好了,但同样
    没有任何代码消费它 —— qc01~qc08 八期照样混入 42–46% 病态原子
    (成片里语音与字幕对不上的直接原因)。白名单缺失时直接抛异常停线。
    """
    whitelist = load_whitelist()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: list[AtomRec] = []
    rejected: dict[str, int] = {}
    for a in data.get("atoms", []):
        why = reject_reason(a, whitelist)
        if why:
            k = re.sub(r"[\d.]+", "N", why)
            rejected[k] = rejected.get(k, 0) + 1
            continue
        p = Path(a["path"])
        if not p.exists():
            rejected["文件缺失"] = rejected.get("文件缺失", 0) + 1
            continue
        out.append(AtomRec(
            id=a["id"],
            path=p,
            role=a.get("role") or "misc",
            tags=list(a.get("tags") or []),
            duration_sec=float(a.get("duration_sec") or 0),
            source_master=a.get("source_master") or "",
            t_start=float(a.get("t_start") or 0),
            t_end=float(a.get("t_end") or 0),
            text=str(a.get("text") or "").strip(),
            addressee=str(a.get("addressee") or "neutral"),
            head_cut=bool(a.get("head_cut")),
            tail_cut=bool(a.get("tail_cut")),
            head_hard_cut=bool(a.get("head_hard_cut")),
            tail_hard_cut=bool(a.get("tail_hard_cut")),
        ))
    if rejected:
        detail = " · ".join(f"{k} {v}" for k, v in sorted(rejected.items()))
        print(f"[atoms] 可用 {len(out)} / 剔除 {sum(rejected.values())}({detail})")
    by_source: dict[str, list[AtomRec]] = {}
    for atom in out:
        by_source.setdefault(atom.source_master, []).append(atom)
    for source_atoms in by_source.values():
        source_atoms.sort(key=lambda atom: (atom.t_start, atom.t_end, atom.id))
        for index, atom in enumerate(source_atoms):
            atom.sequence_index = index
    return out


def load_grammar(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_count(spec) -> int:
    if isinstance(spec, int):
        return spec
    if isinstance(spec, list) and len(spec) == 2:
        return random.randint(int(spec[0]), int(spec[1]))
    return 1


CTA_RE = re.compile(
    r"\b(subscribe|follow (?:the|this) channel|leave a comment|share (?:your|this)|"
    r"prayer request|like (?:this|the) video|turn on notifications)\b",
    re.I,
)
BRAND_RE = re.compile(r"\bwelcome to sleep in grace\b", re.I)
STRONG_CLOSE_RE = re.compile(
    r"\b(amen|peace be with you|good night|sleep in grace|in (?:the )?name of jesus|"
    r"in jesus(?: christ)?'?s name|make me dwell in safety)\b",
    re.I,
)
# 祝福语的**语言形态**判据。只信 role 标签不够:角色是采集时按规则打的,
# 会把「with you now.」这类残句也标成 bless,于是祝福位上出现半句话。
# CLOSE 早就有 is_strong_close_text 做形态校验,BLESS 一直缺这一道。
BLESSING_RE = re.compile(
    r"^\s*may\s+(?:the\s+)?(?:lord|god|he|his|you|your|every|christ|"
    r"the|it|peace|mercy|grace)\b|\bthe lord bless\b|\bpeace be with you\b|"
    r"\bbless you\b|\bgive you (?:his )?peace\b", re.I)


def is_blessing_text(text: str) -> bool:
    return bool(BLESSING_RE.search(text or ""))


FIRST_SINGULAR_RE = re.compile(r"\b(?:I|me|my|mine)\b", re.I)
FIRST_PLURAL_RE = re.compile(r"\b(?:we|us|our|ours)\b", re.I)
FRAGMENT_START_RE = re.compile(
    r"^(?:and\s+)?(?:because|especially|only|with|is|are|was|were|will|would|"
    r"circumstances|us\b|come\s+like|beyond\b)",
    re.I,
)
FRAGMENT_END_RE = re.compile(
    r"\b(?:a|an|the|and|but|or|to|of|in|for|with|like|every|my|your|our|his|"
    r"her|their|who|which|that|is|are|was|were|will|would|let|soft|gentle)\s*[.!?]*$",
    re.I,
)
DEPENDENT_END_RE = re.compile(
    r"\b(?:because|although|unless|while|when|if|so)\s+(?:you(?:\s+alone)?|he|she|we|they|it|lord|god|jesus)\s*[.!?]*$",
    re.I,
)


def normalize_atom_text(text: str) -> str:
    """Normalize transcript text for duplicate and near-duplicate checks."""
    norm = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    words = norm.split()
    words = [word for i, word in enumerate(words) if i == 0 or word != words[i - 1]]
    if len(words) > 2 and words[0] in {"and", "but", "so"}:
        words = words[1:]
    norm = " ".join(words)
    if norm.startswith("amen"):
        return "amen"
    if norm.startswith("peace be with you"):
        return "peace be with you"
    if norm.startswith("you are not alone"):
        return "you are not alone"
    if norm in {"you are here", "you are right here"}:
        return "you are here"
    if re.fullmatch(r"this is your sacred (?:hour|time)", norm):
        return "this is your sacred time"
    if norm.startswith("tonight we return to rest"):
        return "tonight we return to rest"
    norm = re.sub(r"^(?:your|the) word says\s+", "", norm)
    return norm


def is_cta_text(text: str) -> bool:
    return bool(CTA_RE.search(text or ""))


def is_brand_text(text: str) -> bool:
    return bool(BRAND_RE.search(text or ""))


def is_strong_close_text(text: str) -> bool:
    return bool(STRONG_CLOSE_RE.search(text or ""))


def strong_close_score(text: str) -> float:
    raw = re.sub(r"[^a-z]+", " ", (text or "").lower()).strip()
    if raw == "amen":
        return 12.0
    if "in the name of jesus" in raw or "in jesus name" in raw or "in jesus christ s name" in raw:
        return 10.0
    if raw.startswith("peace be with you"):
        return 8.0
    if raw.startswith("amen"):
        return 5.0
    return 3.0 if is_strong_close_text(text) else 0.0


def first_person_profile(text: str) -> tuple[int, int]:
    """Return singular/plural first-person pronoun counts."""
    return len(FIRST_SINGULAR_RE.findall(text or "")), len(FIRST_PLURAL_RE.findall(text or ""))


# 近期用过的原子 → 新鲜度惩罚系数(1.0 = 上一期刚用过,越久越接近 0)。
# 由 load_recent() 在开工前填好;score_atom 读它。
RECENT: dict[str, float] = {}
HISTORY = Path.home() / "Studio/Library/sg/catalog/episode_history.json"


def load_recent(days: int) -> dict[str, float]:
    """读最近 N 期用过的原子,越近权重越高。

    语法里的 cooldown.same_atom_days 一直存在,但没有任何代码读过它 ——
    于是「同一条原子五天内不重复」只是一句配置注释。
    用惩罚而不是硬排除:CLOSE 这类槽位只有 18 条唯一文案,硬排除五期
    就会直接选不出东西;惩罚能在供给紧张时自然退让。
    """
    if not HISTORY.exists() or days <= 0:
        return {}
    try:
        hist = json.loads(HISTORY.read_text())
    except Exception:
        return {}
    eps = hist.get("episodes", [])[-days:]
    out: dict[str, float] = {}
    for i, ep in enumerate(eps):
        # 越近权重越大,但**最老的一期也要留住半程罚分**。
        # 原式 (i+1)/len 让窗口最老那期只剩 1/12 权重 → 罚分 −3.3,
        # 排不过续接 +12 与角色 +5,于是相隔 8 期的两期能撞掉 67.7% 的台词
        # (2026-08-12 实测第 3 期 ∩ 第 11 期 = 63/93 句)。
        # 下限抬到 0.5(罚分 −20)后,整个窗口内都真正设防;仍用惩罚而非硬排除,
        # CLOSE 这类只有 7 条唯一文案的槽位才能在供给紧张时自然退让。
        w = 0.5 + 0.5 * (i + 1) / len(eps)
        for aid in ep.get("atom_ids", []):
            out[aid] = max(out.get(aid, 0.0), w)
    return out


def record_episode(episode_id: str, atom_ids: list[str], keep: int = 60,
                   tracks: list[str] | None = None) -> None:
    hist = {"episodes": []}
    if HISTORY.exists():
        try:
            hist = json.loads(HISTORY.read_text())
        except Exception:
            pass
    hist.setdefault("episodes", []).append(
        {"episode_id": episode_id,
         "at": datetime.now(timezone.utc).isoformat(),
         "atom_ids": atom_ids,
         "tracks": tracks or []})
    hist["episodes"] = hist["episodes"][-keep:]
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1))


def record_tracks(episode_id: str, tracks: list[str]) -> None:
    """把选床结果回填进本期的历史条目。

    历史在**门禁通过时**落笔(原子与裁决同一时刻,不能等),而曲目要到
    渲染阶段选完床才知道 —— 所以分两步:先记原子,后补曲目。"""
    if not HISTORY.exists():
        return
    try:
        hist = json.loads(HISTORY.read_text())
    except Exception:
        return
    for ep in reversed(hist.get("episodes", [])):
        if ep.get("episode_id") == episode_id:
            ep["tracks"] = tracks
            break
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1))


def load_recent_tracks(episodes: int = 8) -> set[str]:
    """最近 N 期用过的曲目文件名 —— 选床时整曲回避。

    VO 原子有 cooldown,音乐此前却是纯随机:1,501 首曲库随机抽 10 首,
    两期重合的期望只有 0.07 首,听感上确实"几乎不重"——但那是概率,
    不是保证。改成硬回避后:60 分钟一期约 18 首,曲库仍够 80+ 期完全
    不重曲;回避窗口 8 期只挡住近邻,远期轮回是曲库规模决定的自由。
    """
    if not HISTORY.exists():
        return set()
    try:
        hist = json.loads(HISTORY.read_text())
    except Exception:
        return set()
    out: set[str] = set()
    for ep in hist.get("episodes", [])[-episodes:]:
        out.update(ep.get("tracks") or [])
    return out


MID_SENTENCE_RE = re.compile(r"[.!?]\s*[\"”]?\s*$")


def ends_mid_sentence(text: str) -> bool:
    """句末没有终止标点 = 这条原子把句子切断了,必须由后继补完。"""
    t = (text or "").strip()
    return bool(t) and not MID_SENTENCE_RE.search(t)


def needs_closure(atom: "AtomRec") -> bool:
    """这条原子是否必须由母带里的后继补完。

    两类证据都算,波形优先:
      tail_cut  波形显示终点切穿了语流 —— 尾词已被削掉,听感上就是半个词
      文本      句末没有终止标点 —— 话没说完
    """
    return bool(atom.tail_cut) or ends_mid_sentence(atom.text)


def successor_of(atoms: list["AtomRec"], atom: "AtomRec") -> "AtomRec | None":
    """母带里**序号紧邻**的下一条原子。

    必须严格按 sequence_index + 1 取,不能「按时间找下一条」:后者遇到
    与当前原子重叠的条目会跳过它,直接跨到 seq+2 —— 于是补完出来的句子
    中间缺了一块,而审计(用序号相邻判定续接)会把它判成孤立碎片。
    选择端与审计端必须用同一套「相邻」定义。
    """
    if atom.sequence_index < 0:
        return None
    for c in atoms:
        if (c.source_master == atom.source_master
                and c.sequence_index == atom.sequence_index + 1):
            # 后继若离得太远,母带里中间隔着别的话,接上去并不能把句子说完。
            # 判据必须和 directly_continues / 内容审计完全一致,否则
            # 补完的结果会被审计判成孤立碎片。
            #
            # **尾词被波形切穿的,容差收到 0.35s**:那半个词就躺在紧挨着的
            # 下一条里,隔几秒的「后继」中间已经丢了话,补完是假的。
            # 三档容差,按「要补的是什么」分:
            #   被削掉半个词  → 0.35s(那半个词就在紧挨着的下一条里)
            #   句子没说完    → 8.0s(实测真实续句的上界)
            #   只是语流衔接  → 18.0s(刻意的长停顿,两句各自完整)
            if atom.tail_cut and atom.tail_hard_cut:
                limit = WAVEFORM_REPAIR_GAP
            elif ends_mid_sentence(atom.text):
                limit = SYNTAX_REPAIR_GAP
            else:
                limit = FLOW_GAP
            return c if directly_continues(atom, c, limit) else None
    return None


def addressee_compatible(prev: "AtomRec | None", atom: "AtomRec") -> bool:
    """相邻两条原子的「你」能不能指向不同对象。

    祷告模式 god      "You are faithful."        → you = 上帝
    旁白模式 listener "He is watching over you." → you = 听者

    这两句直接相邻,听者会在一秒内失去指代:「他整夜看顾**你**……**你**是
    信实的。」谁是信实的?中性句(neutral)两边都能接,是唯一的合法过渡。
    模式切换必须经由 neutral 或一段静默,不能硬切。

    这比 perspective(I/we 一致)重要:人称错了是语法瑕疵,
    addressee 错了是语义崩塌。
    """
    if prev is None:                      # 段首/静默之后,可自由起调
        return True
    a, b = prev.addressee, atom.addressee
    return a == b or "neutral" in (a, b)


def matches_perspective(text: str, perspective: str) -> bool:
    singular, plural = first_person_profile(text)
    if singular and plural:
        return False
    if perspective == "singular":
        return plural == 0
    if perspective == "plural":
        return singular == 0
    return True


def is_orphan_fragment(text: str) -> bool:
    """Return True when a phrase is unsafe without its source context."""
    value = " ".join((text or "").split()).strip()
    if not value:
        return True
    norm = normalize_atom_text(value)
    if norm in {"amen", "breathe", "breathe slowly", "peace be with you"}:
        return False
    if len(norm.split()) <= 1:
        return True
    if value[:1].islower() or FRAGMENT_START_RE.search(value):
        return True
    if FRAGMENT_END_RE.search(value):
        return True
    if DEPENDENT_END_RE.search(value):
        return True
    return False


# 间隔判据(MAX_OVERLAP / WAVEFORM_REPAIR_GAP / SYNTAX_REPAIR_GAP)的取值依据
# 与出处见 atom_quality —— 出片端与验收端共用,不得在本文件另行定义。


def directly_continues(previous: AtomRec | None, atom: AtomRec, max_gap_sec: float) -> bool:
    if previous is None or not previous.source_master or previous.source_master != atom.source_master:
        return False
    if previous.sequence_index >= 0 and atom.sequence_index != previous.sequence_index + 1:
        return False
    gap = atom.t_start - previous.t_end
    return MAX_OVERLAP <= gap <= max_gap_sec


def waveform_contiguous(previous: AtomRec | None, atom: AtomRec) -> bool:
    """两条原子在母带里是否**紧挨着** —— 被切穿的边界只有它修得了。"""
    return directly_continues(previous, atom, WAVEFORM_REPAIR_GAP)


def stutters_with(previous: AtomRec | None, atom: AtomRec) -> bool:
    """接上去会不会把同一个词念两遍。

    相邻原子有 0.09s / 0.21s 两档固定重叠(采集切分的伪影)。重叠区里若正好
    落着一个词,它就同时存在于两个文件中 —— 拼起来听到的是
    「Now, Lord, as ／ **As** I lie down」。
    判据必须带上「间隔为负」:间隔 6 秒的「…surrounds you.」接「**You** are
    invited…」只是两句都碰到了 you,而「You can rest… ／ You can sleep…」
    是刻意的排比,两者都不该拦。
    """
    if previous is None or previous.source_master != atom.source_master:
        return False
    if atom.t_start - previous.t_end >= 0:
        return False
    pw, aw = aq_words(previous.text or ""), aq_words(atom.text or "")
    return bool(pw and aw and pw[-1] == aw[0])


def text_is_duplicate(text: str, used_texts: set[str], threshold: float = 0.84) -> bool:
    norm = normalize_atom_text(text)
    if not norm:
        return True
    if norm in used_texts:
        return True
    if len(norm.split()) >= 4:
        prefix = " ".join(norm.split()[:2])
        return any(
            old.startswith(prefix + " ")
            and abs(len(old) - len(norm)) <= max(12, int(len(norm) * 0.25))
            and difflib.SequenceMatcher(None, norm, old).ratio() >= threshold
            for old in used_texts
        )
    return False


def score_atom(
    atom: AtomRec,
    roles: list[str],
    boost_tags: list[str],
    prefer_tags: list[str],
    prefer_min_sec: float = 0.0,
    previous_atom: AtomRec | None = None,
    continuation_max_gap_sec: float = 18.0,
) -> float:
    score = 0.0
    if atom.role in roles:
        score += 5.0
    for r in roles:
        if r in atom.tags:
            score += 2.0
    for t in boost_tags:
        blob = " ".join(atom.tags).lower() + " " + atom.source_master.lower()
        if t.lower() in blob:
            score += 1.5
    for t in prefer_tags:
        if t.lower() in " ".join(atom.tags).lower() or t.lower() in atom.source_master.lower():
            score += 2.5
    if prefer_min_sec and atom.duration_sec >= prefer_min_sec:
        score += 2.0
    if 2.5 <= atom.duration_sec <= 11.0:
        score += 1.2
    if atom.duration_sec < 1.6:
        score -= 1.5
    if directly_continues(previous_atom, atom, continuation_max_gap_sec):
        gap = max(0.0, atom.t_start - (previous_atom.t_end if previous_atom else 0.0))
        score += 12.0 if gap <= 3.0 else 8.0
    elif previous_atom and atom.source_master == previous_atom.source_master:
        if atom.t_start > previous_atom.t_start:
            score += 2.0
        else:
            score -= 6.0
    elif previous_atom:
        score -= 1.0
    # 近期用过的重罚 —— 日更频道最怕连着两晚听到同一篇稿子。
    # 2026-08-05 实测:12 期两两平均重叠 74.4%,6 句每一期都出现。
    # 语法里 cooldown.same_atom_days 早就写了,但代码从没读过它。
    if atom.id in RECENT:
        score -= 40.0 * RECENT[atom.id]
    # 抖动必须大到能改变名次。原先是 0.8,而角色匹配 +5.0、续接 +12.0 ——
    # 这点抖动排不动任何东西,于是每次都是同一批原子胜出。
    # 但不能盖过续接分:那是正确性(半句话必须接上),不是偏好。
    score += random.random() * 4.0
    return score


def _atom_sidecar_text(atom_path: Path) -> str | None:
    side = atom_path.with_suffix(".json")
    if side.exists():
        try:
            return json.loads(side.read_text(encoding="utf-8")).get("text")
        except Exception:
            return None
    return None


def select_cold_open(
    atoms: list[AtomRec],
    grammar: dict,
    *,
    used_ids: set[str],
) -> AtomRec | None:
    """Always start with brand welcome when cold_open is enabled."""
    cfg = grammar.get("cold_open") or {}
    if cfg.get("enabled") is False:
        return None
    exacts = [str(t).strip() for t in (cfg.get("exact_texts") or []) if str(t).strip()]
    prefer = str(cfg.get("prefer_exact") or "Welcome to Sleep in Grace.").strip()
    if prefer and prefer not in exacts:
        exacts = [prefer, *exacts]
    if not exacts:
        exacts = ["Welcome to Sleep in Grace."]

    # Load texts for open-role atoms
    scored: list[tuple[int, AtomRec]] = []
    for a in atoms:
        if a.id in used_ids:
            continue
        text = (_atom_sidecar_text(a.path) or "").strip()
        if not text:
            continue
        if text not in exacts:
            # also accept case-insensitive exact
            if text.lower() not in {t.lower() for t in exacts}:
                continue
        # prefer exact brand line, then Welcome master, then shorter clean line
        rank = 0
        if text == prefer or text.lower() == prefer.lower():
            rank += 100
        if "Welcome_to_Sleep" in (a.source_master or ""):
            rank += 20
        if text.lower().startswith("welcome to sleep in grace"):
            rank += 10
        rank += max(0, 5 - int(a.duration_sec))  # slight prefer clean short welcome
        scored.append((rank, a))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1].id))
    return scored[0][1]


def select_for_slot(
    atoms: list[AtomRec],
    slot: dict,
    *,
    used_ids: set[str],
    boost_tags: list[str],
    grammar: dict | None = None,
    used_texts: set[str] | None = None,
    previous_atom: AtomRec | None = None,
    cta_count: int = 0,
    terminal_phase: bool = False,
    role_streak: tuple[str, int] = ("", 0),
) -> list[AtomRec | float]:
    """Return list of AtomRec or float silence seconds."""
    roles = slot.get("roles") or ["misc"]
    if roles == ["silence"] or str(slot.get("id", "")).startswith("REST_SILENCE"):
        sil = slot.get("silence_sec", [20, 40])
        if isinstance(sil, list):
            return [float(random.uniform(float(sil[0]), float(sil[1])))]
        return [float(sil)]

    # Fixed brand cold open
    if slot.get("fixed_cold_open") or str(slot.get("id", "")).upper() == "COLD_OPEN":
        a = select_cold_open(atoms, grammar or {}, used_ids=used_ids)
        if a is None:
            return []
        used_ids.add(a.id)
        return [a]

    prefer = slot.get("prefer_tags") or []
    prefer_min = float(slot.get("prefer_min_sec") or 0.0)
    policy = (grammar or {}).get("content_policy") or {}
    max_cta = int(policy.get("max_cta_per_session", 1))
    reject_fragments = bool(policy.get("reject_orphan_fragments", True))
    continuity_gap = float(policy.get("continuation_max_gap_sec", 18.0))
    perspective = str(policy.get("perspective") or "any").lower()
    used_texts = used_texts if used_texts is not None else set()
    n = pick_count(slot.get("pick", 1))
    if slot.get("optional") and n == 0:
        return []

    candidates = [a for a in atoms if a.id not in used_ids]
    if not candidates:
        candidates = list(atoms)

    def _eligible(atom: AtomRec) -> bool:
        text = atom.text or (_atom_sidecar_text(atom.path) or "")
        continuation = directly_continues(previous_atom, atom, continuity_gap)
        if text_is_duplicate(text, used_texts):
            return False
        if is_cta_text(text) and cta_count >= max_cta:
            return False
        if is_brand_text(text) and str(slot.get("id", "")).upper() != "COLD_OPEN":
            return False
        if atom.role == "close" and not terminal_phase:
            return False
        # 只挡 close **角色**不够:「In the name of Jesus Christ.」存在 release
        # 角色的孪生原子,曾被 FILL 在中段消费 —— 结尾语提前出现,且 CLOSE
        # 随后因文本查重无米下锅。强结尾**形态**一律留给终末槽位。
        if not terminal_phase and is_strong_close_text(text):
            return False
        if atom.role == "open" and terminal_phase:
            return False
        if str(slot.get("id", "")).upper() == "CLOSE" and not is_strong_close_text(text):
            return False
        slot_id = str(slot.get("id", "")).upper()
        if slot_id == "BLESS" and not is_blessing_text(text):
            return False
        # 祝福与收尾必须**自足**:不能是需要后继补完的半句。
        # 「Peace be with you.」被波形判为尾部切穿(真实音频是 "…with you now"),
        # 补句链把后继接上后,祝福位读成「Peace be with you. with you now.」
        if slot_id in {"BLESS", "CLOSE"} and needs_closure(atom):
            return False
        # 头部残缺 → 只能紧跟母带里的前一条,单独播会缺字/没头没脑。
        # 波形证据(head_cut)比句法可靠:"He will never leave." 语法完整、
        # 句号结尾,但波形显示它切穿了 "He will never leave you" 的语流。
        # 句法证据(连词开头)同样算:「And he answers with love.」单独出现
        # 是悬空的续句 —— 此前本地的 FRAGMENT_START_RE 只拦一小撮词,
        # "And he…" 漏网,改用 atom_quality 的公共判据(同一概念一处判据)。
        #
        # 两种残缺要求的「前一条」不是一回事:波形切穿要**紧挨着**(0.35s)才
        # 补得回首词;句法碎片语流完整,普通续接(18s)即可。
        if (head_fragment_reason({"head_cut": atom.head_cut, "text": text})
                and not continuation):
            return False
        # 语速上界:>3.5 词/秒的原子睡前听不清。上界历史上实测(4.0)无误杀,
        # 当年误判的是**下界**(慢读是设计)—— 这里只设上界,不碰下界。
        if atom.duration_sec > 0 and len(aq_words(text)) / atom.duration_sec > 3.5:
            return False
        if stutters_with(previous_atom, atom):
            return False
        if not addressee_compatible(previous_atom, atom):
            return False
        if slot_id not in {"COLD_OPEN", "OPEN"} and not matches_perspective(text, perspective):
            return False
        if reject_fragments and is_orphan_fragment(text) and not continuation:
            return False
        # 收尾可行性:切在句中的原子必须能被它的后继补完,而**后继本身也得合格**。
        # 补句链此前不做资格检查(为了把话说完就硬接),结果让复数人称的句子
        # 混进了单数人称的一期。收不干净的原子,干脆不选。
        if not closure_feasible(atom):
            return False
        return True

    def closure_feasible(atom: AtomRec) -> bool:
        cur, seen_ids = atom, {atom.id}
        for _ in range(3):
            if not needs_closure(cur):
                return True
            nxt = successor_of(atoms, cur)
            if nxt is None or nxt.id in used_ids or nxt.id in seen_ids:
                return False
            ntext = nxt.text or ""
            if text_is_duplicate(ntext, used_texts):
                return False
            if not matches_perspective(ntext, perspective):
                return False
            # 补句链会把后继**直接**接进节目,不再过 _eligible —— 所以后继
            # 自身的硬性判据必须在这里查。VO_PIPELINE 第 5 条记过一次同样的
            # 事(复数人称经补句链混进单数人称的一期),当时补了人称与指代,
            # 漏了语速:2026-08-12 实测「At the end of the day,」5.5 词/秒
            # 靠这条缝隙进了 11 期,每期被 C5 扣分。
            if nxt.duration_sec > 0 and len(aq_words(ntext)) / nxt.duration_sec > 3.5:
                return False
            if stutters_with(cur, nxt):
                return False
            # 悬空句只能由**同一句的延续**接上。后继若是大写开头的新句,
            # 补句链看似「说完了」,听感上那个念头始终悬着。
            if not completes_dangling(cur.text or "", ntext):
                return False
            if not addressee_compatible(cur, nxt):
                return False
            seen_ids.add(nxt.id)
            cur = nxt
        return not needs_closure(cur)

    picked: list[AtomRec] = []
    remaining = list(candidates)
    streak_role, streak_len = role_streak
    slot_id_up = str(slot.get("id", "")).upper()
    while len(picked) < n and remaining:
        eligible = [a for a in remaining if _eligible(a)]
        if not eligible:
            break
        role_matched = [a for a in eligible if a.role in roles or any(r in a.tags for r in roles)]
        # In the body, source adjacency may override the requested role: the
        # role is an arc preference, while preserving a sentence/passage is a
        # correctness requirement. Terminal slots remain role-strict.
        # 终末槽位(祝福/收尾)**绝不退化到任意角色**:祝福位上放呼吸提示,
        # 比这一期少一句祝福糟得多。宁可空着让审计报出来。
        if terminal_phase:
            if not role_matched:
                break
            pool = role_matched
        else:
            pool = eligible

        def _extras(candidate: AtomRec) -> float:
            extra = 0.0
            if slot_id_up == "CLOSE":
                extra += strong_close_score(candidate.text)
            # BLESS 靠 bless 标签回退时会抢强结尾原子(CLOSE 的唯一供给
            # 只有 14 条文案)。祝福位上避开强结尾形态,把它们留给 CLOSE。
            if slot_id_up == "BLESS" and is_strong_close_text(candidate.text or ""):
                extra -= 6.0
            # 同角色连跑 >4 条行文单调(scripture 连读 7 条像在念经文清单)。
            # 只是偏好,不是正确性 —— 续接 +12 仍能压过它。
            if candidate.role == streak_role:
                if streak_len >= 4:
                    extra -= 8.0
                elif streak_len == 3:
                    extra -= 3.0
            return extra

        a = max(
            pool,
            key=lambda candidate: score_atom(
                candidate, roles, boost_tags, prefer, prefer_min,
                previous_atom=previous_atom,
                continuation_max_gap_sec=continuity_gap,
            ) + _extras(candidate),
        )
        if a.role == streak_role:
            streak_len += 1
        else:
            streak_role, streak_len = a.role, 1
        picked.append(a)
        used_ids.add(a.id)
        remaining = [candidate for candidate in remaining if candidate.id != a.id]
        text = a.text or (_atom_sidecar_text(a.path) or "")
        norm = normalize_atom_text(text)
        if norm:
            used_texts.add(norm)
        if is_cta_text(text):
            cta_count += 1
        previous_atom = a

        # —— 句子必须说完 ——
        # 一条原子若切在句中(末尾没有句末标点),后面必须紧跟它在母带里的
        # 下一条,否则听众听到的是半句话。2026-08-05 的成片里出现过:
        #   「…the Spirit of God dwells in you and he does not」→ 下一句换了话题
        # 续接此前只向后校验(这条能否接住上一条),从不向前保证(这条能否
        # 被接住)。补上正向闭合。
        guard = 0
        while needs_closure(previous_atom) and guard < 3:
            guard += 1
            nxt = successor_of(atoms, previous_atom)
            if nxt is None or nxt.id in used_ids:
                break
            picked.append(nxt)
            used_ids.add(nxt.id)
            remaining = [c for c in remaining if c.id != nxt.id]
            nt = normalize_atom_text(nxt.text or "")
            if nt:
                used_texts.add(nt)
            if nxt.role == streak_role:
                streak_len += 1
            else:
                streak_role, streak_len = nxt.role, 1
            previous_atom = nxt
    return picked


def list_music(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in paths:
        root = root.expanduser()
        if not root.exists():
            continue
        files.extend(root.rglob("*.mp3"))
    # de-prioritize obvious vocal folder names
    instr = [p for p in files if "vocal" not in str(p).lower()]
    return instr if instr else files


def bed_layout(selected: list[Path], durations: list[float],
               crossfade: float, target_sec: float, looped: bool) -> list[dict]:
    """每首曲子在成品床上的起止秒数。

    视觉线需要它:VO 结束后还有四十多分钟只有音乐,那一段的画面事件只能
    锁到音乐的节拍上,而换曲会换速度 —— 不知道曲目边界就无法重新锁相。
    此前 session.json 只记了三个电平参数,曲目信息全丢了。

    acrossfade 的时间学:相邻两首重叠 crossfade 秒,所以第 i 首的起点是
    前面所有时长之和减去 i 段淡入。单曲循环则按整首时长重复。
    """
    rows: list[dict] = []
    if looped and selected:
        d = durations[0]
        k = 0
        while k * d < target_sec:
            rows.append({"path": str(selected[0]), "name": selected[0].name,
                         "start_sec": round(k * d, 3),
                         "end_sec": round(min((k + 1) * d, target_sec), 3),
                         "duration_sec": round(d, 3), "loop_index": k,
                         "crossfade_in_sec": 0.0})
            k += 1
        return rows
    cur = 0.0
    for i, (p, d) in enumerate(zip(selected, durations)):
        rows.append({"path": str(p), "name": p.name,
                     "start_sec": round(cur, 3),
                     "end_sec": round(min(cur + d, target_sec), 3),
                     "duration_sec": round(d, 3),
                     "crossfade_in_sec": 0.0 if i == 0 else round(crossfade, 3)})
        cur += d - (crossfade if i < len(selected) - 1 else 0.0)
        if cur >= target_sec:
            break
    return rows


def build_music_bed(
    tracks: list[Path],
    target_sec: float,
    out_path: Path,
    *,
    crossfade: float = 8.0,
    layout_out: list | None = None,
    avoid: set[str] | None = None,
) -> Path:
    if not tracks:
        raise RuntimeError("No music tracks available for bed")
    random.shuffle(tracks)
    if avoid:
        # 近期用过的曲目排到队尾而不是丢掉:曲库万一不够长,宁可重曲也不能没床
        fresh = [t for t in tracks if t.name not in avoid]
        stale = [t for t in tracks if t.name in avoid]
        if stale:
            print(f"  [music] 回避近期用过的 {len(stale)} 首(曲库剩 {len(fresh)} 首可选)")
        tracks = fresh + stale
    selected: list[Path] = []
    durations: list[float] = []
    total = 0.0
    for t in tracks:
        d = probe_duration(t)
        if d < 30:
            continue
        selected.append(t)
        durations.append(d)
        total += d - (crossfade if len(selected) > 1 else 0)
        if total >= target_sec + 30:
            break
    if not selected:
        selected = tracks[:8]
        durations = [probe_duration(t) for t in selected]

    # Use acrossfade chain for 2+; simple concat if one
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if layout_out is not None:
        layout_out.extend(bed_layout(selected, durations, crossfade,
                                     target_sec, looped=len(selected) == 1))
    if len(selected) == 1:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", str(selected[0]),
            "-t", f"{target_sec:.2f}",
            "-ac", "2", "-ar", "44100",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(out_path),
        ]
        r = _run(cmd)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-500:])
        return out_path

    # 单次 filter_complex 串太多 acrossfade 会又慢又脆,所以每批最多 BATCH 首。
    # 但**不能直接截断**:曲库中位时长 3.2 分钟,12 首减去交叉淡入只有 36.6 分钟,
    # 而节目要填到 60 分钟乃至 2 小时 —— 截断会让床静默地短一大截,
    # 而 ffmpeg 的 -t 只能截短、不会补长,失败时毫无提示。
    # 改为分批构建再把批次之间同样用交叉淡入衔接;布局公式不变,
    # 因为每个接缝用的都是同一个 crossfade。
    BATCH = 12
    if len(selected) > BATCH:
        tmp_dir = out_path.parent / f".{out_path.stem}_parts"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []
        for i in range(0, len(selected), BATCH):
            chunk = selected[i:i + BATCH]
            part = tmp_dir / f"part{i//BATCH:02d}.mp3"
            build_music_bed(chunk, sum(durations[i:i + BATCH]) + 60.0, part,
                            crossfade=crossfade)
            parts.append(part)
        try:
            build_music_bed(parts, target_sec, out_path, crossfade=crossfade)
        finally:
            for p in parts:
                p.unlink(missing_ok=True)
            tmp_dir.rmdir()
        return out_path

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for p in selected:
        cmd += ["-i", str(p)]
    n = len(selected)
    if n == 2:
        fc = f"[0:a][1:a]acrossfade=d={crossfade}:c1=tri:c2=tri[out]"
    else:
        parts = []
        prev = "[0:a]"
        for i in range(1, n):
            cur = f"[{i}:a]"
            outlab = "[out]" if i == n - 1 else f"[cf{i}]"
            parts.append(f"{prev}{cur}acrossfade=d={crossfade}:c1=tri:c2=tri{outlab}")
            prev = f"[cf{i}]"
        fc = ";".join(parts)
    cmd += [
        "-filter_complex", fc, "-map", "[out]",
        "-t", f"{target_sec:.2f}",
        "-ac", "2", "-ar", "44100",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]
    r = _run(cmd)
    if r.returncode != 0:
        # fallback: concat demuxer without crossfade
        lst = out_path.with_suffix(".txt")
        lst.write_text("".join(f"file '{p}'\n" for p in selected), encoding="utf-8")
        cmd2 = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(lst),
            "-t", f"{target_sec:.2f}",
            "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k",
            str(out_path),
        ]
        r2 = _run(cmd2)
        if r2.returncode != 0:
            raise RuntimeError(r.stderr[-800:] + "\n" + r2.stderr[-400:])
    return out_path


VO_CACHE = Path.home() / "Studio/Workspace/temp/sg/vo_cache"


def wav_seconds(p: Path) -> float:
    """从 RIFF 头读时长 —— 不起 ffprobe 进程。

    一期要量两百多个片段,每次一个 ffprobe 就是十几秒纯开销。
    """
    try:
        with p.open("rb") as fh:
            head = fh.read(64)
        if head[:4] != b"RIFF":
            return 0.0
        byte_rate = int.from_bytes(head[28:32], "little")
        size = p.stat().st_size - 44
        return size / byte_rate if byte_rate else 0.0
    except Exception:
        return 0.0


def _silence_piece(sec: float, sample_rate: int) -> Path:
    """静音片段按时长(取整到 10ms)缓存复用。

    一期 268 次 ffmpeg 调用里有 142 次只是在生成静音,而静音只和「多长」有关,
    与是哪一期无关 —— 缓存后批量出片几乎不再为它花时间。
    """
    key = round(max(0.0, sec), 2)
    VO_CACHE.mkdir(parents=True, exist_ok=True)
    p = VO_CACHE / f"sil_{sample_rate}_{key:.2f}.wav"
    if not p.exists():
        _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
              "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono",
              "-t", f"{key:.3f}", str(p)])
    return p


def _atom_piece(src: Path, atempo: float, sample_rate: int) -> Path:
    """变速后的原子片段缓存。

    同一条原子在多期里会被反复用到(冷却窗口之外就能重来),而变速结果只取决于
    (原子, atempo, 采样率)。批量出片时第一期填满缓存,之后几乎命中。
    """
    VO_CACHE.mkdir(parents=True, exist_ok=True)
    stamp = int(src.stat().st_mtime)     # 原子被重切过就自动失效
    p = VO_CACHE / f"{src.stem}_{sample_rate}_{atempo:.4f}_{stamp}.wav"
    if p.exists() and p.stat().st_size > 44:
        return p
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(src), "-ac", "1", "-ar", str(sample_rate)]
    if abs(atempo - 1.0) > 0.001:
        cmd += ["-af", f"atempo={atempo:.4f}"]
    cmd.append(str(p))
    r = _run(cmd)
    if r.returncode != 0 or not p.exists():
        raise RuntimeError(f"atom piece fail {src.name}: {r.stderr[-300:]}")
    return p


def build_vo_track(
    timeline: list[tuple[str, Path | float, float]],
    out_path: Path,
    *,
    sample_rate: int = 44100,
    atempo: float = 1.0,
    marks_out: list[dict] | None = None,
) -> tuple[Path, float]:
    """timeline items: (kind, path_or_silence_sec, pad_after). Returns path, duration.

    atempo < 1.0 slightly slows speech (e.g. 0.93) for a calmer prayer pace.

    marks_out 收每条原子在**成品轨**上的真实起止秒数 —— 字幕只能用它。
    plan 里的 start_sec 是编排时的估算(变速与留白折算不一致),实测与成品
    差了 1.8 分钟,拿去打字幕会整体错位。
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    piece_files: list[Path] = []
    # ffmpeg atempo only accepts 0.5–2.0
    atempo = max(0.5, min(2.0, float(atempo)))
    cursor = 0.0

    for i, (kind, payload, pad_after) in enumerate(timeline):
        if kind == "silence":
            piece = _silence_piece(float(payload), sample_rate)
        else:
            piece = _atom_piece(Path(str(payload)), atempo, sample_rate)
        dur = wav_seconds(piece)
        if kind == "atom" and marks_out is not None:
            marks_out.append({"index": i, "start_sec": round(cursor, 3),
                              "end_sec": round(cursor + dur, 3),
                              "src": str(payload)})
        cursor += dur
        piece_files.append(piece)
        if pad_after and pad_after > 0.05:
            pad = _silence_piece(float(pad_after), sample_rate)
            piece_files.append(pad)
            cursor += wav_seconds(pad)

    parts_dir = out_path.parent / "_parts"
    parts_dir.mkdir(exist_ok=True)

    # concat
    lst = parts_dir / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in piece_files), encoding="utf-8")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    return out_path, probe_duration(out_path)


def _srt_time(sec: float) -> str:
    h, rem = divmod(max(0.0, sec), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"


def subtitle_typography(text: str, *, continues_prev: bool) -> str:
    """字幕排版修正 —— VO_PIPELINE 明确许可的两项:标点与大小写。

    **只动字幕文本,不动音频、不加词、不改词。** 采集按语音停顿切分,一句话
    常被切成两条原子,于是成片字幕出现「set apart for restoration.」
    「tonight i will rest」这种小写开头、无句末标点的条目 —— 语义没错,
    读起来却像残句。

    两条规则,都要求**有把握**才动:
      · 句首字母大写:仅当这条不是紧接前一条的续句时(续句本就该小写)
      · 补句末标点:仅当这条不被后继补完时,且末尾不是逗号等待续接
    拿不准就原样保留 —— 字幕宁可朴素,不可自作主张。
    """
    t = text.strip()
    if not t:
        return t
    # 英文第一人称代词恒为大写,这条没有判断余地(whisper 常转写成小写 i)
    t = re.sub(r"\bi\b", "I", t)
    if not continues_prev and t[:1].islower():
        t = t[0].upper() + t[1:]
    return t


def build_srt(atoms: list[dict], min_on: float = 1.2, lead: float = 0.10) -> str:
    """一条原子 = 一条字幕。

    时间用 vo_start_sec / vo_end_sec —— 那是**成品轨**上的真实位置。
    plan 里的 start_sec 是编排估算,与成品差了将近两分钟,拿去打字幕会整体错位。

    短句给一个最短驻留(默认 1.2s),否则一闪而过;但绝不越过下一句的起点,
    宁可提前消失也不能压住下一句。
    """
    out: list[str] = []
    n = 0
    for i, p in enumerate(atoms):
        prev = atoms[i - 1] if i else None
        cont = bool(prev
                    and prev.get("source_master") == p.get("source_master")
                    and int(p.get("source_sequence_index", -1))
                    == int(prev.get("source_sequence_index", -2)) + 1)
        text = subtitle_typography(p.get("text") or "", continues_prev=cont)
        s = p.get("vo_start_sec")
        e = p.get("vo_end_sec")
        if not text or s is None or e is None:
            continue
        s = max(0.0, float(s) - lead)
        e = float(e)
        if e - s < min_on:
            e = s + min_on
        nxt = atoms[i + 1].get("vo_start_sec") if i + 1 < len(atoms) else None
        if nxt is not None:
            e = min(e, float(nxt) - 0.08)
        if e <= s:
            continue
        n += 1
        out.append(f"{n}\n{_srt_time(s)} --> {_srt_time(e)}\n{text}\n")
    return "\n".join(out)


def duck_mix(
    music: Path,
    vo: Path,
    out_path: Path,
    *,
    bed_volume_db: float = -16.0,
    ducking_db: float = -18.0,
    vo_gain_db: float = 3.0,
    duck_ratio: float = 12.0,
    duck_release_ms: int = 700,
) -> Path:
    """Mix music bed under VO with a quiet base bed + deeper duck while speech is present.

    bed_volume_db: constant music level (negative = quieter bed overall).
    ducking_db: how hard to pull bed under active speech (more negative = deeper duck).
    vo_gain_db: slight speech lift so VO stays intelligible over a soft bed.
    duck_ratio / duck_release_ms: 压缩比与释放。默认值 12:1 / 700ms 是
    原子时代冻结参数(已发布期次的声音,不动);2026-08-17 人耳审听发现
    这组参数在句间 4s 停顿下音乐每句涨落 13-16 dB(「抽吸」),分子
    管线改传 4:1 / 2200ms —— 压得浅、放得慢,音乐保持连续空间感。
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bed = float(bed_volume_db)
    duck = float(ducking_db)
    vo_g = float(vo_gain_db)
    # How much further to pull bed down when VO is loud
    extra_duck = max(0.0, bed - duck)  # e.g. bed=-16, duck=-18 → 2 dB more under speech

    # [0]=music [1]=vo
    # 1) lower bed base  2) sidechain compress when VO present  3) lift VO  4) amix
    # aformat keeps mono VO compatible with stereo bed
    sc = (
        f"[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo,volume={bed:.1f}dB[m0];"
        f"[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo,volume={vo_g:.1f}dB,asplit=2[voc][sc];"
        f"[m0][sc]sidechaincompress="
        f"threshold=0.012:ratio={duck_ratio:g}:attack=30"
        f":release={int(duck_release_ms)}:makeup=1:knee=2.5"
        f"[ducked];"
        f"[ducked]volume={-extra_duck:.1f}dB[m];"
        f"[m][voc]amix=inputs=2:duration=longest:dropout_transition=2:normalize=0,"
        f"alimiter=limit=0.95:attack=5:release=50[out]"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(music), "-i", str(vo),
        "-filter_complex", sc, "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]
    r = _run(cmd)
    if r.returncode == 0 and out_path.exists():
        return out_path

    # Fallback: fixed bed at duck level (safer quieter bed) + lifted VO
    bed_db = min(bed, duck)
    fc = (
        f"[0:a]aformat=channel_layouts=stereo,volume={bed_db:.1f}dB[m];"
        f"[1:a]aformat=channel_layouts=stereo,volume={vo_g:.1f}dB[v];"
        f"[m][v]amix=inputs=2:duration=longest:dropout_transition=2:normalize=0,"
        f"alimiter=limit=0.95:attack=5:release=50[out]"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(music), "-i", str(vo),
        "-filter_complex", fc, "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError("duck mix failed: " + (r.stderr or "")[-600:])
    return out_path


# 停顿曲线（2026-08-06 用户令）：稳在 4–6s，后段逐渐延伸到 10s。
PAUSE_EARLY_SEC = 4.0     # 开场：引导语密一些，听者还醒着
PAUSE_MID_SEC = 6.0       # 中段稳态
PAUSE_LATE_SEC = 10.0     # 后段：已经在入睡，句子之间可以很空
PAUSE_WORD_TILT = 0.06    # 每词微调上限系数（长句略多留白，但不主导）
PAUSE_TILT_CLAMP = (0.88, 1.14)


def speech_pad(
    duration_sec: float,
    pad_cfg: float,
    *,
    pad_ge_speech: bool = True,
    pad_speech_ratio: float = 1.0,
    words: int | None = None,
    progress: float = 0.0,
) -> float:
    """Pause after a phrase, as a function of **session position**, not duration.

    ⚠ 这是 2026-08-06 用户报「有时空隙过大，有时又很紧」的修复点。

    旧规则是「空白 ≥ 说话时长」。它在语速恒定时是合理的，但这条线**刻意不设
    语速门禁**（VO_PIPELINE：「'Take a deep breath in.' 读满 9 秒是设计」），
    实测语速跨度 0.56–4.66 词/秒、整整八倍。于是时长根本不代表"说了多少"：

        "Lord." 占 7.51s（VO_PIPELINE 自己举的例）→ 换来 ≥7.5s 停顿
        一句 3.7 词/秒的完整句                    → 相对内容量只配到很短的停顿

    **规则被自己反转了：说得越少，后面越空。** qc08 实测间隙标准差 5.79s、
    中位 2.62s、最大 33.5s，就是这么来的。

    新规则：停顿由**节目进度**决定（4 → 6 → 10 秒），词数只做 ±14% 的微调，
    永远不让它主导。这样同一位置的停顿彼此可比，而整期有一条从紧到空的曲线
    ——那正是助眠该有的形状，也不再需要靠原子时长这个坏代理。

    `pad_cfg` 仍是下限（语法里某些槽位要求更长的停顿，例如祝祷前）。
    `pad_ge_speech` / `pad_speech_ratio` 保留但不再参与计算：旧调用不会报错，
    而行为统一到新曲线（留着签名是为了 grammar JSON 不必同步改）。
    """
    p = min(1.0, max(0.0, float(progress)))
    # 两段线性：前半 4→6，后半 6→10。后段抬得更快，入睡曲线不是直线。
    if p <= 0.5:
        base = PAUSE_EARLY_SEC + (PAUSE_MID_SEC - PAUSE_EARLY_SEC) * (p / 0.5)
    else:
        base = PAUSE_MID_SEC + (PAUSE_LATE_SEC - PAUSE_MID_SEC) * ((p - 0.5) / 0.5)
    if words:
        tilt = 1.0 + (int(words) - 8) * PAUSE_WORD_TILT / 8.0
        base *= min(PAUSE_TILT_CLAMP[1], max(PAUSE_TILT_CLAMP[0], tilt))
    return max(float(pad_cfg), base)


def source_continuation_pad(
    previous: AtomRec,
    current: AtomRec,
    *,
    tempo_scale: float,
    max_pad_sec: float,
) -> float:
    """Restore a compact version of the original gap between adjacent atoms."""
    source_gap = max(0.0, current.t_start - previous.t_end)
    return min(max_pad_sec, max(0.12, source_gap * tempo_scale))


def audit_plan_content(plan: list[dict], grammar: dict) -> dict:
    """Fail-fast content QA for the assembled prayer before audio rendering."""
    policy = grammar.get("content_policy") or {}
    continuity_gap = float(policy.get("continuation_max_gap_sec", 18.0))
    max_cta = int(policy.get("max_cta_per_session", 1))
    seen: set[str] = set()
    duplicates: list[str] = []
    orphan_fragments: list[str] = []
    misplaced_closes: list[str] = []
    ctas: list[str] = []
    perspective = str(policy.get("perspective") or "any").lower()
    perspective_violations: list[str] = []
    addressee_violations: list[str] = []
    previous: dict | None = None
    source_switch_count = 0
    source_continuation_count = 0

    for item in plan:
        if item.get("type") != "atom":
            previous = None          # 静默是合法的模式切换点
            continue
        # 「你」的指代在相邻两句间硬切 —— 听者当场失去指代对象
        if previous is not None:
            a, b = previous.get("addressee", "neutral"), item.get("addressee", "neutral")
            if a != b and "neutral" not in (a, b):
                addressee_violations.append(
                    f"{a}→{b}: {str(previous.get('text',''))[:34]} ‖ "
                    f"{str(item.get('text',''))[:34]}")
        text = str(item.get("text") or "").strip()
        norm = normalize_atom_text(text)
        if norm in seen:
            duplicates.append(text)
        elif norm:
            seen.add(norm)
        if is_cta_text(text):
            ctas.append(text)
        if str(item.get("slot", "")).upper() not in {"COLD_OPEN", "OPEN"}:
            if not matches_perspective(text, perspective):
                perspective_violations.append(text)
        continues = False
        if previous is not None and previous.get("source_master") == item.get("source_master"):
            gap = float(item.get("source_t_start") or 0) - float(previous.get("source_t_end") or 0)
            adjacent = int(item.get("source_sequence_index", -1)) == int(
                previous.get("source_sequence_index", -2)
            ) + 1
            continues = adjacent and MAX_OVERLAP <= gap <= continuity_gap
            if continues:
                source_continuation_count += 1
        elif previous is not None:
            source_switch_count += 1
        if is_orphan_fragment(text) and not continues:
            orphan_fragments.append(text)
        if item.get("role") == "close" and str(item.get("slot", "")).upper() not in {"BLESS", "CLOSE"}:
            misplaced_closes.append(text)
        previous = item

    errors: list[str] = []
    if duplicates:
        errors.append(f"duplicate texts: {len(duplicates)}")
    if orphan_fragments:
        errors.append(f"orphan fragments: {len(orphan_fragments)}")
    if len(ctas) > max_cta:
        errors.append(f"CTA count {len(ctas)} exceeds {max_cta}")
    if misplaced_closes:
        errors.append(f"closes before terminal phase: {len(misplaced_closes)}")
    if perspective_violations:
        errors.append(f"perspective violations: {len(perspective_violations)}")
    if addressee_violations:
        errors.append(f"addressee 硬切: {len(addressee_violations)}")
    atom_items = [p for p in plan if p.get("type") == "atom"]
    final_text = str(atom_items[-1].get("text") or "") if atom_items else ""
    if not is_strong_close_text(final_text):
        errors.append("final atom is not a recognized closing line")
    return {
        "ok": not errors,
        "errors": errors,
        "atom_count": sum(p.get("type") == "atom" for p in plan),
        "unique_text_count": len(seen),
        "cta_count": len(ctas),
        "source_switch_count": source_switch_count,
        "source_continuation_count": source_continuation_count,
        "duplicate_texts": duplicates,
        "orphan_fragments": orphan_fragments,
        "misplaced_closes": misplaced_closes,
        "perspective": perspective,
        "perspective_violations": perspective_violations,
        "addressee_violations": addressee_violations,
        "final_text": final_text,
    }


def render_text_script(plan: list[dict], *, episode_id: str, theme: str, audit: dict) -> str:
    """Render a readable, atom-only script; headings are non-spoken metadata."""
    phases: dict[str, list[str]] = {"Opening": [], "Prayer": [], "Closing": []}
    buffers: dict[str, list[str]] = {name: [] for name in phases}
    last_source: dict[str, str | None] = {name: None for name in phases}

    def flush(phase: str) -> None:
        if buffers[phase]:
            phases[phase].append(" ".join(buffers[phase]))
            buffers[phase] = []

    for item in plan:
        slot = str(item.get("slot", "")).upper()
        phase = "Opening" if slot in {"COLD_OPEN", "OPEN"} else "Closing" if slot in {"BLESS", "CLOSE"} else "Prayer"
        if item.get("type") != "atom":
            flush(phase)
            last_source[phase] = None
            continue
        source = str(item.get("source_master") or "")
        if last_source[phase] is not None and source != last_source[phase]:
            flush(phase)
        text = " ".join(str(item.get("text") or "").split())
        if text:
            buffers[phase].append(text)
        last_source[phase] = source
    for phase in phases:
        flush(phase)

    atom_items = [p for p in plan if p.get("type") == "atom"]
    spoken = " ".join(str(p.get("text") or "") for p in atom_items)
    word_count = len(re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", spoken))
    sources = sorted({str(p.get("source_master") or "") for p in atom_items if p.get("source_master")})
    lines = [
        f"# {episode_id}",
        "",
        f"Theme: `{theme}`  ",
        f"Perspective: `{audit.get('perspective')}`  ",
        f"Atoms: `{audit.get('atom_count')}`  ",
        f"Words: `{word_count}`  ",
        f"QA: `{'PASS' if audit.get('ok') else 'FAIL'}`",
    ]
    for phase in ("Opening", "Prayer", "Closing"):
        lines.extend(["", f"## {phase}", ""])
        lines.append("\n\n".join(phases[phase]) or "—")
    lines.extend(["", "## Atom provenance", ""])
    lines.extend(
        f"- `{item.get('id')}` — `{Path(str(item.get('source_master') or '')).name}`"
        for item in atom_items
    )
    lines.extend(["", "## Source masters", ""])
    lines.extend(f"- `{Path(source).name}`" for source in sources)
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atoms-root", type=Path, default=DEFAULT_ATOMS)
    ap.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--theme", default="night_of_peace")
    ap.add_argument("--perspective", choices=["singular", "plural"], default="singular")
    ap.add_argument("--minutes", type=float, default=18.0, help="Target total session minutes (VO+rest+bed)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--episode-id", default=None)
    ap.add_argument("--with-video", action="store_true", help="Also render slow-loop YouTube mp4")
    ap.add_argument("--video-speed", type=float, default=0.125, help="Video playback speed (default 0.125 = 8× slower)")
    ap.add_argument("--video-dir", type=Path, default=DEFAULT_VIDEO_DIR)
    ap.add_argument("--plan-only", action="store_true", help="Assemble and audit content without rendering audio")
    ap.add_argument("--no-score-gate", action="store_true",
                    help="VO 检测门降级为只报不拦(调试/复现旧片用)")
    ap.add_argument("--no-history", action="store_true",
                    help="不记入出片历史(试排/回归测试用,免得污染 cooldown)")
    ap.add_argument("--plan-output", type=Path, default=None, help="Write full atom plan JSON and a readable Markdown script")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    man = args.atoms_root / "manifest.json"
    if not man.exists():
        print(f"Missing manifest: {man}\nRun harvest_atoms.py first.", file=sys.stderr)
        return 1

    atoms = load_atoms(man)
    grammar = load_grammar(args.grammar)
    grammar.setdefault("content_policy", {})["perspective"] = args.perspective
    if not atoms:
        print("No atoms loaded", file=sys.stderr)
        return 1

    cool = int((grammar.get("cooldown") or {}).get("same_atom_days", 0) or 0)
    RECENT.clear()
    RECENT.update(load_recent(cool))
    if RECENT:
        print(f"[cooldown] 近 {cool} 期用过 {len(RECENT)} 条原子,本期回避")

    themes = grammar.get("themes") or {}
    boost = list((themes.get(args.theme) or {}).get("boost_tags") or [])
    used: set[str] = set()
    timeline: list[tuple[str, Path | float, float]] = []
    plan: list[dict] = []
    cursor = 0.0  # absolute timeline for subtitles (post-atempo units)

    mb = grammar.get("music_bed") or {}
    atempo = float(grammar.get("vo_atempo") or 1.0)
    pad_ge = bool(grammar.get("pad_ge_speech", True))
    pad_ratio = float(grammar.get("pad_speech_ratio") or 1.0)
    policy = grammar.get("content_policy") or {}
    continuation_gap = float(policy.get("continuation_max_gap_sec", 18.0))
    continuation_pad_max = float(policy.get("continuation_pad_max_sec", 2.5))
    # slowed speech stretches wall-clock duration
    tempo_scale = 1.0 / max(0.5, min(2.0, atempo))
    used_texts: set[str] = set()
    previous_atom: AtomRec | None = None
    cta_count = 0
    # 跨槽位的同角色连跑计数 —— 选曲端据此避免 scripture 连读 5+ 条的单调感
    role_streak_state: list = ["", 0]

    def _atom_text(atom_path: Path) -> str | None:
        side = atom_path.with_suffix(".json")
        if side.exists():
            try:
                return json.loads(side.read_text(encoding="utf-8")).get("text")
            except Exception:
                return None
        return None

    # Ensure COLD_OPEN is first if grammar defines cold_open but slots lack it
    slots = list(grammar.get("slots") or [])
    co = grammar.get("cold_open") or {}
    if co.get("enabled", True) and not any(
        s.get("fixed_cold_open") or str(s.get("id", "")).upper() == "COLD_OPEN" for s in slots
    ):
        slots.insert(0, {
            "id": "COLD_OPEN",
            "roles": ["open"],
            "pick": 1,
            "fixed_cold_open": True,
            "pad_after_sec": float(co.get("pad_after_sec") or 2.0),
        })

    def append_atom(atom: AtomRec, slot_id: str, pad_cfg: float) -> None:
        nonlocal cursor, previous_atom, cta_count
        # If this atom directly follows the prior atom in its master, undo the
        # synthetic sleep pause between them and restore source-like phrasing.
        if (
            previous_atom is not None
            and timeline
            and plan
            and timeline[-1][0] == "atom"
            and directly_continues(previous_atom, atom, continuation_gap)
        ):
            compact_pad = source_continuation_pad(
                previous_atom, atom,
                tempo_scale=tempo_scale,
                max_pad_sec=continuation_pad_max,
            )
            kind, payload, old_pad = timeline[-1]
            timeline[-1] = (kind, payload, compact_pad)
            plan[-1]["pad_after_sec"] = compact_pad
            cursor += compact_pad - float(old_pad)

        speech_dur = float(atom.duration_sec) * tempo_scale
        # progress 用 cursor / 目标总长：停顿要跟"听者听到哪儿了"走，
        # 不是跟第几个原子走（原子长短差十倍，计数不代表时间）。
        # 分母必须是**本期真实目标** vo_goal，不能用 args.minutes(固定 18)：
        # vo_goal 从语法抽 [10,22] 分钟，抽到 10 分钟时若按 18 算，
        # 节目结束在 progress≈0.55，深度停顿段(6→10s)整段没走到 ——
        # 后半程密度降不下来就是这么来的。
        pad = speech_pad(
            speech_dur, pad_cfg, pad_ge_speech=pad_ge, pad_speech_ratio=pad_ratio,
            words=len(str(atom.text or "").split()) or None,
            progress=cursor / max(60.0, vo_goal),
        )
        text = atom.text or _atom_text(atom.path)
        timeline.append(("atom", atom.path, pad))
        plan.append({
            "slot": slot_id,
            "type": "atom",
            "id": atom.id,
            "role": atom.role,
            "path": str(atom.path),
            "duration_sec": speech_dur,
            "source_duration_sec": atom.duration_sec,
            "pad_after_sec": pad,
            "tags": atom.tags,
            "text": text,
            "addressee": atom.addressee,
            "head_cut": atom.head_cut,
            "tail_cut": atom.tail_cut,
            "source_master": atom.source_master,
            "source_t_start": atom.t_start,
            "source_t_end": atom.t_end,
            "source_sequence_index": atom.sequence_index,
            "start_sec": cursor,
            "end_sec": cursor + speech_dur,
        })
        cursor += speech_dur + pad
        norm = normalize_atom_text(text or "")
        if norm:
            used_texts.add(norm)
        if is_cta_text(text or ""):
            cta_count += 1
        if atom.role == role_streak_state[0]:
            role_streak_state[1] += 1
        else:
            role_streak_state[0], role_streak_state[1] = atom.role, 1
        previous_atom = atom

    def process_slots(slot_group: list[dict], *, terminal_phase: bool = False) -> None:
        nonlocal cursor, previous_atom
        for slot in slot_group:
            picks = select_for_slot(
                atoms,
                slot,
                used_ids=used,
                boost_tags=boost,
                grammar=grammar,
                used_texts=used_texts,
                previous_atom=previous_atom,
                cta_count=cta_count,
                terminal_phase=terminal_phase,
                role_streak=(role_streak_state[0], role_streak_state[1]),
            )
            pad_cfg = float(slot.get("pad_after_sec") or co.get("pad_after_sec") or 1.5)
            for pick in picks:
                if isinstance(pick, float):
                    timeline.append(("silence", pick, 0.0))
                    plan.append({"slot": slot["id"], "type": "silence", "sec": pick, "start_sec": cursor})
                    cursor += float(pick)
                    previous_atom = None
                else:
                    append_atom(pick, str(slot["id"]), pad_cfg)
                    pad_cfg = max(1.0, pad_cfg * 0.85)

    # 本期 VO 目标必须在**出第一条原子之前**定下来:append_atom 的停顿曲线
    # 以它为进度分母。原先在 body 处理完才抽,曲线只能拿 args.minutes 凑数。
    vo_target_min = grammar.get("target_vo_minutes") or [10, 18]
    if isinstance(vo_target_min, list):
        vo_goal = random.uniform(float(vo_target_min[0]), float(vo_target_min[1])) * 60.0
    else:
        vo_goal = float(vo_target_min) * 60.0

    # REST_BEFORE_BLESS 必须归终末组:它是「祝福前的静默」,留在 body 里会被
    # 密度填充(FILL)插到它和 BLESS 之间 —— 静默名存实亡(10/10 期实测如此)。
    terminal_ids = {"REST_BEFORE_BLESS", "BLESS", "CLOSE"}
    body_slots = [s for s in slots if str(s.get("id", "")).upper() not in terminal_ids]
    terminal_slots = [s for s in slots if str(s.get("id", "")).upper() in terminal_ids]
    process_slots(body_slots)

    # Rough estimate current VO length from plan (speech + pads + rests)
    est = sum(
        (
            float(p["sec"])
            if p["type"] == "silence"
            else float(p.get("duration_sec") or 0) + float(p.get("pad_after_sec") or 0)
        )
        for p in plan
    )
    fill_roles = ["scripture", "poetic", "safety", "release", "deepen"]
    fi = 0
    fill_pad_cfg = 1.5
    max_fill_attempts = len(atoms)
    # —— 填充段的语音密度必须**低于**正片段 ——
    # T3 要求后半程比前半程更空(助眠曲线),而填充全落在后半。此前靠「每 N 条
    # 插一段定长休息」去凑,常数调了三轮:每 5 条 → 后半密度 1.14 被拦;
    # 每 3 条加随进度缩放 → 又掉到 0.23,被 T2 判太空。
    # 症结是拿「插入频率」这个间接量去控「密度」这个直接量。改成直接算:
    # 量出正片段的实际密度,再按目标比例反推每条填充后面该留多长。
    body_speech = sum(float(p.get("duration_sec") or 0)
                      for p in plan if p.get("type") == "atom")
    body_density = body_speech / max(1.0, cursor)
    fill_density_target = max(0.16, body_density * 0.72)
    max_fill_attempts = len(atoms)
    while est < vo_goal and fi < max_fill_attempts:
        fi += 1
        picks = select_for_slot(
            atoms,
            # 不再偏好长原子:prefer_min_sec 3.0 让填充系统性地挑更长的句子,
            # 语音变多而停顿不变,正是后半密度顶上去的直接原因。
            {"id": "FILL", "roles": fill_roles, "pick": 1, "prefer_min_sec": 2.0},
            used_ids=used,
            boost_tags=boost,
            grammar=grammar,
            used_texts=used_texts,
            previous_atom=previous_atom,
            cta_count=cta_count,
            terminal_phase=False,
            role_streak=(role_streak_state[0], role_streak_state[1]),
        )
        if not picks or isinstance(picks[0], float):
            break
        before = cursor
        # 取回**全部** picks:select_for_slot 可能为了补完半截句子而多带回
        # 后继原子,只取 picks[0] 会把补完的部分丢掉,半句话照样进片。
        for pick in picks:
            if isinstance(pick, float):
                continue
            append_atom(pick, "FILL", fill_pad_cfg)
            previous_atom = pick
        est += cursor - before
        # 这一轮加进来的语音,按目标密度反推该占多长的时间;不足的部分补静默。
        added_speech = sum(float(p.get("duration_sec") or 0) for p in plan
                           if p.get("type") == "atom"
                           and float(p.get("start_sec") or 0) >= before)
        want_span = added_speech / fill_density_target
        sil = want_span - (cursor - before)
        if sil >= 3.0:
            sil = min(sil, 45.0) * random.uniform(0.9, 1.1)
            timeline.append(("silence", sil, 0.0))
            plan.append({"slot": "FILL_REST", "type": "silence", "sec": sil, "start_sec": cursor})
            cursor += sil
            est += sil
            previous_atom = None

    # Blessing and close are always last; density fill can no longer continue
    # after an Amen or closing benediction.
    # 终末供给保卫:强结尾唯一文案仅 ~14 条,BLESS 靠 bless 标签回退时会吃掉
    # 同一批 close 原子,轮到 CLOSE 时无米下锅(实测 seed 9/10 成片没有结尾)。
    # 先试选 CLOSE 并预留其原子,选完 BLESS 再归还预留、正式选 CLOSE。
    close_slot = next((s for s in terminal_slots
                       if str(s.get("id", "")).upper() == "CLOSE"), None)
    reserved: set[str] = set()
    if close_slot is not None:
        trial = select_for_slot(
            atoms, close_slot,
            used_ids=set(used), boost_tags=boost, grammar=grammar,
            used_texts=set(used_texts), previous_atom=previous_atom,
            cta_count=cta_count, terminal_phase=True,
        )
        reserved = {a.id for a in trial if not isinstance(a, float)}
        used.update(reserved)
    process_slots([s for s in terminal_slots if s is not close_slot],
                  terminal_phase=True)
    used.difference_update(reserved)
    if close_slot is not None:
        # 祝福(you=听者)与收尾祷告(you=上帝)几乎必然切换指代,而 addressee
        # 门禁只认中性句或静默作为切换点 —— 于是 CLOSE 十有八九选不出原子,
        # 成片没有结尾(实测 8/10)。与 REST_BEFORE_BLESS 同一手法:改结构,
        # 插静默,不加隐藏规则。礼仪上祝祷与奉名结束之间本就该有停顿。
        if plan and plan[-1].get("type") == "atom" \
                and str(plan[-1].get("slot", "")).upper() == "BLESS":
            sil = random.uniform(4.0, 7.0)
            timeline.append(("silence", sil, 0.0))
            plan.append({"slot": "REST_BEFORE_CLOSE", "type": "silence",
                         "sec": sil, "start_sec": cursor})
            cursor += sil
            previous_atom = None
        process_slots([close_slot], terminal_phase=True)

    content_audit = audit_plan_content(plan, grammar)
    if not content_audit["ok"]:
        # 门禁失败时必须留下现场。只抛一行错误信息等于让人猜是哪几条原子
        # 触发的 —— 迭代时每次都要重跑一遍才能看到内容。
        tag = args.episode_id or "session"
        dump = args.out / tag / f"{tag}_FAILED_plan.json"
        dump.parent.mkdir(parents=True, exist_ok=True)
        dump.write_text(json.dumps({"audit": content_audit, "plan": plan},
                                   ensure_ascii=False, indent=1))
        print(f"\n❌ 内容门禁未过,方案已落盘: {dump}")
        for k in ("orphan_fragments", "perspective_violations",
                  "addressee_violations", "duplicates", "misplaced_closes"):
            v = content_audit.get(k) or []
            if v:
                print(f"  {k} ({len(v)}):")
                for item in v[:6]:
                    print(f"    · {str(item)[:96]}")
        raise SystemExit("content quality gate failed: "
                         + "; ".join(content_audit["errors"]))

    # —— VO 检测门(2026-08-10):时序/停顿 40 + 表述清晰度 30 + 行文结构 30,
    # ≥95 放行。判据细节见 vo_score.py;A 层判据与 qc_session 同源。
    from vo_score import PASS_SCORE, score_plan
    vo_verdict = score_plan({
        "episode_id": args.episode_id, "theme": args.theme, "seed": args.seed,
        "perspective": args.perspective, "audit": content_audit, "plan": plan,
    })
    print(f"[vo-score] {'✅' if vo_verdict['pass'] else '❌'} 总分 {vo_verdict['score']}"
          f"  (时序 {vo_verdict['timing']}/40 · 清晰 {vo_verdict['clarity']}/30"
          f" · 结构 {vo_verdict['structure']}/30)")
    for n in vo_verdict["notes"][:8]:
        print(f"    · {n}")
    if not vo_verdict["pass"] and not args.no_score_gate:
        tag = args.episode_id or "session"
        dump = args.out / tag / f"{tag}_FAILED_score.json"
        dump.parent.mkdir(parents=True, exist_ok=True)
        dump.write_text(json.dumps({"vo_score": vo_verdict, "plan": plan},
                                   ensure_ascii=False, indent=1))
        raise SystemExit(f"vo score gate failed: {vo_verdict['score']}"
                         f" < {PASS_SCORE:g} (现场: {dump})")

    if not args.no_history:
        # 记入历史,下一期据此回避。只记**两道门都过**的 —— 失败的方案不算出过片。
        record_episode(args.episode_id or "session",
                       [p["id"] for p in plan
                        if p.get("type") == "atom" and p.get("id")])
    if args.plan_only:
        atom_items = [p for p in plan if p.get("type") == "atom"]
        if args.plan_output:
            args.plan_output.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "episode_id": args.episode_id,
                "theme": args.theme,
                "seed": args.seed,
                "perspective": args.perspective,
                "audit": content_audit,
                "vo_score": vo_verdict,
                "plan": plan,
            }
            args.plan_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            md_path = args.plan_output.with_suffix(".md")
            md_path.write_text(
                render_text_script(
                    plan,
                    episode_id=args.episode_id or args.plan_output.stem,
                    theme=args.theme,
                    audit=content_audit,
                ),
                encoding="utf-8",
            )
        print(json.dumps({
            "audit": content_audit,
            "estimated_duration_sec": cursor,
            "first_atoms": [p.get("text") for p in atom_items[:8]],
            "last_atoms": [p.get("text") for p in atom_items[-8:]],
        }, ensure_ascii=False, indent=2))
        return 0

    eid = args.episode_id or f"sg_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = args.out / eid
    out_dir.mkdir(parents=True, exist_ok=True)

    vo_path = out_dir / f"{eid}_vo.mp3"
    print(
        f"Building VO track ({len(plan)} plan items, goal~{vo_goal/60:.1f} min, "
        f"atempo={atempo:.3f}, pad≥speech={pad_ge}, pad_ratio={pad_ratio:.2f})…"
    )
    vo_marks: list[dict] = []
    build_vo_track(timeline, vo_path, atempo=atempo, marks_out=vo_marks)
    vo_dur = probe_duration(vo_path)
    # 把真实时间轴配回 plan 里的原子(timeline 与 plan 的原子顺序一一对应),
    # 字幕、SRT、视觉击打全部以此为准。
    plan_atoms = [p for p in plan if p.get("type") == "atom"]
    for p, m in zip(plan_atoms, vo_marks):
        p["vo_start_sec"], p["vo_end_sec"] = m["start_sec"], m["end_sec"]
    if len(plan_atoms) != len(vo_marks):
        print(f"  ⚠️ 时间轴条数不符:plan {len(plan_atoms)} vs 渲染 {len(vo_marks)}")
    srt_path = out_dir / f"{eid}.srt"
    srt_path.write_text(build_srt(plan_atoms), encoding="utf-8")
    print(f"  字幕 {srt_path.name}({len(plan_atoms)} 条)")
    print(f"  VO duration: {vo_dur/60:.2f} min")

    target_total = max(args.minutes * 60.0, vo_dur + 30.0)
    # If VO shorter than target, append trailing rest silence on bed only (music continues)
    music_path = out_dir / f"{eid}_bed.mp3"
    print(f"Building music bed ~{target_total/60:.1f} min…")
    music_files = list_music(MUSIC_SOURCES)
    bed_tracks: list[dict] = []
    build_music_bed(music_files, target_total, music_path,
                    crossfade=float(mb.get("crossfade_sec", 8)),
                    layout_out=bed_tracks,
                    avoid=load_recent_tracks())
    if not args.no_history:
        record_tracks(eid, sorted({t["name"] for t in bed_tracks}))

    # If VO shorter, pad VO with trailing silence to match bed for mix alignment end
    if vo_dur < target_total - 1:
        pad_sec = target_total - vo_dur
        padded = out_dir / f"{eid}_vo_padded.mp3"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(vo_path),
            "-af", f"apad=pad_dur={pad_sec:.3f}",
            "-t", f"{target_total:.3f}",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(padded),
        ]
        r = _run(cmd)
        if r.returncode == 0:
            vo_for_mix = padded
        else:
            vo_for_mix = vo_path
    else:
        vo_for_mix = vo_path

    final_path = out_dir / f"{eid}_final_mix.mp3"
    bed_db = float(mb.get("bed_volume_db", -16))
    duck_db = float(mb.get("ducking_db", -18))
    vo_gain = float(mb.get("vo_gain_db", 3.0))
    print(f"Ducking mix (bed base {bed_db} dB, under-VO {duck_db} dB, VO +{vo_gain} dB)…")
    duck_mix(
        music_path, vo_for_mix, final_path,
        bed_volume_db=bed_db, ducking_db=duck_db, vo_gain_db=vo_gain,
    )

    meta = {
        "episode_id": eid,
        "theme": args.theme,
        "voice": "Locke",
        "grammar": grammar.get("id"),
        # 路径也要存:release_gate R2 与 repair_session 会**现场重算**内容门禁,
        # 只有 id 的话它们只能猜是默认语法 —— 换语法建的期次会被按错的规则复审。
        "grammar_path": str(args.grammar),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "vo_atempo": atempo,
        "pad_ge_speech": pad_ge,
        "pad_speech_ratio": pad_ratio,
        "music_bed": {
            "bed_volume_db": bed_db, "ducking_db": duck_db, "vo_gain_db": vo_gain,
            "crossfade_sec": float(mb.get("crossfade_sec", 8)),
            # 曲目表 —— 视觉线用它在 VO 结束后把画面锁到音乐节拍上。
            # 每首的 start_sec/end_sec 是在成品床上的位置(已计入交叉淡入重叠)。
            "tracks": bed_tracks,
        },
        # VO 之后只有音乐的那一段。视觉事件在这里必须换来源:
        # 前段用原子时间轴,后段用节拍网格。
        "vo_ends_sec": round(vo_dur, 3),
        "music_only_from_sec": round(vo_dur, 3),
        "vo_duration_sec": vo_dur,
        "total_duration_sec": probe_duration(final_path),
        "plan": plan,
        "paths": {
            "vo": str(vo_path),
            "bed": str(music_path),
            "final_mix": str(final_path),
            "srt": str(srt_path),
        },
        "atom_count_used": len([p for p in plan if p["type"] == "atom"]),
        "content_audit": content_audit,
        "vo_score": vo_verdict,
    }
    meta_path = out_dir / f"{eid}_session.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.with_video:
        # Lazy import path: call sibling render script logic inline
        try:
            from render_video_slow import pick_video, render as render_slow_video
        except ImportError:
            # same dir
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from render_video_slow import pick_video, render as render_slow_video
        vfile = pick_video(args.video_dir, seed=args.seed)
        vout = out_dir / f"{eid}_youtube.mp4"
        print(f"Rendering slow video ({args.video_speed}x) from {vfile.name}…")
        render_slow_video(
            final_path, vfile, vout,
            speed=args.video_speed,
        )
        meta["paths"]["youtube_mp4"] = str(vout)
        meta["video"] = {"file": str(vfile), "speed": args.video_speed}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  video: {vout}")

    print("\nDONE")
    print(f"  final: {final_path}")
    print(f"  meta:  {meta_path}")
    print(f"  atoms used: {meta['atom_count_used']}  total {meta['total_duration_sec']/60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
