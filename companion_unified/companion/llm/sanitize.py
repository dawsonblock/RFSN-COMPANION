from __future__ import annotations
import re

_INJECTION_PATTERNS = [
    r"(?i)ignore (all|any|previous) instructions",
    r"(?i)system prompt",
    r"(?i)developer message",
    r"(?i)exfiltrate",
]

def sanitize_untrusted_text(s: str, max_chars: int = 4000) -> str:
    s = (s or "").strip()
    if len(s) > max_chars:
        s = s[:max_chars] + "\n…[truncated]"
    out_lines = []
    for line in s.splitlines():
        if any(re.search(p, line) for p in _INJECTION_PATTERNS):
            continue
        out_lines.append(line)
    return "\n".join(out_lines).strip()
