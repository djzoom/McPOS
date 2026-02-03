from __future__ import annotations

from dataclasses import dataclass

from ...core.logging import log_info, log_warning


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class EpisodeBudget:
    max_calls: int = 2
    used: int = 0

    def consume(self, label: str) -> None:
        if self.used >= self.max_calls:
            log_warning(f"Budget exceeded for model call: {label} ({self.used}/{self.max_calls})")
            raise BudgetExceeded(f"Model call budget exceeded: {label}")
        self.used += 1
        log_info(f"Model call consumed: {label} ({self.used}/{self.max_calls})")

def ensure_budget(budget: EpisodeBudget | None, max_calls: int = 2) -> EpisodeBudget:
    if budget is not None:
        return budget
    return EpisodeBudget(max_calls=max_calls)
