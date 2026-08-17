#!/usr/bin/env python3
# coding: utf-8
"""Sleep in Grace — YouTube OAuth 与上传核心(每频道独立凭证)。

凭证(与 kat 分离,gitignored):
    config/google/sg/client_secrets.json   ← 从 Google Cloud OAuth 客户端(桌面型)导入
    config/google/sg/youtube_token.json    ← 本脚本铸造/自动刷新

    python scripts/sg/sg_upload.py auth --secrets ~/Downloads/client_secret_*.json
    python scripts/sg/sg_upload.py status

单链路锁(血的教训 2026-07-17):非阻塞,拿不到即退出。

**SG 与 kat 同属 Google 项目 gothic-context-439714-t3 → 共享 10000u/天配额池**,
两者的上传链路必须互斥。锁文件统一在
  ~/Studio/Workspace/temp/_locks/upload_link.lock
(RBR 属另一项目 openclawgog-488312,配额独立,但沿用同名锁目录惯例。)
注意:kat 现有上传器 scripts/uploader/upload_to_youtube.py **没有任何锁**,
SG 单方面持锁挡不住它 —— 见 docs/ 待办。
"""
from __future__ import annotations

import argparse
import fcntl
import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GDIR = ROOT / "config" / "google" / "sg"
SECRETS = GDIR / "client_secrets.json"
TOKEN = GDIR / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
UPLOAD_LOCK_PATH = Path.home() / "Studio/Workspace/temp/_locks/upload_link.lock"


@contextmanager
def upload_link_lock(label: str):
    """非阻塞单链路锁:拿不到立刻退出,绝不排队(排队=重复上传事故根因)。"""
    UPLOAD_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = UPLOAD_LOCK_PATH.open("a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.seek(0)
        holder = fh.read().strip() or "unknown"
        sys.exit(f"⛔ 上传链路已被占用({holder})——非阻塞锁,直接退出,不排队")
    fh.truncate(0)
    fh.write(f"{label}\n")
    fh.flush()
    try:
        yield
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
        UPLOAD_LOCK_PATH.unlink(missing_ok=True)


def _save_token(creds) -> None:
    GDIR.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(creds.to_json())


def load_creds(interactive: bool = False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    creds = None
    if TOKEN.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
        except ValueError:
            creds = None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
        except Exception as exc:
            print(f"⚠️ token 刷新失败(要报警不要静默): {exc}", file=sys.stderr)
            creds = None
    if creds and creds.valid:
        return creds
    if not interactive:
        return None
    if not SECRETS.exists():
        sys.exit(f"缺少 {SECRETS} — 先运行: sg_upload.py auth --secrets <client_secret.json>")
    from google_auth_oauthlib.flow import InstalledAppFlow
    creds = InstalledAppFlow.from_client_secrets_file(str(SECRETS), SCOPES)\
        .run_local_server(port=0)
    _save_token(creds)
    return creds


def build_service(interactive: bool = False):
    from googleapiclient.discovery import build
    creds = load_creds(interactive=interactive)
    if creds is None:
        sys.exit("⛔ 无有效凭证 — 先运行 sg_upload.py auth")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_media(yt, video_path: Path, body: dict) -> str:
    """断点续传上传,返回 video_id。调用方负责配额记账。"""
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                            chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"    ↑ {int(status.progress() * 100)}%", end="\r", flush=True)
    print()
    return resp["id"]


def upload_caption(yt, video_id: str, srt_path: Path,
                   language: str = "en", name: str = "English") -> None:
    """挂一条字幕轨。

    language 必须传对:此前这里把语言硬编码成 en,于是本地明明生成了
    简繁两版中文字幕(zh-Hans/zh-Hant),平台上却只有英文轨 —— 做出来的
    东西没送到观众面前,和没做一样。
    """
    from googleapiclient.http import MediaFileUpload
    yt.captions().insert(
        part="snippet",
        body={"snippet": {"videoId": video_id, "language": language,
                          "name": name, "isDraft": False}},
        media_body=MediaFileUpload(str(srt_path), mimetype="application/octet-stream"),
    ).execute()


# 每期要挂的字幕轨:后缀 → (语言代码, 轨道名)
CAPTION_TRACKS = [
    ("",           "en",      "English"),
    (".zh-Hans",   "zh-Hans", "简体中文"),
    (".zh-Hant",   "zh-Hant", "繁體中文"),
]


def set_thumbnail(yt, video_id: str, thumb_path: Path) -> None:
    from googleapiclient.http import MediaFileUpload
    yt.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg"),
    ).execute()


def cmd_auth(a) -> None:
    if a.secrets:
        GDIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(a.secrets, SECRETS)
        print(f"✅ client_secrets 已导入 → {SECRETS}")
    if TOKEN.exists() and a.reset:
        TOKEN.unlink()
        print("旧 token 已清除")
    creds = load_creds(interactive=True)
    print("✅ 授权完成" if creds else "⛔ 授权失败")


def cmd_status(_a) -> None:
    print(f"client_secrets: {'✅ ' + str(SECRETS) if SECRETS.exists() else '❌ 未导入'}")
    if not TOKEN.exists():
        print("token:          ❌ 未授权(sg_upload.py auth)")
        return
    creds = load_creds()
    print(f"token:          {'✅ 有效' if creds else '⚠️ 失效(需重新 auth)'}")


def cmd_reschedule(a) -> None:
    """把主表里标记 reschedule_needed 的期次,在平台端改 publishAt。

    排播节奏变更(2026-08-14:日更改周更)时,已上传的期次在 YouTube 上
    还挂着旧的定时公开 —— 不改,它们会按旧日期自己公开出去。
    videos.update 每次 ~50u,走配额账本;改完清标记、回填主表。
    """
    import quota
    master_path = ROOT / "config" / "sg_schedule_master.json"
    master = json.loads(master_path.read_text(encoding="utf-8"))
    todo = [r for r in master.get("episodes", [])
            if r.get("reschedule_needed") and r.get("video_id")]
    if not todo:
        print("没有待改期的期次")
        return
    if a.dry_run:
        for r in todo:
            print(f"  DRY #{r['episode_number']} {r['video_id']} → {r['publish_at']}")
        print(f"(共 {len(todo)} 期,实跑需 {50*len(todo)}u)")
        return
    cost = 50 * len(todo)
    if not quota.can_afford(cost):
        print(f"⛔ 配额不足(需 {cost}u)—— 等太平洋时间午夜重置后再跑")
        return
    yt = build_service()
    with upload_link_lock("sg-reschedule"):
        for r in todo:
            yt.videos().update(part="status", body={
                "id": r["video_id"],
                "status": {"privacyStatus": "private",
                           "publishAt": r["publish_at"],
                           "selfDeclaredMadeForKids": False},
            }).execute()
            quota.record("videos.update", f"reschedule #{r['episode_number']}")
            r.pop("reschedule_needed", None)
            print(f"  ✅ #{r['episode_number']} {r['video_id']} → publishAt {r['publish_at']}")
    if not a.dry_run:
        bak = master_path.with_suffix(".json.bak_resched")
        if not bak.exists():
            bak.write_text(master_path.read_text(encoding="utf-8"))
        master_path.write_text(json.dumps(master, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        print("主表已回填")


def cmd_recall(a) -> None:
    """撤回未播出的长片:平台删除 + 主表标 hold,已公开的绝不动。

    2026-08-17 用户令:原子拼接的成片表达太碎太密,未播出的一律撤回,
    等分子管线出了真正合格的内容再重新上传。删除不可逆,三重保险:
    ① 只挑 published_at_actual 为空的行;② 平台端现场核实
    privacyStatus=='private'(1u,便宜);③ 核实不过就跳过并大声报告。

    幂等:先给全部目标行落 recall_needed 标记(意图先落盘),再删配额
    允许的部分;删成一条清一条标记。配额中断后重跑即续,daily_ops
    也会在有标记时自动续跑 —— 未删干净的期次仍挂着定时公开,拖着不删
    它会自己播出去。
    """
    import quota
    master_path = ROOT / "config" / "sg_schedule_master.json"
    master = json.loads(master_path.read_text(encoding="utf-8"))
    targets = [r for r in master.get("episodes", [])
               if r.get("video_id") and not r.get("published_at_actual")]
    for r in targets:                       # 意图先落盘,配额中断也不丢
        r["recall_needed"] = True
    master_path.write_text(json.dumps(master, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    if not targets:
        print("没有待撤回的期次")
        return
    print(f"待撤回 {len(targets)} 期(按公开日先近后远):")
    targets.sort(key=lambda r: r.get("publish_at", ""))
    if a.dry_run:
        for r in targets:
            print(f"  DRY #{r['episode_number']} {r['video_id']} "
                  f"(原定 {r.get('schedule_date')})")
        return
    yt = build_service()
    done = 0
    with upload_link_lock("sg-recall"):
        for r in targets:
            if not quota.can_afford(51):     # list 1u + delete 50u
                print(f"  ⛔ 配额不足,余 {quota.remaining()}u —— "
                      f"剩 {len(targets)-done} 期留给下次(daily_ops 会自动续)")
                break
            vid = r["video_id"]
            resp = yt.videos().list(part="status", id=vid).execute()
            quota.record("videos.list", f"recall-check #{r['episode_number']}")
            items = resp.get("items", [])
            if items and items[0]["status"]["privacyStatus"] != "private":
                print(f"  🛑 #{r['episode_number']} {vid} 状态是 "
                      f"{items[0]['status']['privacyStatus']},不是 private —— 跳过不删")
                continue
            if items:
                yt.videos().delete(id=vid).execute()
                quota.record("videos.delete", f"recall #{r['episode_number']}")
            else:
                print(f"  (#{r['episode_number']} 平台已不存在,只清主表)")
            r["recalled_video_id"] = vid
            r.pop("video_id", None)
            r.pop("recall_needed", None)
            r["status"] = "recalled"
            r["hold"] = True                 # 上传器护栏:此行冻结,旧文件绝不重传
            r["caption_uploaded"] = False
            done += 1
            print(f"  ✅ #{r['episode_number']} {vid} 已删除并冻结")
    master_path.write_text(json.dumps(master, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"本次撤回 {done}/{len(targets)} 期,主表已回填")


def main() -> int:
    ap = argparse.ArgumentParser(description="SG YouTube OAuth/上传核心")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("auth", help="首次授权/重授权")
    pa.add_argument("--secrets", type=Path, help="client_secret.json 路径")
    pa.add_argument("--reset", action="store_true", help="清除旧 token")
    sub.add_parser("status", help="凭证状态")
    pr = sub.add_parser("reschedule", help="平台端改期(主表 reschedule_needed 标记)")
    pr.add_argument("--dry-run", action="store_true")
    pc = sub.add_parser("recall", help="撤回未播出的长片(平台删除+主表冻结)")
    pc.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    {"auth": cmd_auth, "status": cmd_status,
     "reschedule": cmd_reschedule, "recall": cmd_recall}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
