from __future__ import annotations
import base64, hashlib, hmac, json, time, uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))

@dataclass(frozen=True)
class Approval:
    token_type: str
    jti: str
    exp: float
    bind: Dict[str, Any]
    sig: str

def mint(secret: bytes, *, token_type: str, ttl_s: int, bind: Dict[str, Any]) -> str:
    payload = {"token_type": token_type, "jti": str(uuid.uuid4()), "exp": time.time() + ttl_s, "bind": bind}
    p = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = _b64(hmac.new(secret, p, hashlib.sha256).digest())
    blob = {"payload": payload, "sig": sig}
    return _b64(json.dumps(blob, sort_keys=True, separators=(",", ":")).encode("utf-8"))

def verify(secret: bytes, token: str) -> Optional[Approval]:
    try:
        blob = json.loads(_b64d(token).decode("utf-8"))
        payload = blob["payload"]
        sig = blob["sig"]
        p = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = _b64(hmac.new(secret, p, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        return Approval(token_type=payload["token_type"], jti=payload["jti"], exp=float(payload["exp"]), bind=dict(payload["bind"]), sig=sig)
    except Exception:
        return None
