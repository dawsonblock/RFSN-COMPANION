from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List
from googleapiclient.discovery import build
from .google_oauth import get_creds

GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def read_calendar(*, client_secret_path: str, token_path: str, calendar_id: str = "primary", window_days: int = 14, now: datetime | None = None) -> Dict[str, Any]:
    now = now or datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=window_days)).isoformat() + "Z"
    creds = get_creds(scopes=GCAL_SCOPES, client_secret_path=client_secret_path, token_path=token_path)
    svc = build("calendar", "v3", credentials=creds)
    events_resp = svc.events().list(calendarId=calendar_id, timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy="startTime", maxResults=50).execute()
    events = []
    for ev in events_resp.get("items", []) or []:
        start = (ev.get("start", {}) or {}).get("dateTime") or (ev.get("start", {}) or {}).get("date")
        end = (ev.get("end", {}) or {}).get("dateTime") or (ev.get("end", {}) or {}).get("date")
        events.append({
            "event_id": ev.get("id",""),
            "title": ev.get("summary",""),
            "when": f"{start} -> {end}",
            "description": ev.get("description","") or "",
            "starts_soon": False,
        })
    return {"events": events, "calendar_id": calendar_id, "time_min": time_min, "time_max": time_max}
