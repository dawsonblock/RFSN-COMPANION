from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass(frozen=True)
class CreateEventSpec:
    qid: str
    calendar_id: str
    title: str
    start_iso: str
    end_iso: str
    description_md_path: str
    attendees: List[str]

def spec_hash(spec: CreateEventSpec) -> str:
    payload = {
        "qid": spec.qid,
        "calendar_id": spec.calendar_id,
        "title": spec.title,
        "start_iso": spec.start_iso,
        "end_iso": spec.end_iso,
        "description_md_path": spec.description_md_path,
        "attendees": spec.attendees,
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
