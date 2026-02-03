from __future__ import annotations
import json, urllib.request
from typing import Any, Dict
from ..types import LLMResponse

class OllamaHTTP:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> LLMResponse:
        url = f"{self.base_url}/api/generate"
        prompt = f"<<SYS>>\n{system}\n<</SYS>>\n\n{user}"
        payload: Dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = (data.get("response") or "").strip()
        js = None
        if json_mode:
            try: js = json.loads(text)
            except Exception: js = None
        return LLMResponse(text=text, json=js, model=self.model, usage=None)

    def stream(self, *, system: str, user: str):
        url = f"{self.base_url}/api/generate"
        prompt = f"<<SYS>>\n{system}\n<</SYS>>\n\n{user}"
        payload: Dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": True}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            for line in r:
                if not line:
                    continue
                try:
                    data = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                chunk = data.get("response") or ""
                if chunk:
                    yield chunk
