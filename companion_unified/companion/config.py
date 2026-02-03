from __future__ import annotations
from dataclasses import dataclass
import os


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except Exception:
        return default


@dataclass(frozen=True)
class Config:
    llm_provider: str
    ollama_base_url: str
    ollama_model: str
    exec_secret: str
    auto_approve: bool
    auto_approve_policy: str
    self_email: str
    auto_approve_ttl_s: int
    event_window_days: int
    event_max_duration_min: int
    event_start_hour: int
    event_end_hour: int
    auto_calendar_id: str
    moltbook_enabled: bool
    moltbook_base_url: str
    moltbook_credentials_path: str
    moltbook_feed_sort: str
    moltbook_feed_limit: int

    @property
    def exec_secret_bytes(self) -> bytes:
        return self.exec_secret.encode("utf-8") if self.exec_secret else b""


def load_config() -> Config:
    return Config(
        llm_provider=(os.getenv("COMPANION_LLM_PROVIDER") or "").strip().lower(),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        exec_secret=os.getenv("COMPANION_EXEC_SECRET", ""),
        auto_approve=_get_bool("COMPANION_AUTO_APPROVE", False),
        auto_approve_policy=(os.getenv("COMPANION_AUTO_APPROVE_POLICY") or "conservative").strip().lower(),
        self_email=(os.getenv("COMPANION_SELF_EMAIL") or "").strip(),
        auto_approve_ttl_s=_get_int("COMPANION_AUTO_APPROVE_TTL_S", 600),
        event_window_days=_get_int("COMPANION_AUTO_APPROVE_EVENT_WINDOW_DAYS", 7),
        event_max_duration_min=_get_int("COMPANION_AUTO_APPROVE_EVENT_MAX_DURATION_MIN", 120),
        event_start_hour=_get_int("COMPANION_AUTO_APPROVE_EVENT_START_HOUR", 8),
        event_end_hour=_get_int("COMPANION_AUTO_APPROVE_EVENT_END_HOUR", 20),
        auto_calendar_id=os.getenv("COMPANION_AUTO_APPROVE_CALENDAR_ID", "primary"),
        moltbook_enabled=_get_bool("MOLTBOOK_ENABLED", False),
        moltbook_base_url=os.getenv("MOLTBOOK_BASE_URL", "https://moltbook.com"),
        moltbook_credentials_path=os.getenv("MOLTBOOK_CREDENTIALS_PATH", "~/.config/moltbook/credentials.json"),
        moltbook_feed_sort=os.getenv("MOLTBOOK_FEED_SORT", "hot"),
        moltbook_feed_limit=_get_int("MOLTBOOK_FEED_LIMIT", 10),
    )
