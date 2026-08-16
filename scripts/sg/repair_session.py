#!/usr/bin/env python3
# coding: utf-8
"""从**既有成片**剪掉坏原子并原地重出 VO / 字幕 / 混音 —— 不重排内容。

用途:成片已经过 A/B 两层验收、视频也渲好了,却在人工过稿时发现个别句子
语义坏掉(丢词、半句、意思相反)。整期重排会换掉全部文案,代价太大;
这个脚本只做**减法**,其余每一条原子的音频、顺序、停顿曲线全部保持原样。

**唯一许可的操作是 DROP。** 与 VO_PIPELINE 的铁律一致:
不加词改词、不跨原子合并、不在原子内部再切(边车没有词级时间戳,而
whisper 会在静音上脑补熟悉的经文 —— 2026-08-05 它凭空补出过 "Do not")。
所以「半句话」只能整条剪掉,不能把坏的那半截切下来。

剪掉之后有一处必须补:前一条原子若原本**紧接**着被剪的这条(母带里序号
相邻),它的停顿被压缩成了 0.12–2.5s 的续接间隔。后继一没,它就直接撞上
一句不相干的话。所以要把这类停顿按进度曲线还原成正常的 4→6→10 秒。

  ./.venv/bin/python scripts/sg/repair_session.py --session sg_gold_001 --drop-cue 16 48
  ./.venv/bin/python scripts/sg/repair_session.py --session sg_gold_001 --drop-cue 16 --dry-run
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_session as bs
from vo_score import score_plan

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
# 低于此值的停顿一定是续接压缩的产物(正常曲线最低 4s × 0.88 微调 ≈ 3.5s)
COMPACT_PAD_MAX = 3.0


def restore_pad(atom: dict, vo_total: float) -> float:
    """把续接压缩过的停顿还原成进度曲线上的正常值。

    进度用**成品轨**上的位置(vo_start_sec / 全长),不用 plan 的估算 ——
    后者与成品差过将近两分钟。
    """
    progress = float(atom.get("vo_start_sec") or atom.get("start_sec") or 0) / max(60.0, vo_total)
    return bs.speech_pad(
        float(atom.get("duration_sec") or 0), 1.5,
        words=len(str(atom.get("text") or "").split()) or None,
        progress=progress,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--drop-cue", type=int, nargs="+", required=True,
                    help="要剪掉的字幕条号(1 起,与现有 .srt / plan 原子顺序一致)")
    ap.add_argument("--dry-run", action="store_true", help="只报告要剪什么,不动文件")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--keep-in-library", action="store_true",
                    help="只从本期剪掉,**不**逐出素材库(默认会逐出)")
    ap.add_argument("--replay", action="store_true",
                    help="不剪新的,只把该期历史上剪过的原子补做源头隔离")
    a = ap.parse_args()

    D = SESSIONS / a.session
    meta_path = D / f"{a.session}_session.json"
    if not meta_path.exists():
        raise SystemExit(f"找不到 {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    plan = meta["plan"]
    atoms = [p for p in plan if p.get("type") == "atom"]
    vo_total = float(meta.get("vo_duration_sec") or 0)

    def quarantine_at_source(ids: dict[str, str]) -> int:
        """把剪掉的原子逐出素材库 —— 否则它明天还会被选中。

        2026-08-12 的教训:第 1 期剪掉「…and he does not」、第 2 期剪掉
        「yours, my soul.」、第 3 期剪掉残缺的以赛亚书 26:3,可它们都留在库里,
        于是第 4 期又把同样的三条选了回来,一轮轮重演。
        **一条句子坏到要从成片里剪掉,就该同时从候选池里除名。**
        """
        mp = Path.home() / "Studio/Library/sg/atoms/manifest.json"
        man = json.loads(mp.read_text(encoding="utf-8"))
        stamp = datetime.now(timezone.utc).isoformat()
        n = 0
        for x in man["atoms"]:
            if x["id"] in ids and not x.get("quarantined"):
                x["quarantined"] = "dropped_in_review"
                x["quarantined_at"] = stamp
                x["dropped_from"] = ids[x["id"]]
                n += 1
        if n:
            mp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        return n

    if a.replay:
        recorded: dict[str, str] = {}
        for rec in (meta.get("repairs") or []):
            for d in rec.get("dropped", []):
                recorded[d["id"]] = a.session
        if not recorded:
            print("该期没有剪辑记录,无事可做")
            return 0
        print(f"补做源头隔离:{a.session} 历史上剪掉 {len(recorded)} 条")
        n = quarantine_at_source(recorded)
        print(f"🔒 新隔离 {n} 条(其余早已在隔离中)")
        return 0

    drop_idx = sorted({c - 1 for c in a.drop_cue})
    bad = [i + 1 for i in drop_idx if not 0 <= i < len(atoms)]
    if bad:
        raise SystemExit(f"条号越界(本期共 {len(atoms)} 条): {bad}")
    drop_ids = {atoms[i]["id"] for i in drop_idx}

    print(f"=== {a.session}:{len(atoms)} 条 → 剪掉 {len(drop_idx)} 条 ===")
    for i in drop_idx:
        print(f"  ✂ cue{i+1}  「{str(atoms[i].get('text'))[:66]}」")

    # 剪掉之后,谁的停顿需要还原
    restore: dict[str, float] = {}
    for i in drop_idx:
        if i == 0:
            continue
        prev = atoms[i - 1]
        if prev["id"] in drop_ids:
            continue
        if float(prev.get("pad_after_sec") or 0) <= COMPACT_PAD_MAX:
            new_pad = restore_pad(prev, vo_total)
            restore[prev["id"]] = new_pad
            print(f"  ↻ cue{i}  停顿 {float(prev['pad_after_sec']):.2f}s → {new_pad:.2f}s"
                  f"(原本紧接着被剪的那条)")

    if a.dry_run:
        print("\n(dry-run,未改动任何文件)")
        return 0

    # —— 重建 timeline:顺序、音频、停顿全部沿用原 plan,只是少了几条 ——
    new_plan: list[dict] = []
    timeline: list[tuple[str, object, float]] = []
    for p in plan:
        if p.get("type") == "atom":
            if p["id"] in drop_ids:
                continue
            pad = restore.get(p["id"], float(p.get("pad_after_sec") or 0))
            p = {**p, "pad_after_sec": pad}
            timeline.append(("atom", Path(p["path"]), pad))
        else:
            timeline.append(("silence", float(p.get("sec") or 0), 0.0))
        new_plan.append(p)

    if not a.no_backup:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        bak = D / f"_pre_repair_{stamp}"
        bak.mkdir(exist_ok=True)
        for name in (f"{a.session}_vo.mp3", f"{a.session}_final_mix.mp3",
                     f"{a.session}.srt", f"{a.session}_session.json"):
            src = D / name
            if src.exists():
                shutil.copy2(src, bak / name)
        print(f"\n原件已备份 → {bak.name}/")

    atempo = float(meta.get("vo_atempo") or 1.0)
    vo_path = D / f"{a.session}_vo.mp3"
    print("重出 VO…")
    marks: list[dict] = []
    bs.build_vo_track(timeline, vo_path, atempo=atempo, marks_out=marks)
    vo_dur = bs.probe_duration(vo_path)

    new_atoms = [p for p in new_plan if p.get("type") == "atom"]
    if len(new_atoms) != len(marks):
        raise SystemExit(f"时间轴条数不符: plan {len(new_atoms)} vs 渲染 {len(marks)}")
    for p, m in zip(new_atoms, marks):
        p["vo_start_sec"], p["vo_end_sec"] = m["start_sec"], m["end_sec"]

    srt_path = D / f"{a.session}.srt"
    srt_path.write_text(bs.build_srt(new_atoms), encoding="utf-8")
    print(f"  字幕 {srt_path.name}({len(new_atoms)} 条)· VO {vo_dur/60:.2f} min"
          f"(原 {vo_total/60:.2f} min)")

    # —— 混音:沿用**原有音乐床**,总长不变,只有人声轨变短 ——
    bed_path = D / f"{a.session}_bed.mp3"
    total = bs.probe_duration(bed_path)
    vo_for_mix = vo_path
    if vo_dur < total - 1:
        padded = D / f"{a.session}_vo_padded.mp3"
        r = bs._run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(vo_path), "-af", f"apad=pad_dur={total - vo_dur:.3f}",
            "-t", f"{total:.3f}", "-c:a", "libmp3lame", "-b:a", "192k", str(padded),
        ])
        if r.returncode == 0:
            vo_for_mix = padded
    mbcfg = meta.get("music_bed") or {}
    final_path = D / f"{a.session}_final_mix.mp3"
    print("重新混音…")
    bs.duck_mix(bed_path, vo_for_mix, final_path,
                bed_volume_db=float(mbcfg.get("bed_volume_db", -16)),
                ducking_db=float(mbcfg.get("ducking_db", -18)),
                vo_gain_db=float(mbcfg.get("vo_gain_db", 3.0)))

    meta["plan"] = new_plan
    meta["vo_duration_sec"] = vo_dur
    meta["vo_ends_sec"] = round(vo_dur, 3)
    meta["music_only_from_sec"] = round(vo_dur, 3)
    meta["total_duration_sec"] = bs.probe_duration(final_path)
    meta["atom_count_used"] = len(new_atoms)
    meta.setdefault("repairs", []).append({
        "at": datetime.now(timezone.utc).isoformat(),
        "dropped": [{"cue": i + 1, "id": atoms[i]["id"], "text": atoms[i].get("text")}
                    for i in drop_idx],
        "pads_restored": restore,
    })

    grammar = bs.load_grammar(Path(meta.get("grammar_path") or bs.DEFAULT_GRAMMAR))
    audit = bs.audit_plan_content(new_plan, grammar)
    meta["content_audit"] = audit
    verdict = score_plan({**meta, "audit": audit, "plan": new_plan})
    meta["vo_score"] = verdict
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n内容门禁 {'✅ 通过' if audit['ok'] else '❌ 未过: ' + '; '.join(audit['errors'][:3])}")
    print(f"VO 检测门 {'✅' if verdict['pass'] else '❌'} {verdict['score']} "
          f"(时序 {verdict['timing']}/40 · 清晰 {verdict['clarity']}/30 · 结构 {verdict['structure']}/30)")
    for n in verdict["notes"][:6]:
        print(f"    · {n}")
    if not a.keep_in_library:
        n = quarantine_at_source({atoms[i]["id"]: a.session for i in drop_idx})
        print(f"🔒 同时逐出素材库 {n} 条(reason=dropped_in_review)"
              f" —— 不这么做,它下一期还会被选回来")

    print(f"\n成品 {final_path.name} · {meta['total_duration_sec']/60:.1f} min"
          f" —— 视频需重渲(时间轴已变)")
    return 0 if (audit["ok"] and verdict["pass"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
