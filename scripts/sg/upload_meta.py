#!/usr/bin/env python3
# coding: utf-8
"""Sleep in Grace — 每期 YouTube 元数据构建器(纯函数)+ 真源→主表同步校验。

标题真源在本文件 EPISODE_TITLES(逐期定稿表);排播主表
config/sg_schedule_master.json 里的 title 仅作展示。改标题的流程:
  1) 改 EPISODE_TITLES;2) python scripts/sg/upload_meta.py --sync-check
  (校验/回写主表,写前自动落 .bak_<yyyymmdd>)。

SEO 改版纪律(继承 RBR):只动未发布期(status 非 uploaded/verified),
回写时在 config/sg_meta_rollback_<yyyymmdd>.json 存回滚收据。

  python scripts/sg/upload_meta.py --episode 1          # 预览一期完整元数据
  python scripts/sg/upload_meta.py --sync-check         # 真源→主表 校验+回写
  python scripts/sg/upload_meta.py --build-srt 1        # 生成该期 SRT
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "config" / "sg_schedule_master.json"
SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"

CHANNEL = "Sleep in Grace"
CATEGORY_MUSIC = "10"

# ---------------------------------------------------------------- 真源:逐期定稿标题
# YouTube 硬限 100 字符;SEO 前置关键词;不用句号(照 Kat/RBR 家规)。
# 2026-08-19 分子 v3 重制:Ep2-8 原子期已撤回删除,标题整表换新;
# 主经文一律取音频实读(THEOLOGY_REVIEW 事故级第 4 条)。
EPISODE_TITLES = {
    1: "Safety is His to give — Psalm 4:8 | 18 Minutes Christian Night Prayer for Sleep · No. 001",
    2: "He will never leave you — Deuteronomy 31:6 | 30 Minutes Christian Night Prayer for Sleep · No. 002",
    3: "Peace the world cannot give — John 14:27 | 30 Minutes Christian Night Prayer for Sleep · No. 003",
    4: "Your keeper never sleeps — Psalm 121 | 30 Minutes Christian Night Prayer for Sleep · No. 004",
    5: "Anxious for nothing — Philippians 4:6-7 | 30 Minutes Christian Night Prayer for Sleep · No. 005",
    6: "At His right hand, unshaken — Psalm 16:8 | 30 Minutes Christian Night Prayer for Sleep · No. 006",
    7: "No one can snatch you away — John 10:28 | 30 Minutes Christian Night Prayer for Sleep · No. 007",
    8: "Kept in perfect peace — Isaiah 26:3 | 30 Minutes Christian Night Prayer for Sleep · No. 008",
    9: "He will not let you fall — Psalm 121:4 | 30 Minutes Christian Night Prayer for Sleep · No. 009",
    10: "In peace I lie down — Psalm 4:8 | 30 Minutes Christian Night Prayer for Sleep · No. 010",
}

TITLE_TEMPLATE = ("Sleep in Grace 🕊 {minutes_h} Christian Bedtime Prayer & "
                  "Sacred Instrumental Rest | Ep {num}")

DESCRIPTION_TEMPLATE = """A quiet hour in God's presence.

{chapters}

Tonight's prayer is read slowly, with long silences, over sacred instrumental \
music — made to be played as you fall asleep. The light of the cross and three \
golden orbits turn gently through the whole hour; nothing startles, nothing \
demands your attention.

"He gives to His beloved sleep." — Psalm 127:2

Subscribe for a new hour of rest: every episode is a different prayer and a \
different night of music.

#christianmusic #bedtimeprayer #sleepmusic #prayer #christianmeditation
"""

TAGS_POOL = [
    "christian bedtime prayer", "sleep in grace", "christian sleep music",
    "bedtime prayer", "fall asleep praying", "christian meditation",
    "night prayer", "sacred instrumental music", "peaceful prayer",
    "sleep prayer", "evening prayer", "christian relaxation",
    "prayer before sleep", "instrumental worship", "deep sleep christian",
]


# ---------------------------------------------------------------- 纯函数构建器

def build_title(num: int, minutes: float = 60) -> str:
    t = EPISODE_TITLES.get(num) or TITLE_TEMPLATE.format(
        minutes_h=f"{minutes / 60:g} Hour", num=num)
    if len(t) > 100:
        raise ValueError(f"标题超 100 字符({len(t)}): {t[:60]}…")
    return t


def _fmt_tc(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_chapters(session_dir: Path, minutes: float = 60) -> str:
    """时间码章节。VO 段落来自 manifest(vo_start/vo_minutes),其余为音乐安息。"""
    manifest = next(iter(sorted(session_dir.glob("*_manifest.json"))), None)
    vo_start, vo_min = 10.0, 20.0
    if manifest:
        m = json.loads(manifest.read_text())
        vo_start = float(m.get("vo_start_sec", 10.0))
        vo_min = float(m.get("vo_minutes", 20.0))
    lines = ["0:00 Sleep in Grace — Opening",
             f"{_fmt_tc(vo_start)} Evening Prayer",
             f"{_fmt_tc(vo_start + vo_min * 60)} Sacred Instrumental Rest"]
    return "\n".join(lines)


def build_description(num: int, session_dir: Path, minutes: float = 60) -> str:
    desc = DESCRIPTION_TEMPLATE.format(chapters=build_chapters(session_dir, minutes))
    if "{" in desc.replace("{chapters}", ""):
        raise ValueError("描述模板存在未替换变量")
    if len(desc.encode()) > 5000:
        raise ValueError(f"描述超 5000 字节({len(desc.encode())})")
    return desc


def build_tags() -> list[str]:
    tags, total = [], 0
    for t in TAGS_POOL:
        if total + len(t) + 1 > 480:      # 硬限 500,留余量
            break
        tags.append(t)
        total += len(t) + 1
    return tags


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(session_dir: Path, vo_start: float = 10.0,
              atempo: float = 1.0) -> str:
    """从 session.json plan 生成 SRT(与烧录 ASS 同源同时基)。"""
    sid = session_dir.name
    plan = json.loads((session_dir / f"{sid}_session.json").read_text())["plan"]
    out, n = [], 0
    for e in plan:
        if e.get("type") != "atom" or not e.get("text"):
            continue
        n += 1
        a = e["start_sec"] / atempo + vo_start
        b = e["end_sec"] / atempo + vo_start + 0.35
        text = " ".join(e["text"].split())
        out.append(f"{n}\n{_srt_time(a)} --> {_srt_time(b)}\n{text}\n")
    return "\n".join(out)


def build_body(num: int, session_dir: Path, publish_at: str,
               minutes: float = 60) -> dict:
    """videos.insert 请求体:private + publishAt 未来排播(血的教训:绝不即时公开)。"""
    return {
        "snippet": {
            "title": build_title(num, minutes),
            "description": build_description(num, session_dir, minutes),
            "tags": build_tags(),
            "categoryId": CATEGORY_MUSIC,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
            "license": "creativeCommon",
            "embeddable": True,
            "publicStatsViewable": True,
        },
    }


# ---------------------------------------------------------------- 真源→主表 同步

def sync_check(write: bool = True) -> int:
    master = json.loads(MASTER_PATH.read_text())
    drift, blocked = [], []
    for ep in master["episodes"]:
        num = ep["episode_number"]
        want = build_title(num, ep.get("minutes", 60))
        if ep.get("title") != want:
            if ep.get("status") in ("uploaded", "verified"):
                blocked.append((num, ep.get("title"), want))
            else:
                drift.append((num, ep.get("title"), want))
                ep["title"] = want
    for num, old, new in blocked:
        print(f"⚠️  #{num} 已发布,标题不回写(SEO 改版只动未发布期): {new[:50]}…")
    if not drift:
        print("✅ 真源与主表一致" + (f"({len(blocked)} 期已发布跳过)" if blocked else ""))
        return 0
    for num, old, new in drift:
        print(f"↻ #{num}: '{(old or '')[:40]}…' → '{new[:40]}…'")
    if write:
        stamp = datetime.now().strftime("%Y%m%d")
        bak = MASTER_PATH.with_suffix(f".json.bak_{stamp}")
        if not bak.exists():
            bak.write_text(MASTER_PATH.read_text())
        rollback = ROOT / "config" / f"sg_meta_rollback_{stamp}.json"
        rollback.write_text(json.dumps(
            [{"episode_number": n, "old": o, "new": w} for n, o, w in drift],
            ensure_ascii=False, indent=2))
        MASTER_PATH.write_text(json.dumps(master, ensure_ascii=False, indent=2))
        print(f"✅ 主表已回写({len(drift)} 期);备份 {bak.name};回滚收据 {rollback.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="SG 元数据构建/校验")
    ap.add_argument("--episode", type=int, help="预览一期")
    ap.add_argument("--sync-check", action="store_true")
    ap.add_argument("--build-srt", type=int, metavar="N", help="生成该期 SRT 文件")
    a = ap.parse_args()

    master = json.loads(MASTER_PATH.read_text())
    by_num = {e["episode_number"]: e for e in master["episodes"]}

    if a.sync_check:
        return sync_check()
    if a.build_srt:
        ep = by_num[a.build_srt]
        sdir = Path(ep["output_file"]).parent
        manifest = next(iter(sorted(sdir.glob("*_manifest.json"))), None)
        vo_start, atempo = 10.0, 1.0
        if manifest:
            m = json.loads(manifest.read_text())
            vo_start = float(m.get("vo_start_sec", 10))
            atempo = float(m.get("vo_atempo", 1.0))
        srt = build_srt(sdir, vo_start, atempo)
        Path(ep["srt_file"]).write_text(srt, encoding="utf-8")
        print(f"✅ SRT → {ep['srt_file']} ({srt.count('-->')} 条)")
        return 0
    if a.episode:
        ep = by_num[a.episode]
        sdir = Path(ep["output_file"]).parent
        body = build_body(a.episode, sdir, ep["publish_at"], ep.get("minutes", 60))
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
