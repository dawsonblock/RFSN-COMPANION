from __future__ import annotations
import os

from companion.adapters.moltbook_http import create_post as http_create_post
from companion.adapters.moltbook_http import reply_post as http_reply_post


def _base_url() -> str:
    return os.getenv("MOLTBOOK_BASE_URL", "https://moltbook.com")


def _creds_path() -> str:
    return os.getenv("MOLTBOOK_CREDENTIALS_PATH", "~/.config/moltbook/credentials.json")


def create_post(*, title: str, body_md_path: str):
    body = open(body_md_path, "r", encoding="utf-8").read()
    return http_create_post(base_url=_base_url(), credentials_path=_creds_path(), title=title, content=body)


def reply_post(*, post_id: str, body_md_path: str):
    body = open(body_md_path, "r", encoding="utf-8").read()
    return http_reply_post(base_url=_base_url(), credentials_path=_creds_path(), post_id=post_id, content=body)
