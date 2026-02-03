from __future__ import annotations
import os
from email.utils import parseaddr
from typing import Optional
from companion.core.types import ExecutionResult, Intent
from companion.llm.types import LLM
from companion.llm.promptlib import system_draft_email, user_draft_email
from companion.llm.sanitize import sanitize_untrusted_text
from companion.queues.send_queue import SendEmailSpec, spec_hash, load, write

class MessagesController:
    def __init__(self, artifacts_dir: str, llm: Optional[LLM] = None):
        self.artifacts_dir = artifacts_dir
        self.llm = llm

    def execute(self, intent: Intent) -> ExecutionResult:
        drafts_dir = os.path.join(self.artifacts_dir, "messages", "drafts")
        os.makedirs(drafts_dir, exist_ok=True)

        if intent.type != "draft_reply":
            return ExecutionResult("skipped", [], "unsupported_intent")

        tid = intent.payload.get("thread_id", "unknown")
        subj = sanitize_untrusted_text(intent.payload.get("subject", ""), 200)
        snip = sanitize_untrusted_text(intent.payload.get("snippet", ""), 2000)

        draft = ""
        if self.llm:
            draft = self.llm.complete(system=system_draft_email(), user=user_draft_email(subj, snip), json_mode=False).text

        path = os.path.join(drafts_dir, f"{tid}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Draft reply\n\nSubject: {subj}\n\nContext:\n{snip}\n\n---\n\nDraft:\n\n{draft}\n")

        # enqueue send
        from_field = intent.payload.get("from", "") or ""
        _, parsed_to = parseaddr(from_field)
        to_addr = parsed_to.strip() if parsed_to else ""
        queue_path = os.path.join(self.artifacts_dir, "messages", "send_queue.json")
        items = load(queue_path)
        qid = f"send_{tid}"
        spec = SendEmailSpec(
            qid=qid,
            thread_id=tid,
            to=to_addr,  # empty if parsing fails
            subject=subj,
            body_md_path=path,
            reply_to_message_id=intent.payload.get("message_id"),
        )
        h = spec_hash(spec)
        items.append({
            "qid": qid,
            "action": "send_email",
            "spec": {
                "qid": spec.qid,
                "thread_id": spec.thread_id,
                "to": spec.to,
                "subject": spec.subject,
                "body_md_path": spec.body_md_path,
                "reply_to_message_id": spec.reply_to_message_id,
            },
            "spec_hash": h,
            "approval_token": None,
            "approved_by": None,
            "approved_at": None,
            "status": "pending",
        })
        write(queue_path, items)
        return ExecutionResult("ok", [path, queue_path], "draft_created_and_enqueued")
