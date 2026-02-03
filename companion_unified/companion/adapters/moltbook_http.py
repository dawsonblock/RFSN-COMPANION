from __future__ import annotations
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


def _expand(path: str) -> str:
    return os.path.expanduser(path)


def load_credentials(path: str) -> Dict[str, str]:
    p = Path(_expand(path))
    data = json.loads(p.read_text(encoding="utf-8"))
    api_key = data.get("api_key") or data.get("apiKey") or ""
    agent_name = data.get("agent_name") or data.get("agentName") or "companion"
    return {"api_key": api_key, "agent_name": agent_name}


def _request(base_url: str, method: str, path: str, api_key: str, agent_name: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    url = base_url.rstrip("/") + path
    body = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": agent_name,
        "X-Agent-Name": agent_name,
        "Content-Type": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read().decode("utf-8")
    try:
        return json.loads(data)
    except Exception:
        return data


def list_posts(*, base_url: str, credentials_path: str, sort: str = "hot", limit: int = 10) -> List[Dict[str, Any]]:
    creds = load_credentials(credentials_path)
    if not creds.get("api_key"):
        raise RuntimeError("Missing Moltbook api_key in credentials.json")
    qs = f"?sort={sort}&limit={limit}"
    resp = _request(base_url, "GET", f"/posts{qs}", creds["api_key"], creds["agent_name"])
    if isinstance(resp, dict) and isinstance(resp.get("posts"), list):
        return resp["posts"]
    if isinstance(resp, list):
        return resp
    return []


def get_post(*, base_url: str, credentials_path: str, post_id: str) -> Dict[str, Any]:
    creds = load_credentials(credentials_path)
    if not creds.get("api_key"):
        raise RuntimeError("Missing Moltbook api_key in credentials.json")
    resp = _request(base_url, "GET", f"/posts/{post_id}", creds["api_key"], creds["agent_name"])
    return resp if isinstance(resp, dict) else {"raw": resp}


def create_post(*, base_url: str, credentials_path: str, title: str, content: str) -> Dict[str, Any]:
    creds = load_credentials(credentials_path)
    if not creds.get("api_key"):
        raise RuntimeError("Missing Moltbook api_key in credentials.json")
    payload = {"title": title, "content": content}
    resp = _request(base_url, "POST", "/posts", creds["api_key"], creds["agent_name"], payload)
    return resp if isinstance(resp, dict) else {"raw": resp}


def reply_post(*, base_url: str, credentials_path: str, post_id: str, content: str) -> Dict[str, Any]:
    creds = load_credentials(credentials_path)
    if not creds.get("api_key"):
        raise RuntimeError("Missing Moltbook api_key in credentials.json")
    payload = {"content": content}
    resp = _request(base_url, "POST", f"/posts/{post_id}/comments", creds["api_key"], creds["agent_name"], payload)
    return resp if isinstance(resp, dict) else {"raw": resp}


def read_feed(*, base_url: str, credentials_path: str, sort: str = "hot", limit: int = 10) -> Dict[str, Any]:
    posts = list_posts(base_url=base_url, credentials_path=credentials_path, sort=sort, limit=limit)
    return {"posts": posts}
