from __future__ import annotations
import os, uuid
from typing import Optional
from companion.core.types import ExecutionResult, Intent
from companion.llm.sanitize import sanitize_untrusted_text
from companion.queues.calendar_queue import CreateEventSpec, spec_hash, load, write

class CalendarController:
    def __init__(self, artifacts_dir: str, llm: Optional[object] = None):
        self.artifacts_dir = artifacts_dir
        self.llm = llm

    def execute(self, intent: Intent) -> ExecutionResult:
        drafts_dir = os.path.join(self.artifacts_dir, "calendar", "drafts")
        os.makedirs(drafts_dir, exist_ok=True)

        if intent.type == "agenda_draft":
            eid = intent.payload.get("event_id", "unknown")
            title = sanitize_untrusted_text(intent.payload.get("title",""), 200)
            when = sanitize_untrusted_text(intent.payload.get("when",""), 200)
            desc = sanitize_untrusted_text(intent.payload.get("description",""), 2000)
            path = os.path.join(drafts_dir, f"{eid}_agenda.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Agenda Draft\n\nEvent: {title}\nWhen: {when}\n\n{desc}\n")
            return ExecutionResult("ok", [path], "agenda_draft_created")

        if intent.type == "enqueue_event_draft":
            cal_id = intent.payload.get("calendar_id","primary")
            title = sanitize_untrusted_text(intent.payload.get("title",""), 200)
            start_iso = intent.payload.get("start_iso","")
            end_iso = intent.payload.get("end_iso","")
            attendees = list(intent.payload.get("attendees", []))
            desc = sanitize_untrusted_text(intent.payload.get("description",""), 2000)

            desc_path = os.path.join(drafts_dir, f"event_{uuid.uuid4().hex}.md")
            with open(desc_path, "w", encoding="utf-8") as f:
                f.write(desc)

            queue_path = os.path.join(self.artifacts_dir, "calendar", "event_queue.json")
            items = load(queue_path)

            qid = f"create_event_{uuid.uuid4().hex}"
            spec = CreateEventSpec(qid=qid, calendar_id=cal_id, title=title, start_iso=start_iso, end_iso=end_iso, description_md_path=desc_path, attendees=attendees)
            h = spec_hash(spec)
            items.append({
                "qid": qid,
                "action": "create_event",
                "spec": {
                    "qid": spec.qid,
                    "calendar_id": spec.calendar_id,
                    "title": spec.title,
                    "start_iso": spec.start_iso,
                    "end_iso": spec.end_iso,
                    "description_md_path": spec.description_md_path,
                    "attendees": spec.attendees,
                },
                "spec_hash": h,
                "approval_token": None,
                "approved_by": None,
                "approved_at": None,
                "status": "pending",
            })
            write(queue_path, items)
            return ExecutionResult("ok", [desc_path, queue_path], "event_enqueued")

        return ExecutionResult("skipped", [], "unsupported_intent")
