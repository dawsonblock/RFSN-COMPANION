from __future__ import annotations
import json, uuid
from typing import Any, Dict, List, Optional
from companion.core.types import Intent, Risk
from companion.llm.types import LLM
from companion.llm.schemas import IntentBatch
from companion.llm.promptlib import system_messages_scheduler, user_messages_scheduler
from companion.llm.sanitize import sanitize_untrusted_text

class MessagesScheduler:
    def __init__(self, inbox_state: Dict[str, Any], llm: Optional[LLM] = None):
        self.inbox_state = inbox_state
        self.llm = llm

    def _fallback(self) -> List[Intent]:
        intents: List[Intent] = []
        for th in (self.inbox_state.get("threads", []) or [])[:10]:
            urgency = 0.8 if th.get("unread") else 0.4
            value = 0.7 if th.get("important") else 0.4
            intents.append(Intent(
                id=str(uuid.uuid4()),
                domain="messages",
                type="draft_reply",
                payload={
                    "thread_id": th.get("thread_id"),
                    "message_id": th.get("message_id"),
                    "subject": th.get("subject",""),
                    "snippet": th.get("snippet",""),
                    "from": th.get("from",""),
                },
                value=value,
                urgency=urgency,
                effort_s=60,
                risk=Risk(),
                preconditions=["has_inbox_data"],
            ))
        return intents

    def propose(self) -> List[Intent]:
        if not self.llm:
            return self._fallback()

        threads = (self.inbox_state.get("threads", []) or [])[:20]
        safe_threads = []
        for th in threads:
            safe_threads.append({
                "thread_id": th.get("thread_id"),
                "message_id": th.get("message_id"),
                "from": sanitize_untrusted_text(th.get("from",""), 200),
                "subject": sanitize_untrusted_text(th.get("subject",""), 200),
                "snippet": sanitize_untrusted_text(th.get("snippet",""), 800),
                "unread": bool(th.get("unread", False)),
                "important": bool(th.get("important", False)),
            })

        resp = self.llm.complete(
            system=system_messages_scheduler(),
            user=user_messages_scheduler(json.dumps(safe_threads, ensure_ascii=False)),
            json_mode=True,
        )
        if not resp.json:
            return self._fallback()

        try:
            batch = IntentBatch.model_validate(resp.json)
        except Exception:
            return self._fallback()

        intents: List[Intent] = []
        for it in batch.intents:
            intents.append(Intent(
                id=str(uuid.uuid4()),
                domain=it.domain,
                type=it.type,
                payload=it.payload,
                value=float(it.value),
                urgency=float(it.urgency),
                effort_s=int(it.effort_s),
                risk=Risk(),
                preconditions=it.preconditions or ["has_inbox_data"],
            ))
        return intents
