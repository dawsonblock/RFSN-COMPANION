from __future__ import annotations
import base64
from email.message import EmailMessage
from googleapiclient.discovery import build
from companion.adapters.google_oauth import get_creds

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def send_email(*, client_secret: str, token_path: str, to: str, subject: str, body_md_path: str):
    body = open(body_md_path, "r", encoding="utf-8").read()
    creds = get_creds(scopes=SCOPES, client_secret_path=client_secret, token_path=token_path)
    svc = build("gmail", "v1", credentials=creds)
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
