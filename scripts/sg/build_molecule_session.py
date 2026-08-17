#!/usr/bin/env python3
# coding: utf-8
"""分子出片器 —— 每期一处经文,节制表达,语音稀疏(2026-08-17 用户令)。

与原子出片器的根本区别:**不再逐句拼接**。分子是母带的整段原声
(段内语气、句间距、呼吸全是录音时的真实节奏),出片只做三个决定:
  ① 选哪个主题(= 哪支母带,一支母带天然只围绕一处经文)
  ② 用哪些段落(保持母带原顺序,开场→正文子集→收束)
  ③ 段落之间隔多远(16–55s,随进度拉长 —— 入睡曲线)
句级拼接的全部失败模式(结巴/悬空/重叠/密度失控)从结构上不存在。

节制的量化(30 分钟一期):分子音频约 7 分钟、8–12 块,其余是音乐与
静默;60 分钟约 10 分钟、10–14 块。不做密度填充 —— 稀疏是产品本体。

出片后必须过独立内容门(content_gate.py,只看成片音频)才算合格;
门不放行本期作废,换种子重排。

  ./.venv/bin/python scripts/sg/build_molecule_session.py --minutes 30 --seed 7
"""
from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_session import (                    # noqa: E402
    MUSIC_SOURCES, build_music_bed, build_vo_track, duck_mix,
    list_music, load_recent, load_recent_tracks, record_episode,
    record_tracks)
from molecule_quality import (                  # noqa: E402
    books_heard, perspective, reject_reason)
from sg_media import measure_loudness, probe_duration  # noqa: E402

# 响度目标 = 已公开 Ep1 实测(-28.0 LUFS / TP -6.6)。频道听众深夜连听,
# 期与期响度必须一致;YouTube 只压不抬(-14 以上才压),此区间安全。
TARGET_LUFS = -28.0
LOUD_TOL = 0.8         # 偏差超过此值才动增益;小偏差不折腾
TP_CEIL = -2.0         # 真峰上限(加了增益也不许贴顶)

MANIFEST = Path.home() / "Studio/Library/sg/molecules/manifest.json"
DEFAULT_OUT = Path.home() / "Studio/Workspace/outputs/sg/sessions"

# 节制预算:minutes → (分子音频目标秒数, 块数下限, 块数上限)
BUDGET = {30: (7 * 60, 8, 12), 60: (10 * 60, 10, 14)}
# 2026-08-17 人耳审听定的节奏参数(此前 16-36×1.6 封顶 55,审听结论:
# 「句子快、留白长」不成引导感;40→22 的涨落也不平滑):
GAP_BASE = (18.0, 30.0)    # 块间距基础区间,随进度 ×(1+0.5·p)
GAP_CAP = 42.0
GAP_FINAL_CAP = 30.0       # 结尾块之前的停顿封顶:近 50s 静默后人声
                           # 突然回来会把已入睡的听众唤醒
VO_ATEMPO = 0.86           # 句内语速实测 141 wpm(热段 165),睡前引导
                           # 应在 115-125 —— 0.86 → 均值 ~121 wpm
COOL_EPISODES = 12         # 分子冷却窗:近 N 期用过的段落,本期回避


def load_molecules() -> list[dict]:
    mols = json.loads(MANIFEST.read_text(encoding="utf-8"))["molecules"]
    usable = [m for m in mols if reject_reason(m) is None]  # 单一权威,现场复判
    if len(usable) < len(mols):
        print(f"[库] 复判淘汰 {len(mols)-len(usable)} 条(判据已更新?)")
    return usable


def pick_theme(mols: list[dict], recent: dict[str, float],
               force: str | None) -> str:
    themes: dict[str, list[dict]] = {}
    for m in mols:
        themes.setdefault(m["master_slug"], []).append(m)
    if force:
        if force not in themes:
            raise SystemExit(f"主题不存在: {force}(可选 {sorted(themes)})")
        return force
    # 罚分 = 该主题分子在冷却窗内的权重占比;取最冷的主题
    scored = []
    for slug, ms in themes.items():
        pen = sum(recent.get(m["id"], 0.0) for m in ms) / len(ms)
        scored.append((pen, random.random(), slug))
    scored.sort()
    return scored[0][2]


def select_molecules(pool: list[dict], budget_sec: float,
                     bmax: int, recent: dict[str, float]) -> list[dict]:
    """开场→正文子集→收束,全程保持母带原顺序(span_index)。

    预算(秒 + 块数上限)与经文保底都在**这里**闭环。教训(2026-08-17
    连排):保底曾放在选段里、块数收敛放在 main() 事后抽稀 —— 抽稀从
    中段删,把保底刚补进的引用分子又删掉了,门照拦。约束必须在同一个
    函数里按序满足:先预算,后保底,保底在满员时用置换而不是追加。
    """
    pool = sorted(pool, key=lambda m: m["span_index"])
    opener = pool[0]                       # 母带开场(通常含台标欢迎)
    closers = [m for m in pool[-3:] if m["role"] in ("close", "bless")]
    if not closers:
        closers = pool[-1:]
    body = [m for m in pool
            if m is not opener and m not in closers]
    # 冷却:近期用过的段落回避;正文不够时按权重从冷到热放行
    body.sort(key=lambda m: (recent.get(m["id"], 0.0), m["span_index"]))
    body_cap = max(1, bmax - 1 - len(closers))
    remain = budget_sec - opener["duration_sec"] \
        - sum(m["duration_sec"] for m in closers)
    picked: list[dict] = []
    for m in body:
        if remain <= 0 or len(picked) >= body_cap:
            break
        picked.append(m)
        remain -= m["duration_sec"]

    # 视角塑形:成片应呈单弧线「对你安抚(Y)→众人祷告(W)」。母带原作
    # 里 Y/W 段落间有过渡段衔接,跳选把过渡抽走后横跳会裸露(2026-08-17
    # 九期重判:6 期 Y/W 横跳,最多切换 7 次)。做法:在母带顺序上找
    # 最优分割点(前 Y 后 W 错位最少),弃错位段,用同相候选补预算。
    picked.sort(key=lambda m: m["span_index"])
    pers = {m["id"]: perspective(m["text"]) for m in body}
    seq = [pers[m["id"]] for m in picked]
    best_s, best_cost = 0, 10 ** 9
    for s in range(len(seq) + 1):
        cost = sum(1 for p in seq[:s] if p == "W") \
            + sum(1 for p in seq[s:] if p == "Y")
        if cost < best_cost:
            best_s, best_cost = s, cost
    if best_cost:
        split_span = picked[best_s]["span_index"] if best_s < len(picked) \
            else 10 ** 9
        misfits = [m for i, m in enumerate(picked)
                   if (seq[i] == "W" and i < best_s)
                   or (seq[i] == "Y" and i >= best_s)]
        for m in misfits:
            picked.remove(m)
            print(f"  [视角塑形] 弃错位段 span={m['span_index']}({pers[m['id']]})")
        refill = [m for m in body
                  if m not in picked and m not in misfits
                  and (pers[m["id"]] != "W" if m["span_index"] < split_span
                       else pers[m["id"]] != "Y")]
        refill.sort(key=lambda m: (recent.get(m["id"], 0.0), m["span_index"]))
        lack = min(len(misfits), body_cap - len(picked))
        for m in refill[:max(0, lack)]:
            picked.append(m)
            print(f"  [视角塑形] 补同相段 span={m['span_index']}({pers[m['id']]})")

    # 主经文必须被读出声:内容门 G4 要求音频里真实听到主书卷名。
    # 主题池里有朗读引用的分子但子集没带上时,补进来;满员就置换
    # 最热(冷却权重最高)的非引用正文段。
    prim_books = set(books_heard(opener["primary_scripture"]))
    have_cite = any(prim_books & set(m.get("books_heard", []))
                    for m in [opener] + picked + closers)
    if prim_books and not have_cite:
        citing = sorted((m for m in body
                         if prim_books & set(m.get("books_heard", []))
                         and m not in picked),
                        key=lambda m: recent.get(m["id"], 0.0))
        if citing:
            add = citing[0]
            if len(picked) >= body_cap:
                victim = max((m for m in picked
                              if not (prim_books & set(m.get("books_heard", [])))),
                             key=lambda m: recent.get(m["id"], 0.0))
                picked.remove(victim)
                print(f"  [经文保底] 置换 {victim['id']} → {add['id']}")
            else:
                print(f"  [经文保底] 补入 {add['id']}")
            picked.append(add)

    # 指代悬空护栏:以指示词(That/This/It/These/Those/Such)开头的段落,
    # 指的是母带里**上一段**说过的东西 —— 上一段没入选就跳选它,听者
    # 会不知所指。处理:前段在场则留;不在场且补得进就补;补不进就弃。
    picked.sort(key=lambda m: m["span_index"])
    ana = re.compile(r"^(That|This|It|These|Those|Such)\b")
    have = {m["span_index"] for m in [opener] + picked + closers}
    for m in list(picked):
        if not ana.match(m["text"].strip()):
            continue
        prev_idx = m["span_index"] - 1
        if prev_idx in have:
            continue
        prev = next((x for x in body if x["span_index"] == prev_idx), None)
        if prev and len(picked) < body_cap:
            picked.append(prev)
            have.add(prev_idx)
            print(f"  [指代护栏] 补入前段 span={prev_idx}(为「{m['text'][:24]}…」)")
        else:
            picked.remove(m)
            have.discard(m["span_index"])
            print(f"  [指代护栏] 弃选指代悬空段 span={m['span_index']}")
    picked.sort(key=lambda m: m["span_index"])
    return [opener] + picked + closers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, choices=sorted(BUDGET), default=30)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--theme", default=None, help="主题 slug(默认取最冷)")
    ap.add_argument("--episode-id", default=None)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--skip-gate", action="store_true",
                    help="不跑内容门(仅调试;正式出片禁止)")
    a = ap.parse_args()
    if a.seed is not None:
        random.seed(a.seed)

    mols = load_molecules()
    recent = load_recent(COOL_EPISODES)
    theme = pick_theme(mols, recent, a.theme)
    pool = [m for m in mols if m["master_slug"] == theme]
    budget, bmin, bmax = BUDGET[a.minutes]
    picked = select_molecules(pool, budget, bmax, recent)
    if len(picked) < bmin:
        print(f"[节制] 本主题只凑出 {len(picked)} 块(下限 {bmin})—— "
              f"小主题按实际供给出片,内容门仍会把关块数")
    primary = picked[0]["primary_scripture"]
    scriptures = picked[0]["scriptures"]
    # 声明必须是库级实测(整个主题池听到的书卷),不是文件名的猜测:
    # john10 母带在祷文中朗读了 Deuteronomy 33:27,首次实弹即被门拦下。
    books_allowed = sorted(
        {b for m in pool for b in m.get("books_heard", [])})

    eid = a.episode_id or f"sg_mol_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = a.out / eid
    out_dir.mkdir(parents=True, exist_ok=True)
    speech_total = sum(m["duration_sec"] for m in picked)
    print(f"═══ {eid} · 主题 {theme}({primary})═══")
    print(f"  {len(picked)} 块 · 分子音频 {speech_total/60:.1f} min"
          f" · 目标全长 {a.minutes} min")

    # 时间线:块间距随进度拉长(入睡曲线),最后一块之后交给音乐尾
    timeline: list[tuple[str, Path | float, float]] = []
    plan: list[dict] = []
    cursor = 0.0
    for i, m in enumerate(picked):
        last = i == len(picked) - 1
        prog = i / max(1, len(picked) - 1)
        gap = 0.0 if last else min(
            GAP_CAP, random.uniform(*GAP_BASE) * (1 + 0.5 * prog))
        if i == len(picked) - 2:
            gap = min(gap, GAP_FINAL_CAP)
        timeline.append(("atom", Path(m["path"]), round(gap, 1)))
        plan.append({
            "slot": f"MOL_{i:02d}", "type": "atom", "id": m["id"],
            "role": m["role"], "path": m["path"], "text": m["text"],
            "duration_sec": m["duration_sec"],
            "pad_after_sec": round(gap, 1),
            "source_master": m["source_master"],
            "source_sequence_index": m["span_index"],
            "start_sec": round(cursor, 3),
            "end_sec": round(cursor + m["duration_sec"], 3),
        })
        cursor += m["duration_sec"] + gap
        print(f"  {i+1:2d}. [{m['role']:<5}] {m['duration_sec']:5.1f}s"
              f" +{gap:4.1f}s 「{m['text'][:40]}」")

    vo_path = out_dir / f"{eid}_vo.mp3"
    vo_marks: list[dict] = []
    build_vo_track(timeline, vo_path, atempo=VO_ATEMPO, marks_out=vo_marks)
    vo_dur = probe_duration(vo_path)
    for p, mk in zip(plan, vo_marks):
        p["vo_start_sec"], p["vo_end_sec"] = mk["start_sec"], mk["end_sec"]
    print(f"  VO {vo_dur/60:.2f} min(语音占 VO 区 {speech_total/vo_dur:.0%})")

    target_total = max(a.minutes * 60.0, vo_dur + 120.0)
    music_path = out_dir / f"{eid}_bed.mp3"
    bed_tracks: list[dict] = []
    build_music_bed(list_music(MUSIC_SOURCES), target_total, music_path,
                    crossfade=8.0, layout_out=bed_tracks,
                    avoid=load_recent_tracks())

    if vo_dur < target_total - 1:
        padded = out_dir / f"{eid}_vo_padded.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(vo_path), "-af",
             f"apad=pad_dur={target_total-vo_dur:.3f}",
             "-t", f"{target_total:.3f}",
             "-c:a", "libmp3lame", "-b:a", "192k", str(padded)], check=True)
        vo_for_mix = padded
    else:
        vo_for_mix = vo_path
    final_path = out_dir / f"{eid}_final_mix.mp3"
    # 混音柔化(2026-08-17 审听):浅压慢放,音乐不抽吸。ducking 与 bed
    # 同值 → 附加压降为零,总鸭深只来自 4:1 压缩 ≈ 8-10 dB。
    duck_mix(music_path, vo_for_mix, final_path,
             bed_volume_db=-16.0, ducking_db=-16.0, vo_gain_db=3.0,
             duck_ratio=4.0, duck_release_ms=2200)

    # 响度归一:静态增益对齐 Ep1 基线(动态 loudnorm 会呼吸泵动,睡眠向
    # 内容不可接受);增益后真峰越限就按峰让步,宁静勿爆。
    loud = measure_loudness(final_path)
    if loud is None:
        raise SystemExit("响度测不出,拒绝出片(绝不静默兜底)")
    gain = TARGET_LUFS - loud["I"]
    if abs(gain) > LOUD_TOL:
        gain = min(gain, TP_CEIL - loud["TP"])   # 峰值余量封顶
        tmp = final_path.parent / (final_path.stem + "_loud.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(final_path), "-af", f"volume={gain:+.2f}dB",
             "-c:a", "libmp3lame", "-b:a", "192k", str(tmp)], check=True)
        tmp.replace(final_path)
        loud = measure_loudness(final_path) or loud
        print(f"  [响度] 增益 {gain:+.1f} dB → I={loud['I']:.1f} LUFS "
              f"TP={loud['TP']:.1f}")
    else:
        print(f"  [响度] I={loud['I']:.1f} LUFS(基线 {TARGET_LUFS}±{LOUD_TOL},免调)")

    meta = {
        "episode_id": eid,
        "pipeline": "molecule_v1",
        "theme": theme,
        "primary_scripture": primary,
        "scriptures": scriptures,
        "scripture_books_allowed": books_allowed,
        "voice": "Locke",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": a.seed,
        "vo_atempo": VO_ATEMPO,
        "music_bed": {"bed_volume_db": -16.0, "ducking_db": -18.0,
                      "vo_gain_db": 3.0, "crossfade_sec": 8.0,
                      "tracks": bed_tracks},
        "vo_ends_sec": round(vo_dur, 3),
        "music_only_from_sec": round(vo_dur, 3),
        "vo_duration_sec": vo_dur,
        "loudness": loud,
        "total_duration_sec": probe_duration(final_path),
        "molecule_ids": [m["id"] for m in picked],
        "plan": plan,
        "paths": {"vo": str(vo_path), "bed": str(music_path),
                  "final_mix": str(final_path)},
    }
    meta_path = out_dir / f"{eid}_session.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    if not a.no_history:
        record_episode(eid, [m["id"] for m in picked])
        record_tracks(eid, sorted({t["name"] for t in bed_tracks}))

    if a.skip_gate:
        print("⚠ 跳过内容门(--skip-gate)—— 本期不可发布")
        return 0
    r = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "content_gate.py"),
         "--session", str(out_dir)],
        env={"KMP_DUPLICATE_LIB_OK": "TRUE", "PATH": "/opt/homebrew/bin:/usr/bin:/bin"})
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
