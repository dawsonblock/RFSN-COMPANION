from __future__ import annotations
from typing import List, Optional
from .types import Intent

class GlobalArbiter:
    def choose(self, intents: List[Intent]) -> Optional[Intent]:
        if not intents:
            return None
        def score(it: Intent) -> float:
            denom = max(1, it.effort_s)
            return (it.urgency * 0.6 + it.value * 0.4) / denom
        return sorted(intents, key=score, reverse=True)[0]
