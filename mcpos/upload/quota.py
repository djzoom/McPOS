"""
mcpos/upload/quota.py — YouTube Data API v3 quota management

Daily quota: 10,000 units per Google account.
Upload cost: ~1,600 units per video.
Max uploads per channel: ~6/day (with budget=3000 → ~1 upload/day).

QuotaGuard tracks usage in a JSON sidecar file and prevents over-quota uploads.
State resets automatically at the start of each new calendar day.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional
import json

# YouTube API v3 unit costs
UPLOAD_COST = 1_600      # video.insert
LIST_COST = 1            # videos.list / commentThreads.list
INSERT_COST = 50         # comments.insert / videos.update
DAILY_LIMIT = 10_000     # YouTube default per project


class QuotaExceeded(Exception):
    """Raised when a request would exceed the daily quota budget."""


@dataclass
class QuotaGuard:
    """
    Track and enforce per-channel daily quota usage.

    Usage:
        guard = QuotaGuard("kat", budget=3000, state_dir=Path("/..."))
        guard.consume(UPLOAD_COST)        # raises QuotaExceeded if over budget
        guard.consume(UPLOAD_COST, dry_run=True)  # check only
        print(guard.remaining())          # units left today
        print(guard.status())             # full status dict
    """

    channel_id: str
    budget: int = 3_000
    state_dir: Optional[Path] = None

    _usage: int = field(default=0, init=False, repr=False)
    _date: date = field(default_factory=date.today, init=False, repr=False)

    def __post_init__(self):
        if self.state_dir:
            self._load()

    @property
    def _state_file(self) -> Optional[Path]:
        if self.state_dir:
            return Path(self.state_dir) / f"{self.channel_id}_quota.json"
        return None

    def _load(self):
        f = self._state_file
        if f and f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                saved_date = date.fromisoformat(data.get("date", "1970-01-01"))
                if saved_date == date.today():
                    self._usage = int(data.get("usage", 0))
                    return
            except Exception:
                pass
        self._usage = 0

    def _save(self):
        f = self._state_file
        if f:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(
                json.dumps({
                    "channel_id": self.channel_id,
                    "date": date.today().isoformat(),
                    "usage": self._usage,
                    "budget": self.budget,
                    "updated_at": datetime.now().isoformat(),
                }, indent=2),
                encoding="utf-8",
            )

    def remaining(self) -> int:
        """Quota units remaining today."""
        return max(0, self.budget - self._usage)

    def can_afford(self, cost: int) -> bool:
        """Return True if consuming cost units would stay within budget."""
        return self._usage + cost <= self.budget

    def consume(self, cost: int, dry_run: bool = False) -> None:
        """
        Consume `cost` quota units.

        Args:
            cost: Number of units to consume.
            dry_run: If True, check only without recording usage.

        Raises:
            QuotaExceeded: If consuming would exceed the daily budget.
        """
        if not self.can_afford(cost):
            raise QuotaExceeded(
                f"Channel '{self.channel_id}': request of {cost} units would exceed budget. "
                f"Used={self._usage}, budget={self.budget}, remaining={self.remaining()}"
            )
        if not dry_run:
            self._usage += cost
            self._save()

    def reset(self) -> None:
        """Reset usage to 0 (e.g. for testing or manual override)."""
        self._usage = 0
        self._save()

    def status(self) -> dict:
        """Return a status dict for display/logging."""
        return {
            "channel_id": self.channel_id,
            "date": date.today().isoformat(),
            "usage": self._usage,
            "budget": self.budget,
            "remaining": self.remaining(),
            "can_upload": self.can_afford(UPLOAD_COST),
        }
