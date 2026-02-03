from __future__ import annotations
from pathlib import Path
from typing import List
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

def get_creds(*, scopes: List[str], client_secret_path: str, token_path: str) -> Credentials:
    client_secret = Path(client_secret_path)
    token_file = Path(token_path)
    if not client_secret.exists():
        raise FileNotFoundError(f"Missing client secret file: {client_secret}")
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
        creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds
