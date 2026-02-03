from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional
from companion.core.types import Intent, Risk

class CalendarScheduler:
    def __init__(self, calendar_state: Dict[str, Any], llm=None):
        self.calendar_state = calendar_state
        self.llm = llm

    def propose(self) -> List[Intent]:
        intents: List[Intent] = []
        for ev in (self.calendar_state.get("events", []) or [])[:10]:
            intents.append(Intent(
                id=str(uuid.uuid4()),
                domain="calendar",
                type="agenda_draft",
                payload={
                    "event_id": ev.get("event_id"),
                    "title": ev.get("title",""),
                    "when": ev.get("when",""),
                    "description": ev.get("description",""),
                },
                value=0.6,
                urgency=0.4,
                effort_s=120,
                risk=Risk(),
                preconditions=["has_calendar_data"],
            ))
        return intents
