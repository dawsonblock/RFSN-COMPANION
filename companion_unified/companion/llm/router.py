from __future__ import annotations
import os
from typing import Optional
from .types import LLM
from .providers.ollama_http import OllamaHTTP
from .providers.openai_http import OpenAIHTTP
from .providers.anthropic_http import AnthropicHTTP


def build_llm(provider: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None) -> Optional[LLM]:
    provider = (provider or os.getenv("COMPANION_LLM_PROVIDER") or "").strip().lower()
    if not provider:
        return None
    if provider == "ollama":
        return OllamaHTTP(base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), model or os.getenv("OLLAMA_MODEL", "llama3.1"))
    if provider == "openai":
        k = os.getenv("OPENAI_API_KEY")
        if not k:
            return None
        return OpenAIHTTP(k, base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com"), model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    if provider == "anthropic":
        k = os.getenv("ANTHROPIC_API_KEY")
        if not k:
            return None
        return AnthropicHTTP(k, base_url or os.getenv("ANTHROPIC_API_BASE_URL", "https://api.anthropic.com"), model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"))
    return None
