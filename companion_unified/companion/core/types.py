from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal

Domain = Literal["messages", "calendar", "coding", "moltbook"]

@dataclass(frozen=True)
class Risk:
    external_effect: bool = False
    irreversible: bool = False
    sensitive: bool = False
    requires_token: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class Intent:
    id: str
    domain: Domain
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    value: float = 0.5
    urgency: float = 0.5
    effort_s: int = 60
    risk: Risk = field(default_factory=Risk)
    preconditions: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class Decision:
    intent: Intent
    accepted: bool
    reason: str = ""

@dataclass(frozen=True)
class ExecutionResult:
    status: Literal["ok","fail","skipped"]
    artifacts: List[str] = field(default_factory=list)
    note: str = ""
