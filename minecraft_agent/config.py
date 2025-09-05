"""
Centralised runtime configuration.

Reads `.env` once on import.  EVERYTHING that could be dangerous is kept here
so that the rest of the code remains side‑effect‑free.
"""
from pathlib import Path
import os
import json
from dotenv import load_dotenv

load_dotenv()

PELICAN_BASE_URL: str = os.getenv("PELICAN_BASE_URL", "").rstrip("/")
PELICAN_API_KEY:   str = os.getenv("PELICAN_API_KEY",   "")
OPENAI_API_KEY:    str = os.getenv("OPENAI_API_KEY",    "")
OPENAI_MODEL:      str = os.getenv("OPENAI_MODEL",      "o3")
OPENAI_TEMP:       float = float(os.getenv("OPENAI_TEMPERATURE", "0"))

DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

if Path("server_ids.json").exists():
    with open("server_ids.json", "r") as f:
        server_ids = json.load(f)
else:
    server_ids = []
ALLOWED_SERVER_IDS = server_ids