from datetime import datetime, timedelta

from companion.auto_approve.engine import auto_approve_once
from companion.config import Config
from companion.queues.send_queue import SendEmailSpec, spec_hash as send_spec_hash, write as write_send, load as load_send
from companion.queues.calendar_queue import CreateEventSpec, spec_hash as cal_spec_hash, write as write_cal, load as load_cal
from companion_exec.tokens_hmac import verify


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


def test_auto_approve_engine_send(tmp_path):
    cfg = _cfg()
    artifacts = tmp_path
    body = tmp_path / "draft.md"
    body.write_text("hello")
    spec = SendEmailSpec(
        qid="send_1",
        thread_id="t1",
        to="me@example.com",
        subject="Hi",
        body_md_path=str(body),
    )
    h = send_spec_hash(spec)
    send_item = {
        "qid": spec.qid,
        "action": "send_email",
        "spec": {
            "qid": spec.qid,
            "thread_id": spec.thread_id,
            "to": spec.to,
            "subject": spec.subject,
            "body_md_path": spec.body_md_path,
            "reply_to_message_id": spec.reply_to_message_id,
        },
        "spec_hash": h,
        "approval_token": None,
        "status": "pending",
    }
    send_path = artifacts / "messages" / "send_queue.json"
    send_path.parent.mkdir(parents=True, exist_ok=True)
    write_send(str(send_path), [send_item])

    auto_approve_once(str(artifacts), cfg)

    items = load_send(str(send_path))
    assert items
    tok = items[0].get("approval_token")
    assert tok
    assert items[0].get("approved_by") == "auto"
    assert items[0].get("approved_at")
    appr = verify(cfg.exec_secret_bytes, tok)
    assert appr is not None
    assert appr.bind["spec_hash"] == h


def test_auto_approve_engine_event(tmp_path):
    cfg = _cfg()
    artifacts = tmp_path
    desc = tmp_path / "desc.md"
    desc.write_text("details")
    now = datetime.now().astimezone()
    start = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=30)
    spec = CreateEventSpec(
        qid="ev_1",
        calendar_id="primary",
        title="Focus",
        start_iso=start.isoformat(),
        end_iso=end.isoformat(),
        description_md_path=str(desc),
        attendees=[],
    )
    h = cal_spec_hash(spec)
    cal_item = {
        "qid": spec.qid,
        "action": "create_event",
        "spec": {
            "qid": spec.qid,
            "calendar_id": spec.calendar_id,
            "title": spec.title,
            "start_iso": spec.start_iso,
            "end_iso": spec.end_iso,
            "description_md_path": spec.description_md_path,
            "attendees": spec.attendees,
        },
        "spec_hash": h,
        "approval_token": None,
        "status": "pending",
    }
    cal_path = artifacts / "calendar" / "event_queue.json"
    cal_path.parent.mkdir(parents=True, exist_ok=True)
    write_cal(str(cal_path), [cal_item])

    auto_approve_once(str(artifacts), cfg)

    items = load_cal(str(cal_path))
    assert items
    tok = items[0].get("approval_token")
    assert tok
    assert items[0].get("approved_by") == "auto"
    assert items[0].get("approved_at")
    appr = verify(cfg.exec_secret_bytes, tok)
    assert appr is not None
    assert appr.bind["spec_hash"] == h
