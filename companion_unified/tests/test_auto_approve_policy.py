from datetime import datetime, timedelta

from companion.auto_approve.policy import can_auto_approve_send, can_auto_approve_event
from companion.config import Config
from companion.queues.send_queue import SendEmailSpec
from companion.queues.calendar_queue import CreateEventSpec


def _cfg(**overrides) -> Config:
    base = dict(
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3.1",
        exec_secret="secret",
        auto_approve=True,
        auto_approve_policy="conservative",
        self_email="me@example.com",
        auto_approve_ttl_s=600,
        event_window_days=7,
        event_max_duration_min=120,
        event_start_hour=8,
        event_end_hour=20,
        auto_calendar_id="primary",
        moltbook_enabled=False,
        moltbook_base_url="https://moltbook.com",
        moltbook_credentials_path="~/.config/moltbook/credentials.json",
        moltbook_feed_sort="hot",
        moltbook_feed_limit=10,
    )
    base.update(overrides)
    return Config(**base)


def test_policy_send_accepts_self(tmp_path):
    body = tmp_path / "draft.md"
    body.write_text("hello")
    spec = SendEmailSpec(
        qid="send_1",
        thread_id="t1",
        to="me@example.com",
        subject="Hi",
        body_md_path=str(body),
    )
    assert can_auto_approve_send(spec, _cfg())


def test_policy_send_rejects_other(tmp_path):
    body = tmp_path / "draft.md"
    body.write_text("hello")
    spec = SendEmailSpec(
        qid="send_1",
        thread_id="t1",
        to="other@example.com",
        subject="Hi",
        body_md_path=str(body),
    )
    assert not can_auto_approve_send(spec, _cfg())


def test_policy_send_rejects_empty_to(tmp_path):
    body = tmp_path / "draft.md"
    body.write_text("hello")
    spec = SendEmailSpec(
        qid="send_1",
        thread_id="t1",
        to="",
        subject="Hi",
        body_md_path=str(body),
    )
    assert not can_auto_approve_send(spec, _cfg())


def test_policy_event_accepts_simple():
    now = datetime.now().astimezone()
    start = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=60)
    spec = CreateEventSpec(
        qid="ev1",
        calendar_id="primary",
        title="Focus time",
        start_iso=start.isoformat(),
        end_iso=end.isoformat(),
        description_md_path="desc.md",
        attendees=[],
    )
    assert can_auto_approve_event(spec, _cfg())


def test_policy_event_rejects_attendees():
    now = datetime.now().astimezone()
    start = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=60)
    spec = CreateEventSpec(
        qid="ev1",
        calendar_id="primary",
        title="Focus time",
        start_iso=start.isoformat(),
        end_iso=end.isoformat(),
        description_md_path="desc.md",
        attendees=["a@example.com"],
    )
    assert not can_auto_approve_event(spec, _cfg())


def test_policy_event_rejects_outside_window():
    now = datetime.now().astimezone()
    start = (now + timedelta(days=10)).replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=60)
    spec = CreateEventSpec(
        qid="ev1",
        calendar_id="primary",
        title="Later",
        start_iso=start.isoformat(),
        end_iso=end.isoformat(),
        description_md_path="desc.md",
        attendees=[],
    )
    assert not can_auto_approve_event(spec, _cfg())
