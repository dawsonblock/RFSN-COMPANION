from __future__ import annotations

def system_messages_scheduler() -> str:
    return "Propose draft-only message intents. Return strict JSON only."

def user_messages_scheduler(threads_json: str) -> str:
    return (
        "Given inbox threads, propose 3-8 intents. "
        "Allowed types: draft_reply, triage_summary, ask_clarifying_question. "
        "Return JSON: {"intents":[...]}\n\n"
        f"Inbox threads:\n{threads_json}"
    )

def system_draft_email() -> str:
    return "Write a concise email draft. Draft-only. Return only the body."

def user_draft_email(subject: str, context: str) -> str:
    return f"Subject: {subject}\n\nContext:\n{context}\n\nWrite the draft reply body."


def system_moltbook_reply() -> str:
    return "Write a concise Moltbook comment reply. Draft-only. Return only the reply body."


def user_moltbook_reply(title: str, content: str) -> str:
    return f"Post title: {title}\n\nPost content:\n{content}\n\nWrite a helpful, concise reply."


def system_moltbook_post() -> str:
    return "Write a concise Moltbook post. Draft-only. Return only the post body."


def user_moltbook_post(title: str, context: str) -> str:
    return f"Post title: {title}\n\nContext:\n{context}\n\nWrite the post body."
