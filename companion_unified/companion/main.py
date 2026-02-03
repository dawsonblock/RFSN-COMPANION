from __future__ import annotations
import argparse, os, time
from datetime import datetime

from companion.core.ledger import Ledger
from companion.core.gate import Gate
from companion.core.arbiter import GlobalArbiter
from companion.llm.router import build_llm
from companion.config import load_config
from companion.auto_approve.engine import auto_approve_once

from companion.schedulers.messages_scheduler import MessagesScheduler
from companion.schedulers.calendar_scheduler import CalendarScheduler
from companion.schedulers.coding_scheduler import CodingScheduler
from companion.schedulers.moltbook_scheduler import MoltbookScheduler

from companion.controllers.messages_controller import MessagesController
from companion.controllers.calendar_controller import CalendarController
from companion.controllers.coding_controller import CodingController
from companion.controllers.moltbook_controller import MoltbookController

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=5)
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--use_google", action="store_true")
    ap.add_argument("--google_client_secret", default=os.getenv("GOOGLE_CLIENT_SECRET", "secrets/client_secret.json"))
    ap.add_argument("--google_token_dir", default=os.getenv("GOOGLE_TOKEN_DIR", "secrets/tokens"))
    ap.add_argument("--calendar_id", default=os.getenv("GOOGLE_CALENDAR_ID", "primary"))
    ap.add_argument("--repos", nargs="*", default=[])
    args = ap.parse_args()

    os.makedirs(args.artifacts, exist_ok=True)
    cfg = load_config()
    ledger = Ledger(os.path.join(args.artifacts, "ledger.jsonl"))
    gate = Gate()
    arb = GlobalArbiter()
    llm = build_llm()

    msg_ctrl = MessagesController(args.artifacts, llm=llm)
    cal_ctrl = CalendarController(args.artifacts, llm=llm)
    cod_ctrl = CodingController(args.artifacts)
    molt_ctrl = MoltbookController(args.artifacts, llm=llm)

    for t in range(args.ticks):
        if args.use_google:
            from companion.adapters.gmail_reader_google import read_inbox
            from companion.adapters.gcal_reader_google import read_calendar
            inbox_state = read_inbox(client_secret_path=args.google_client_secret, token_path=os.path.join(args.google_token_dir, "gmail_token.json"))
            calendar_state = read_calendar(client_secret_path=args.google_client_secret, token_path=os.path.join(args.google_token_dir, "gcal_token.json"), calendar_id=args.calendar_id, window_days=14)
        else:
            inbox_state = {"threads": []}
            calendar_state = {"events": []}

        repo_state = {"repos": args.repos}
        if cfg.moltbook_enabled:
            try:
                from companion.adapters.moltbook_http import read_feed
                molt_state = read_feed(
                    base_url=cfg.moltbook_base_url,
                    credentials_path=cfg.moltbook_credentials_path,
                    sort=cfg.moltbook_feed_sort,
                    limit=cfg.moltbook_feed_limit,
                )
            except Exception:
                molt_state = {"posts": []}
        else:
            molt_state = {"posts": []}

        intents = []
        intents += MessagesScheduler(inbox_state, llm=llm).propose()
        intents += CalendarScheduler(calendar_state, llm=llm).propose()
        intents += CodingScheduler(repo_state).propose()
        intents += MoltbookScheduler(molt_state).propose()

        chosen = arb.choose(intents)
        if not chosen:
            ledger.append({"ts": datetime.utcnow().isoformat(), "kind":"tick", "tick": t, "note":"no_intents"})
            if cfg.auto_approve and cfg.exec_secret:
                auto_approve_once(args.artifacts, cfg)
            time.sleep(0.1)
            continue

        dec = gate.decide({}, chosen)
        ledger.append({"ts": datetime.utcnow().isoformat(), "kind":"decision", "tick": t, "accepted": dec.accepted, "reason": dec.reason, "intent": chosen.__dict__})

        if not dec.accepted:
            if cfg.auto_approve and cfg.exec_secret:
                auto_approve_once(args.artifacts, cfg)
            time.sleep(0.1)
            continue

        if chosen.domain == "messages":
            res = msg_ctrl.execute(chosen)
        elif chosen.domain == "calendar":
            res = cal_ctrl.execute(chosen)
        elif chosen.domain == "moltbook":
            res = molt_ctrl.execute(chosen)
        else:
            res = cod_ctrl.execute(chosen)

        ledger.append({"ts": datetime.utcnow().isoformat(), "kind":"exec", "tick": t, "status": res.status, "note": res.note, "artifacts": res.artifacts})
        if cfg.auto_approve and cfg.exec_secret:
            auto_approve_once(args.artifacts, cfg)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
