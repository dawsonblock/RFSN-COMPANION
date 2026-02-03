from __future__ import annotations
import uuid
from typing import Any, Dict, List
from companion.core.types import Intent, Risk

class CodingScheduler:
    def __init__(self, repo_state: Dict[str, Any]):
        self.repo_state = repo_state

    def propose(self) -> List[Intent]:
        intents: List[Intent] = []
        for repo in (self.repo_state.get("repos", []) or []):
            intents.append(Intent(
                id=str(uuid.uuid4()),
                domain="coding",
                type="run_tests",
                payload={"repo": repo, "suite": "pytest -q"},
                value=0.6,
                urgency=0.4,
                effort_s=600,
                risk=Risk(),
                preconditions=["repo_available"],
            ))
        return intents
