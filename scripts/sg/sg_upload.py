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


def upload_caption(yt, video_id: str, srt_path: Path) -> None:
    from googleapiclient.http import MediaFileUpload
    yt.captions().insert(
        part="snippet",
        body={"snippet": {"videoId": video_id, "language": "en",
                          "name": "English", "isDraft": False}},
        media_body=MediaFileUpload(str(srt_path), mimetype="application/octet-stream"),
    ).execute()


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


def main() -> int:
    ap = argparse.ArgumentParser(description="SG YouTube OAuth/上传核心")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("auth", help="首次授权/重授权")
    pa.add_argument("--secrets", type=Path, help="client_secret.json 路径")
    pa.add_argument("--reset", action="store_true", help="清除旧 token")
    sub.add_parser("status", help="凭证状态")
    a = ap.parse_args()
    {"auth": cmd_auth, "status": cmd_status}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
