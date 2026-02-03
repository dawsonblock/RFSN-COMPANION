from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

from companion.config import Config
from companion.queues.send_queue import SendEmailSpec
from companion.queues.calendar_queue import CreateEventSpec


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _now_local() -> datetime:
    return datetime.now().astimezone()


def can_auto_approve_send(spec: SendEmailSpec, cfg: Config) -> bool:
    if cfg.auto_approve_policy != "conservative":
        return False
    if not spec.to or not cfg.self_email:
        return False
    if spec.to.strip().lower() != cfg.self_email.strip().lower():
        return False
    if not spec.subject or len(spec.subject) > 200:
        return False
    try:
        with open(spec.body_md_path, "r", encoding="utf-8"):
            pass
    except Exception:
        return False
    return True


def can_auto_approve_event(spec: CreateEventSpec, cfg: Config) -> bool:
    if cfg.auto_approve_policy != "conservative":
        return False
    if spec.calendar_id != cfg.auto_calendar_id:
        return False
    if not spec.title:
        return False
    if spec.attendees:
        return False

    start = _parse_iso(spec.start_iso)
    end = _parse_iso(spec.end_iso)
    if not start or not end:
        return False

    now_local = _now_local()
    try:
        start_local = start.astimezone()
        end_local = end.astimezone()
    except Exception:
        return False

    if start_local <= now_local:
        return False
    if start_local - now_local > timedelta(days=cfg.event_window_days):
        return False

    dur_min = (end_local - start_local).total_seconds() / 60.0
    if dur_min <= 0 or dur_min > cfg.event_max_duration_min:
        return False

    if not (cfg.event_start_hour <= start_local.hour <= cfg.event_end_hour):
        return False
    if not (cfg.event_start_hour <= end_local.hour <= cfg.event_end_hour):
        return False

    return True
