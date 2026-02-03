from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Iterable

@dataclass(frozen=True)
class LLMResponse:
    text: str
    json: Optional[Dict[str, Any]] = None
    model: str = ""
    usage: Optional[Dict[str, Any]] = None

class LLM(Protocol):
    def complete(self, *, system: str, user: str, json_mode: bool = False) -> LLMResponse:
        ...

    def stream(self, *, system: str, user: str) -> Iterable[str]:
        ...
