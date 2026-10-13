"""Runtime configuration, read from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
DB_PATH = Path(os.environ.get("ADJ_DB_PATH", DATA_DIR / "adj.sqlite"))
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"


def _load_dotenv() -> None:
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

ANTHROPIC_MODEL = os.environ.get("ADJ_LLM_MODEL", "claude-opus-5-5")
MAX_UPLOAD_MB = int(os.environ.get("ADJ_MAX_UPLOAD_MB", "50"))
MAX_ROWS = int(os.environ.get("ADJ_MAX_ROWS", "500000"))
DEFAULT_ALPHA = float(os.environ.get("ADJ_ALPHA", "0.05"))
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "ADJ_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]


def llm_available() -> bool:
    """True when an Anthropic credential is configured for AI narrative mode."""
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
