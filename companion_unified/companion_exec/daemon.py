from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Any, Dict, List
from .tokens_hmac import verify
from .gmail_writer import send_email
from .gcal_writer import create_event
from .moltbook_writer import create_post, reply_post

ART = Path(os.getenv("COMPANION_ARTIFACTS_DIR", "artifacts"))
SEND_Q = ART / "messages" / "send_queue.json"
CAL_Q  = ART / "calendar" / "event_queue.json"
MOLT_Q = ART / "moltbook" / "post_queue.json"
LEDGER = ART / "ledger.jsonl"
EXEC_DB = ART / ".exec_executed.json"

def ledger_append(rec: Dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def load_list(path: Path) -> List[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or []
    except FileNotFoundError:
        return []
    except Exception:
        return []

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_db() -> Dict[str, str]:
    try:
        return json.loads(EXEC_DB.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def save_db(db: Dict[str, str]) -> None:
    write_json(EXEC_DB, db)

def main():
    secret = os.getenv("COMPANION_EXEC_SECRET", "").encode("utf-8")
    if not secret:
        raise RuntimeError("Set COMPANION_EXEC_SECRET")

    while True:
        db = load_db()

        send_q = load_list(SEND_Q)
        cal_q  = load_list(CAL_Q)
        molt_q = load_list(MOLT_Q)

        changed_send = False
        changed_cal = False
        changed_molt = False

        for item in send_q:
            qid = item.get("qid")
            if not qid or qid in db or item.get("status") != "pending":
                continue
            tok = item.get("approval_token")
            if not tok:
                continue
            appr = verify(secret, tok)
            if not appr or time.time() > appr.exp or appr.token_type != "send_email":
                item["status"] = "rejected"
                item["reason"] = "invalid_or_expired_token"
                db[qid] = item["status"]
                ledger_append({"kind":"exec_reject","qid":qid,"reason":item["reason"]})
                changed_send = True
                continue
            if appr.bind.get("qid") != qid or appr.bind.get("spec_hash") != item.get("spec_hash"):
                item["status"] = "rejected"
                item["reason"] = "token_bind_mismatch"
                db[qid] = item["status"]
                ledger_append({"kind":"exec_reject","qid":qid,"reason":item["reason"]})
                changed_send = True
                continue
            try:
                spec = item["spec"]
                if not spec.get("to"):
                    raise ValueError("spec.to is empty; fill recipient email before approval")
                send_email(
                    client_secret=os.getenv("GOOGLE_CLIENT_SECRET","secrets/client_secret.json"),
                    token_path=os.getenv("GMAIL_SEND_TOKEN","secrets/tokens/gmail_send_token.json"),
                    to=spec["to"],
                    subject=spec["subject"],
                    body_md_path=spec["body_md_path"],
                )
                item["status"] = "done"
                db[qid] = "done"
                ledger_append({"kind":"exec_ok","qid":qid,"action":"send_email"})
                changed_send = True
            except Exception as e:
                item["status"] = "error"
                item["reason"] = str(e)[:300]
                db[qid] = "error"
                ledger_append({"kind":"exec_error","qid":qid,"action":"send_email","err":item["reason"]})
                changed_send = True

        for item in cal_q:
            qid = item.get("qid")
            if not qid or qid in db or item.get("status") != "pending":
                continue
            tok = item.get("approval_token")
            if not tok:
                continue
            appr = verify(secret, tok)
            if not appr or time.time() > appr.exp or appr.token_type != "create_event":
                item["status"] = "rejected"
                item["reason"] = "invalid_or_expired_token"
                db[qid] = item["status"]
                ledger_append({"kind":"exec_reject","qid":qid,"reason":item["reason"]})
                changed_cal = True
                continue
            if appr.bind.get("qid") != qid or appr.bind.get("spec_hash") != item.get("spec_hash"):
                item["status"] = "rejected"
                item["reason"] = "token_bind_mismatch"
                db[qid] = item["status"]
                ledger_append({"kind":"exec_reject","qid":qid,"reason":item["reason"]})
                changed_cal = True
                continue
            try:
                spec = item["spec"]
                create_event(
                    client_secret=os.getenv("GOOGLE_CLIENT_SECRET","secrets/client_secret.json"),
                    token_path=os.getenv("GCAL_WRITE_TOKEN","secrets/tokens/gcal_write_token.json"),
                    calendar_id=spec["calendar_id"],
                    title=spec["title"],
                    start_iso=spec["start_iso"],
                    end_iso=spec["end_iso"],
                    description_md_path=spec["description_md_path"],
                    attendees=spec.get("attendees", []),
                )
                item["status"] = "done"
                db[qid] = "done"
                ledger_append({"kind":"exec_ok","qid":qid,"action":"create_event"})
                changed_cal = True
            except Exception as e:
                item["status"] = "error"
                item["reason"] = str(e)[:300]
                db[qid] = "error"
                ledger_append({"kind":"exec_error","qid":qid,"action":"create_event","err":item["reason"]})
                changed_cal = True

        for item in molt_q:
            qid = item.get("qid")
            if not qid or qid in db or item.get("status") != "pending":
                continue
            tok = item.get("approval_token")
            if not tok:
                continue
            appr = verify(secret, tok)
            if not appr or time.time() > appr.exp or appr.token_type not in ("moltbook_post", "moltbook_reply"):
                item["status"] = "rejected"
                item["reason"] = "invalid_or_expired_token"
                db[qid] = item["status"]
                ledger_append({"kind":"exec_reject","qid":qid,"reason":item["reason"]})
                changed_molt = True
                continue
            if appr.bind.get("qid") != qid or appr.bind.get("spec_hash") != item.get("spec_hash"):
                item["status"] = "rejected"
                item["reason"] = "token_bind_mismatch"
                db[qid] = item["status"]
                ledger_append({"kind":"exec_reject","qid":qid,"reason":item["reason"]})
                changed_molt = True
                continue
            try:
                spec = item["spec"]
                if item.get("action") == "create_post":
                    create_post(
                        title=spec["title"],
                        body_md_path=spec["body_md_path"],
                    )
                    item["status"] = "done"
                    db[qid] = "done"
                    ledger_append({"kind":"exec_ok","qid":qid,"action":"moltbook_post"})
                elif item.get("action") == "reply_post":
                    reply_post(
                        post_id=spec["post_id"],
                        body_md_path=spec["body_md_path"],
                    )
                    item["status"] = "done"
                    db[qid] = "done"
                    ledger_append({"kind":"exec_ok","qid":qid,"action":"moltbook_reply"})
                else:
                    raise ValueError("unknown_moltbook_action")
                changed_molt = True
            except Exception as e:
                item["status"] = "error"
                item["reason"] = str(e)[:300]
                db[qid] = "error"
                ledger_append({"kind":"exec_error","qid":qid,"action":"moltbook","err":item["reason"]})
                changed_molt = True

        if changed_send:
            write_json(SEND_Q, send_q)
        if changed_cal:
            write_json(CAL_Q, cal_q)
        if changed_molt:
            write_json(MOLT_Q, molt_q)
        save_db(db)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
