from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class SendEmailSpec:
    qid: str
    thread_id: str
    to: str
    subject: str
    body_md_path: str
    reply_to_message_id: Optional[str] = None

def spec_hash(spec: SendEmailSpec) -> str:
    payload = {
        "qid": spec.qid,
        "thread_id": spec.thread_id,
        "to": spec.to,
        "subject": spec.subject,
        "body_md_path": spec.body_md_path,
        "reply_to_message_id": spec.reply_to_message_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def load(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except FileNotFoundError:
        return []
    except Exception:
        return []

def write(path: str, items: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
