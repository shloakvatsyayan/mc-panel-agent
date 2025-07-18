"""
Centralised runtime configuration.

Reads `.env` once on import.  EVERYTHING that could be dangerous is kept here
so that the rest of the code remains side‑effect‑free.
"""
from pathlib import Path
import os
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# .env                                                                         #
# --------------------------------------------------------------------------- #
load_dotenv()

PELICAN_BASE_URL: str = os.getenv("PELICAN_BASE_URL", "").rstrip("/")
PELICAN_API_KEY:   str = os.getenv("PELICAN_API_KEY",   "")
OPENAI_API_KEY:    str = os.getenv("OPENAI_API_KEY",    "")
OPENAI_MODEL:      str = os.getenv("OPENAI_MODEL",      "o3")
OPENAI_TEMP:       float = float(os.getenv("OPENAI_TEMPERATURE", "0"))

# The **only** server(s) the agent may touch
ALLOWED_SERVER_IDS = {"6dcdb020-5ac5-4867-9bc3-98092e4f71fb"}

# Downloads folder (plugins land here before upload)
DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)
