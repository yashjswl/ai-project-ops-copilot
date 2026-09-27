"""JSON-file-backed overlay for runtime-configurable settings.

Lets the app override `.env` defaults (API keys, model names, provider choice)
from the UI, persisted per-machine at `data/user_settings.json`. Deliberately
has no dependency on `backend.config` to avoid any import cycle.
"""
import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_FILE = DATA_DIR / "user_settings.json"

# JSON (snake_case) key -> Settings attribute name
FIELD_MAP = {
    "llm_provider": "LLM_PROVIDER",
    "groq_api_key": "GROQ_API_KEY",
    "groq_model": "GROQ_MODEL",
    "gemini_api_key": "GEMINI_API_KEY",
    "gemini_model": "GEMINI_MODEL",
    "ollama_model": "OLLAMA_MODEL",
    "ollama_base_url": "OLLAMA_BASE_URL",
    "top_k": "TOP_K",
}
ATTR_MAP = {v: k for k, v in FIELD_MAP.items()}
ALLOWED_OVERRIDE_KEYS = set(FIELD_MAP.values())
MASK_FIELDS = {"GROQ_API_KEY", "GEMINI_API_KEY"}
MASK_PREFIX = "••••"  # "••••"


def load_raw() -> dict:
    """Reads the overlay file. Never raises — a missing or corrupt file just
    means "no overrides", so the app falls back to .env defaults."""
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def write_raw(overlay: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_FILE.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(overlay, f, indent=2)
    os.replace(tmp_path, SETTINGS_FILE)


def mask(value) -> str:
    if not value:
        return ""
    value = str(value)
    return MASK_PREFIX + value[-4:] if len(value) > 4 else MASK_PREFIX + value


def build_effective_view(settings_obj) -> dict:
    view = {}
    for field, attr in FIELD_MAP.items():
        value = getattr(settings_obj, attr)
        view[field] = mask(value) if attr in MASK_FIELDS else value
    return view


def resolve_update(payload: dict) -> dict:
    """Merges a PUT body (snake_case, only-set fields already filtered by the
    caller) into the persisted overlay and writes it back.

    Per field: absent -> untouched; "" -> explicitly cleared (removed from the
    overlay, reverting to the .env default); starts with the mask prefix ->
    an unmodified echo of a masked value, ignored; otherwise -> stored as the
    new real value.
    """
    overlay = load_raw()
    for field, value in payload.items():
        attr = FIELD_MAP.get(field)
        if attr is None:
            continue
        if value is None:
            continue
        if attr in MASK_FIELDS and isinstance(value, str) and value.startswith(MASK_PREFIX):
            continue
        if value == "":
            overlay.pop(attr, None)
            continue
        overlay[attr] = value
    write_raw(overlay)
    return overlay
