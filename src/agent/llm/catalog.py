"""LLM provider catalog — danh sách provider + model chuẩn cho UI dropdown."""
from __future__ import annotations

PROVIDER_CATALOG: dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic",
        "base_url": "",
        "models": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        "allow_custom_model": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "allow_custom_model": True,
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "allow_custom_model": True,
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "allow_custom_model": True,
    },
    "mistral": {
        "label": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "models": ["mistral-large-latest", "mistral-small-latest", "open-mixtral-8x7b"],
        "allow_custom_model": True,
    },
    "together": {
        "label": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "models": [
            "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
        ],
        "allow_custom_model": True,
    },
    "ollama": {
        "label": "Ollama (self-hosted)",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3.2", "mistral", "qwen2.5", "phi3"],
        "allow_custom_model": True,
    },
    "greennode": {
        "label": "GreenNode MaaS (VNG Cloud)",
        "base_url": "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1",
        "models": [
            "minimax/minimax-m2.5",
            "qwen/qwen3-5-27b",
            "google/gemma-4-31b-it",
        ],
        "allow_custom_model": True,
    },
}


def get_provider_catalog() -> dict[str, dict]:
    return PROVIDER_CATALOG


def get_models_for_provider(provider: str) -> list[str]:
    return PROVIDER_CATALOG.get(provider, {}).get("models", [])


def get_default_base_url(provider: str) -> str:
    return PROVIDER_CATALOG.get(provider, {}).get("base_url", "")
