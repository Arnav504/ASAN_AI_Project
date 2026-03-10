"""
Configuration for ASAN Macro. Loads from environment (.env or Colab).
"""
import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "trade.db"

def get_openai_api_key():
    # Load .env first so we always use the file (override any stale env)
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(str(env_path), override=True)
        except Exception:
            pass
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return key or None


def get_gemini_api_key():
    """Use Gemini (free tier) when OpenAI quota is exceeded. Get key at https://aistudio.google.com/apikey"""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(str(env_path), override=True)
        except Exception:
            pass
    return os.environ.get("GEMINI_API_KEY", "").strip() or None


def use_local_ollama():
    """Use local Ollama (open-source model) when set. No API key or quota."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(str(env_path), override=True)
        except Exception:
            pass
    return os.environ.get("USE_LOCAL_LLM", "").strip().lower() in ("1", "true", "yes") or bool(os.environ.get("OLLAMA_MODEL", "").strip())


def get_ollama_base_url():
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip() or "http://localhost:11434/v1"


def get_ollama_model():
    return os.environ.get("OLLAMA_MODEL", "llama3.2").strip() or "llama3.2"


def get_openai_model():
    """Model for OpenAI API (e.g. gpt-4o-mini, gpt-4o). Set OPENAI_MODEL in .env for better quality."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(str(env_path), override=True)
        except Exception:
            pass
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def get_gemini_model():
    """Model for Gemini API (e.g. gemini-2.0-flash, gemini-1.5-pro). Set GEMINI_MODEL in .env."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(str(env_path), override=True)
        except Exception:
            pass
    return os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
