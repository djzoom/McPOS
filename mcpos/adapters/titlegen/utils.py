from __future__ import annotations

import hashlib
import random


def seeded_random(seed: str) -> random.Random:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))
