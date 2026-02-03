from __future__ import annotations
import os, uuid
from typing import Optional

from companion.core.types import ExecutionResult, Intent
from companion.llm.types import LLM
from companion.llm.promptlib import system_moltbook_reply, user_moltbook_reply, system_moltbook_post, user_moltbook_post
from companion.llm.sanitize import sanitize_untrusted_text
from companion.queues.moltbook_queue import CreatePostSpec, ReplyPostSpec, spec_hash_post, spec_hash_reply, load, write


class MoltbookController:
    def __init__(self, artifacts_dir: str, llm: Optional[LLM] = None):
        self.artifacts_dir = artifacts_dir
        self.llm = llm

    def _safe_id(self, raw: str) -> str:
        keep = []
        for ch in raw:
            if ch.isalnum() or ch in ("-", "_"):
                keep.append(ch)
        return "".join(keep)[:64] or uuid.uuid4().hex

    def _ensure_queue(self, queue_path: str, qid: str) -> bool:
        items = load(queue_path)
        for it in items:
            if it.get("qid") == qid:
                return False
        return True

    def execute(self, intent: Intent) -> ExecutionResult:
        drafts_dir = os.path.join(self.artifacts_dir, "moltbook", "drafts")
        os.makedirs(drafts_dir, exist_ok=True)

        if intent.type == "draft_moltbook_reply":
            post_id = sanitize_untrusted_text(intent.payload.get("post_id", ""), 200)
            title = sanitize_untrusted_text(intent.payload.get("title", ""), 200)
            content = sanitize_untrusted_text(intent.payload.get("content", ""), 4000)

            queue_path = os.path.join(self.artifacts_dir, "moltbook", "post_queue.json")
            safe_post_id = self._safe_id(post_id)
            qid = f"molt_reply_{safe_post_id}"
            if not self._ensure_queue(queue_path, qid):
                return ExecutionResult("ok", [queue_path], "draft_exists_skip_enqueue")

            draft = ""
            if self.llm:
                draft = self.llm.complete(
                    system=system_moltbook_reply(),
                    user=user_moltbook_reply(title, content),
                    json_mode=False,
                ).text

            path = os.path.join(drafts_dir, f"reply_{safe_post_id}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Moltbook Reply Draft\n\nPost: {title}\n\nContext:\n{content}\n\n---\n\nDraft:\n\n{draft}\n")

            spec = ReplyPostSpec(qid=qid, post_id=post_id, body_md_path=path)
            h = spec_hash_reply(spec)
            items = load(queue_path)
            items.append({
                "qid": qid,
                "action": "reply_post",
                "spec": {
                    "qid": spec.qid,
                    "post_id": spec.post_id,
                    "title": title,
                    "body_md_path": spec.body_md_path,
                },
                "spec_hash": h,
                "approval_token": None,
                "approved_by": None,
                "approved_at": None,
                "status": "pending",
            })
            write(queue_path, items)
            return ExecutionResult("ok", [path, queue_path], "reply_draft_created_and_enqueued")

        if intent.type == "draft_moltbook_post":
            title = sanitize_untrusted_text(intent.payload.get("title", ""), 200)
            context = sanitize_untrusted_text(intent.payload.get("context", ""), 4000)

            draft = ""
            if self.llm:
                draft = self.llm.complete(
                    system=system_moltbook_post(),
                    user=user_moltbook_post(title, context),
                    json_mode=False,
                ).text

            path = os.path.join(drafts_dir, f"post_{uuid.uuid4().hex}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Moltbook Post Draft\n\nTitle: {title}\n\nContext:\n{context}\n\n---\n\nDraft:\n\n{draft}\n")

            queue_path = os.path.join(self.artifacts_dir, "moltbook", "post_queue.json")
            qid = f"molt_post_{uuid.uuid4().hex}"
            spec = CreatePostSpec(qid=qid, title=title, body_md_path=path)
            h = spec_hash_post(spec)
            items = load(queue_path)
            items.append({
                "qid": qid,
                "action": "create_post",
                "spec": {
                    "qid": spec.qid,
                    "title": spec.title,
                    "body_md_path": spec.body_md_path,
                },
                "spec_hash": h,
                "approval_token": None,
                "approved_by": None,
                "approved_at": None,
                "status": "pending",
            })
            write(queue_path, items)
            return ExecutionResult("ok", [path, queue_path], "post_draft_created_and_enqueued")

        return ExecutionResult("skipped", [], "unsupported_intent")
