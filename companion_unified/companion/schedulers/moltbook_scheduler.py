from __future__ import annotations
import uuid
from typing import Any, Dict, List

from companion.core.types import Intent, Risk


class MoltbookScheduler:
    def __init__(self, feed_state: Dict[str, Any]):
        self.feed_state = feed_state

    def propose(self) -> List[Intent]:
        intents: List[Intent] = []
        posts = (self.feed_state.get("posts", []) or [])[:10]
        for post in posts:
            post_id = str(post.get("id") or post.get("post_id") or "")
            if not post_id:
                continue
            title = str(post.get("title") or "")
            content = str(post.get("content") or post.get("body") or post.get("text") or "")
            intents.append(Intent(
                id=str(uuid.uuid4()),
                domain="moltbook",
                type="draft_moltbook_reply",
                payload={
                    "post_id": post_id,
                    "title": title,
                    "content": content[:2000],
                },
                value=0.4,
                urgency=0.3,
                effort_s=120,
                risk=Risk(),
                preconditions=["has_moltbook_feed"],
            ))
        return intents
