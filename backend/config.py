import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- LLM provider selection ---
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # --- Storage ---
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    CHROMA_DIR = os.getenv("CHROMA_DIR", "./data/chroma_db")

    # --- Retrieval / chunking ---
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 120))
    TOP_K = int(os.getenv("TOP_K", 5))

    def apply_overrides(self, overlay: dict) -> None:
        """Applies a settings_store overlay on top of the .env defaults.

        Present key -> set instance override. Key missing from the overlay
        but currently overridden -> remove it, falling back to the original
        class-level (.env) value.
        """
        from backend.settings_store import ALLOWED_OVERRIDE_KEYS

        for attr in ALLOWED_OVERRIDE_KEYS:
            if attr in overlay:
                setattr(self, attr, overlay[attr])
            elif attr in self.__dict__:
                delattr(self, attr)


settings = Settings()

# Make sure storage directories exist
os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")) or ".", exist_ok=True)
os.makedirs(settings.CHROMA_DIR, exist_ok=True)

# Overlay any locally-saved settings (from the in-app Settings UI) on top of
# the .env defaults above. Kept at the bottom of the module so `settings`
# already exists by the time settings_store (which never imports this
# module) is pulled in.
from backend.settings_store import load_raw as _load_settings_overlay  # noqa: E402

settings.apply_overrides(_load_settings_overlay())
