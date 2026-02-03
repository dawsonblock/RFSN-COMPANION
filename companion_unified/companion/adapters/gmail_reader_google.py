from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List
from googleapiclient.discovery import build
from .google_oauth import get_creds

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()

def _extract_headers(headers: List[Dict[str, str]]) -> Dict[str, str]:
    out = {}
    for h in headers:
        k = (h.get("name") or "").lower()
        v = h.get("value") or ""
        if k:
            out[k] = v
    return out

def read_inbox(*, client_secret_path: str, token_path: str, query: str = "newer_than:14d -category:promotions -category:social", max_results: int = 20) -> Dict[str, Any]:
    creds = get_creds(scopes=GMAIL_SCOPES, client_secret_path=client_secret_path, token_path=token_path)
    svc = build("gmail", "v1", credentials=creds)
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    msgs = resp.get("messages", []) or []
    threads: List[Dict[str, Any]] = []
    for m in msgs:
        msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata").execute()
        payload = msg.get("payload", {}) or {}
        headers = _extract_headers(payload.get("headers", []) or [])
        label_ids = set(msg.get("labelIds", []) or [])
        threads.append({
            "thread_id": msg.get("threadId", m["id"]),
            "message_id": m["id"],
            "subject": headers.get("subject",""),
            "from": headers.get("from",""),
            "snippet": msg.get("snippet","") or "",
            "unread": "UNREAD" in label_ids,
            "important": "IMPORTANT" in label_ids,
            "labels": sorted(list(label_ids)),
        })
    return {"threads": threads, "ts": _now_ts(), "query": query}
