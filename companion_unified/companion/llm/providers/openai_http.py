from __future__ import annotations
import json, urllib.request
from typing import Any, Dict
from ..types import LLMResponse

class OpenAIHTTP:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> LLMResponse:
        url = f"{self.base_url}/v1/responses"
        payload: Dict[str, Any] = {"model": self.model, "input":[{"role":"system","content":system},{"role":"user","content":user}]}
        if json_mode:
            payload["text"] = {"format":{"type":"json_object"}}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Authorization": f"Bearer {self.api_key}", "Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = (data.get("output_text") or "").strip()
        js = None
        if json_mode:
            try: js = json.loads(text)
            except Exception: js = None
        return LLMResponse(text=text, json=js, model=self.model, usage=data.get("usage"))

    def stream(self, *, system: str, user: str):
        # Fallback: generate once and yield in chunks
        resp = self.complete(system=system, user=user, json_mode=False)
        text = resp.text or ""
        for i in range(0, len(text), 120):
            yield text[i:i+120]
