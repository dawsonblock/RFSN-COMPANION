from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Set
from .types import Intent, Decision

@dataclass
class GatePolicy:
    allow_types: Set[str]

def default_policy() -> GatePolicy:
    return GatePolicy(
        allow_types={
            # message drafts + enqueue
            "draft_reply",
            "triage_summary",
            "ask_clarifying_question",
            "enqueue_send_draft",
            # calendar drafts + enqueue
            "agenda_draft",
            "conflict_report",
            "propose_slots",
            "enqueue_event_draft",
            # coding drafts
            "run_tests",
            "draft_patch",
            # moltbook drafts + enqueue
            "draft_moltbook_reply",
            "draft_moltbook_post",
        }
    )

class Gate:
    def __init__(self, policy: GatePolicy | None = None):
        self.policy = policy or default_policy()

    def decide(self, state: Dict[str, Any], intent: Intent) -> Decision:
        if intent.type not in self.policy.allow_types:
            return Decision(intent=intent, accepted=False, reason="type_not_allowlisted")
        if intent.domain not in ("messages","calendar","coding","moltbook"):
            return Decision(intent=intent, accepted=False, reason="unknown_domain")
        if not (0.0 <= intent.value <= 1.0 and 0.0 <= intent.urgency <= 1.0):
            return Decision(intent=intent, accepted=False, reason="bad_priority")
        if not (0 <= intent.effort_s <= 3600):
            return Decision(intent=intent, accepted=False, reason="bad_effort")
        return Decision(intent=intent, accepted=True, reason="ok")
