from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class CreatePostSpec:
    qid: str
    title: str
    body_md_path: str


@dataclass(frozen=True)
class ReplyPostSpec:
    qid: str
    post_id: str
    body_md_path: str


def spec_hash_post(spec: CreatePostSpec) -> str:
    payload = {
        "qid": spec.qid,
        "title": spec.title,
        "body_md_path": spec.body_md_path,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def spec_hash_reply(spec: ReplyPostSpec) -> str:
    payload = {
        "qid": spec.qid,
        "post_id": spec.post_id,
        "body_md_path": spec.body_md_path,
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
