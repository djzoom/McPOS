#!/usr/bin/env python3
# coding: utf-8
"""每日运营 —— 一条命令跑完当天该做的事,顺序与止损规则都写死在这里。

频道进入日更之后,每天要做的事是固定的几件,但它们之间有**依赖与预算**:
配额是共享的、短片要保持领先公开日、评论只能等视频公开后才发得出去。
人来记这些顺序迟早会漏,所以固化成一条命令:

    0) 发布链路体检   主表路径/串期/字幕/排期/标志(不花配额,不过就拦下面)
    1) 补发置顶评论   已公开却还挂着 comment_pending 的短片(便宜,先做)
    2) 撤回续跑       recall_needed 标记未清零就续删(不删会自己播出去)
    3) 短片续传       补足「领先公开日 N 天」的缓冲,不多传(配额留给别人)
    4) 字幕补挂       平台缺的语言轨(hold 行没有 video_id,自动跳过)
    5) 长片补传       主表里还没 video_id 且未冻结(hold)的期次
    6) 记录运营日志   ops_log --append,当日一条事实

每一步都先问配额够不够,不够就停在那一步并说明 —— 预算制不是重试制。

  ./.venv/bin/python scripts/sg/daily_ops.py            # 真跑
  ./.venv/bin/python scripts/sg/daily_ops.py --dry-run  # 只报告要做什么
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quota                                        # noqa: E402
from sg_upload import build_service, upload_link_lock   # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = ROOT / ".venv/bin/python"
TOYTUNE = Path.home() / "Projects/TOYTUNE"
LEAD_DAYS = 3          # 短片缓冲:已上传但未公开的条数,少于此就补传
SHORT_COST = 1650      # 一条短片的大致配额(insert 1600 + thumb 50)


def shorts_state() -> dict:
    p = TOYTUNE / "publish_state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"uploaded": {}}


def manifest_rows() -> dict[int, dict]:
    p = TOYTUNE / "output/publish/manifest.csv"
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as f:
        return {int(r["episode"]): r for r in csv.DictReader(f)}


def step_audit() -> bool:
    """发布层前置门 —— 主表体检不过就不许碰平台。

    内容有十一道门,发布层此前一道也没有,于是两天内连出两次险情
    (recall 自行推导删除目标、hold 冻结装着新内容的行)。体检只查本地
    状态与路径、不花配额,失败即拦下所有**读主表**的步骤;短片线那几步
    由 TOYTUNE 自己的状态驱动,不受影响,照常跑。
    """
    print("\n[0/7] 发布链路体检")
    rc = subprocess.run([str(PY), str(HERE / "audit_publish_chain.py")]).returncode
    if rc:
        print("      ⛔ 体检未过 —— 本轮跳过撤回/字幕/长片(主表不可信),"
              "先人工修主表")
    return rc == 0


def step_comments(dry: bool) -> None:
    """已公开的短片补发置顶评论 —— 评论驱动 Shorts 的再分发,别漏。"""
    st = shorts_state()
    pending = {k: v for k, v in st["uploaded"].items() if v.get("comment_pending")}
    now = datetime.now(timezone.utc)
    due = {k: v for k, v in pending.items()
           if v.get("publish_at", "9999") <= now.isoformat()}
    print(f"\n[1/7] 置顶评论:挂起 {len(pending)} 条,其中已公开可发 {len(due)} 条")
    if not due or dry:
        return
    sys.path.insert(0, str(TOYTUNE))
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    scopes = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube.force-ssl"]
    yt = build("youtube", "v3", cache_discovery=False,
               credentials=Credentials.from_authorized_user_file(
                   str(TOYTUNE / ".youtube_token.json"), scopes))
    rows = manifest_rows()
    for ep, rec in sorted(due.items(), key=lambda x: int(x[0])):
        text = (rows.get(int(ep)) or {}).get("pinned_comment")
        if not text:
            continue
        try:
            yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": rec["video_id"],
                "topLevelComment": {"snippet": {"textOriginal": text}}}}).execute()
            rec.pop("comment_pending", None)
            print(f"      ✅ ep{int(ep):03d} 评论已发")
        except HttpError as e:
            print(f"      ⚠ ep{int(ep):03d} 仍失败({e.resp.status}),保留挂起")
    (TOYTUNE / "publish_state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def step_shorts(dry: bool) -> None:
    """补足缓冲即可 —— 一次传完 50 条既吃光配额,也让排期失去调整余地。"""
    st = shorts_state()["uploaded"]
    now = datetime.now(timezone.utc).isoformat()
    buffered = sum(1 for v in st.values() if v.get("publish_at", "") > now)
    need = max(0, LEAD_DAYS - buffered)
    print(f"\n[3/7] 短片:已传 {len(st)} 条 · 未公开缓冲 {buffered} 条 · 需补 {need} 条")
    if not need:
        return
    if not quota.can_afford(SHORT_COST * need):
        print(f"      ⛔ 配额不足(需 ~{SHORT_COST*need}u,余 {quota.remaining()}u)")
        return
    if dry:
        return
    subprocess.run([str(PY), "publish.py", "upload", "--limit", str(len(st) + need)],
                   cwd=str(TOYTUNE))


def step_recall(dry: bool) -> None:
    """续跑未完成的撤回 —— 有 recall_needed 标记才动,删干净后永远静默。

    2026-08-17 用户令撤回全部未播长片。当天配额只够删一部分,剩下的
    期次仍挂着定时公开,拖着不删它会自己播出去 —— 所以这一步必须
    自动续到清零为止。只认标记,绝不自己扩大删除范围。
    """
    master = json.loads((ROOT / "config/sg_schedule_master.json").read_text())
    flagged = [r for r in master["episodes"] if r.get("recall_needed")]
    print(f"\n[2/7] 撤回续跑:剩 {len(flagged)} 期待撤")
    if not flagged:
        return
    cmd = [str(PY), str(HERE / "sg_upload.py"), "recall"]
    subprocess.run(cmd + ["--dry-run"] if dry else cmd)


def step_captions(dry: bool) -> None:
    """补挂缺失的字幕轨(尤其中文)。

    2026-08-16:八期的中文字幕本地早已生成,平台上却只有英文轨 ——
    upload_caption 曾把语言硬编码成 en。当天补了 15/16 条,最后一条
    (Ep8 繁体)卡在配额差 51u。这一步就是让"差一点"自己收尾:
    backfill 幂等,没得补时几秒返回,补得动就补。
    """
    print("\n[4/7] 字幕补挂")
    if dry:
        subprocess.run([str(PY), str(HERE / "backfill_captions.py"), "--dry-run"])
        return
    subprocess.run([str(PY), str(HERE / "backfill_captions.py")])


def step_longs(dry: bool) -> None:
    master = json.loads((ROOT / "config/sg_schedule_master.json").read_text())
    todo = [r for r in master["episodes"]
            if not r.get("video_id") and not r.get("hold")]
    print(f"\n[5/7] 长片:待传 {len(todo)} 期")
    if not todo or dry:
        return
    subprocess.run([str(PY), str(HERE / "sg_batch_upload.py")])
    subprocess.run([str(PY), str(HERE / "sg_verify_uploads.py")])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(f"=== SG 每日运营 · {datetime.now().strftime('%F %H:%M')} ===")
    print(f"配额:已用 {quota.spent_today()}u · 可用 {quota.remaining()}u")
    healthy = step_audit()
    step_comments(a.dry_run)
    if healthy:
        step_recall(a.dry_run)
    step_shorts(a.dry_run)          # 短片线由 TOYTUNE 状态驱动,与主表无关
    if healthy:
        step_captions(a.dry_run)
        step_longs(a.dry_run)
    # 频道对账便宜(2-4u)且能抓到本地门拦不住的东西:平台上有、主表里
    # 没有的视频会自己公开出去(F8WhUgKgOUQ 就差点)。放在最后,不与
    # 上传抢配额。
    if healthy and not a.dry_run and quota.can_afford(200):
        subprocess.run([str(PY), str(HERE / "audit_channel_orphans.py")])
    print("\n[6/7] 运营日志")
    if not a.dry_run:
        subprocess.run([str(PY), str(HERE / "ops_log.py"), "--append"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
