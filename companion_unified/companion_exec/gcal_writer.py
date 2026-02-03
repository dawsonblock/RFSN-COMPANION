from __future__ import annotations
from googleapiclient.discovery import build
from companion.adapters.google_oauth import get_creds

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def create_event(*, client_secret: str, token_path: str, calendar_id: str, title: str, start_iso: str, end_iso: str, description_md_path: str, attendees: list[str]):
    description = open(description_md_path, "r", encoding="utf-8").read()
    creds = get_creds(scopes=SCOPES, client_secret_path=client_secret, token_path=token_path)
    svc = build("calendar", "v3", credentials=creds)
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
        "attendees": [{"email": a} for a in attendees],
    }
    svc.events().insert(calendarId=calendar_id, body=body).execute()
