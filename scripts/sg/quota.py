#!/usr/bin/env python3
# coding: utf-8
"""Sleep in Grace — YouTube Data API 配额账本(预算制,继承 RBR 教训)。

原则:预算制不是重试制。上传前 can_afford() 确认够一整期(~2150u)再开,
不够即停;403 quotaExceeded 不重试(重试也计费)。配额按太平洋时间午夜重置。

注意:若 SG 与 kat/RBR 共用同一 Google Cloud project,则配额池共享——
本账本只记 SG 自己的消耗,预算判断时应把其他频道当日用量心算在内
(或统一到共享账本;当前先按独立 project 假设,接入时确认)。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # McPOS 仓库根
LEDGER_PATH = ROOT / "config" / "sg_quota_ledger.json"

DAILY_BUDGET = 10_000
RESERVE = 1_500                     # 预留给验收/改期/补挂等杂项写操作

COSTS = {  # https://developers.google.com/youtube/v3/determine_quota_cost
    "videos.insert": 1600,
    "videos.update": 50,
    "videos.list": 1,
    "captions.insert": 400,
    "captions.list": 50,
    "thumbnails.set": 50,
}
EPISODE_COST = COSTS["videos.insert"] + COSTS["captions.insert"] + \
    COSTS["thumbnails.set"] + COSTS["videos.update"]          # ≈2100

try:
    from zoneinfo import ZoneInfo
    PT = ZoneInfo("America/Los_Angeles")
except Exception:
    PT = timezone(timedelta(hours=-7))


def window_key(now: datetime | None = None) -> str:
    """当前配额窗口(太平洋日期)。"""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(PT).strftime("%Y-%m-%d")


def _load() -> dict:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return {"window": window_key(), "spent": 0, "calls": []}


def _save(led: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(led, indent=2, ensure_ascii=False))


def _current() -> dict:
    led = _load()
    if led.get("window") != window_key():
        led = {"window": window_key(), "spent": 0, "calls": []}
        _save(led)
    return led


def spent_today() -> int:
    return _current()["spent"]


def remaining() -> int:
    return max(0, DAILY_BUDGET - RESERVE - spent_today())


def can_afford(units: int = EPISODE_COST) -> bool:
    return remaining() >= units


def record(method: str, note: str = "") -> int:
    led = _current()
    units = COSTS.get(method, 50)
    led["spent"] += units
    led["calls"].append({"at": datetime.now(timezone.utc).isoformat(),
                         "method": method, "units": units, "note": note})
    _save(led)
    return units


if __name__ == "__main__":
    print(f"窗口(PT日期): {window_key()}")
    print(f"已用: {spent_today()}u  预算: {DAILY_BUDGET}u  预留: {RESERVE}u")
    print(f"可用: {remaining()}u  ≈ 可上传 {remaining() // EPISODE_COST} 期"
          f"(每期 {EPISODE_COST}u)")
