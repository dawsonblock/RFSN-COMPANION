from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from companion.config import Config
from companion.auto_approve.policy import can_auto_approve_send, can_auto_approve_event
from companion.queues.send_queue import SendEmailSpec, spec_hash as send_spec_hash, load as load_send
from companion.queues.calendar_queue import CreateEventSpec, spec_hash as cal_spec_hash, load as load_cal
from companion_exec.tokens_hmac import mint


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


def _ledger_append(path: Path, rec: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _build_send_spec(item: Dict[str, Any]) -> Tuple[SendEmailSpec | None, str | None]:
    spec = item.get("spec") or {}
    try:
        s = SendEmailSpec(
            qid=spec["qid"],
            thread_id=spec.get("thread_id", ""),
            to=spec.get("to", ""),
            subject=spec.get("subject", ""),
            body_md_path=spec.get("body_md_path", ""),
            reply_to_message_id=spec.get("reply_to_message_id"),
        )
    except Exception:
        return None, None
    h = item.get("spec_hash") or send_spec_hash(s)
    return s, h


def _build_event_spec(item: Dict[str, Any]) -> Tuple[CreateEventSpec | None, str | None]:
    spec = item.get("spec") or {}
    try:
        s = CreateEventSpec(
            qid=spec["qid"],
            calendar_id=spec.get("calendar_id", ""),
            title=spec.get("title", ""),
            start_iso=spec.get("start_iso", ""),
            end_iso=spec.get("end_iso", ""),
            description_md_path=spec.get("description_md_path", ""),
            attendees=list(spec.get("attendees", []) or []),
        )
    except Exception:
        return None, None
    h = item.get("spec_hash") or cal_spec_hash(s)
    return s, h


def auto_approve_once(artifacts_dir: str, cfg: Config) -> int:
    if not cfg.auto_approve or not cfg.exec_secret:
        return 0

    art = Path(artifacts_dir)
    send_q = art / "messages" / "send_queue.json"
    cal_q = art / "calendar" / "event_queue.json"
    ledger = art / "ledger.jsonl"

    send_items = load_send(str(send_q))
    cal_items = load_cal(str(cal_q))

    approvals = 0
    changed_send = False
    changed_cal = False

    now_iso = datetime.utcnow().isoformat()

    for item in send_items:
        if item.get("status") != "pending" or item.get("approval_token"):
            continue
        spec, h = _build_send_spec(item)
        if not spec or not h:
            continue
        if not can_auto_approve_send(spec, cfg):
            continue
        token = mint(cfg.exec_secret_bytes, token_type="send_email", ttl_s=cfg.auto_approve_ttl_s, bind={"qid": spec.qid, "spec_hash": h})
        item["approval_token"] = token
        item["approved_by"] = "auto"
        item["approved_at"] = now_iso
        item["spec_hash"] = h
        approvals += 1
        changed_send = True
        _ledger_append(ledger, {"ts": now_iso, "kind": "auto_approve", "qid": spec.qid, "action": "send_email"})

    for item in cal_items:
        if item.get("status") != "pending" or item.get("approval_token"):
            continue
        spec, h = _build_event_spec(item)
        if not spec or not h:
            continue
        if not can_auto_approve_event(spec, cfg):
            continue
        token = mint(cfg.exec_secret_bytes, token_type="create_event", ttl_s=cfg.auto_approve_ttl_s, bind={"qid": spec.qid, "spec_hash": h})
        item["approval_token"] = token
        item["approved_by"] = "auto"
        item["approved_at"] = now_iso
        item["spec_hash"] = h
        approvals += 1
        changed_cal = True
        _ledger_append(ledger, {"ts": now_iso, "kind": "auto_approve", "qid": spec.qid, "action": "create_event"})

    if changed_send:
        _atomic_write_json(send_q, send_items)
    if changed_cal:
        _atomic_write_json(cal_q, cal_items)

    return approvals
