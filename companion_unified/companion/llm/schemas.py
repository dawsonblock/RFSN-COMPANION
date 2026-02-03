from __future__ import annotations
from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field, conint, confloat

Domain = Literal["messages", "coding", "calendar", "moltbook"]

class IntentJSON(BaseModel):
    domain: Domain
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    value: confloat(ge=0.0, le=1.0) = 0.5
    urgency: confloat(ge=0.0, le=1.0) = 0.5
    effort_s: conint(ge=0, le=3600) = 60
    preconditions: List[str] = Field(default_factory=list)

class IntentBatch(BaseModel):
    intents: List[IntentJSON] = Field(default_factory=list)
