"""
Upload-File Tool for Pelican / Pterodactyl Panel
───────────────────────────────────────────────

Uploads a single file that already exists in the project-root **downloads/**
folder to the remote server using the Pterodactyl *Client* API.

Endpoint used
-------------
POST /api/client/servers/{SERVER_ID}/files/upload   :contentReference[oaicite:0]{index=0}

Environment variables
---------------------
PELICAN_BASE_URL     – panel URL, e.g. https://panel.example.com
PELICAN_API_KEY      – user-level (ptlc_…) API key
PELICAN_SERVER_ID    – the target server’s short UUID (without dashes)

Arguments exposed to the LLM
----------------------------
• **file_name** (str) – name of the file located in downloads/  
• **remote_path** (str, default “/”) – directory on the server
"""
from __future__ import annotations

import os
import requests
from pathlib import Path
from typing import Any, Dict

import pydantic as py

from ..config import DOWNLOADS_DIR           # already used by your other tools
from ..config import (
    PELICAN_BASE_URL,
    PELICAN_API_KEY,
    ALLOWED_SERVER_IDS,
)
from ..utils.logging import get_logger       # keeps logging unified

log = get_logger("UploadFileTool")

# ──────────────────── auth / configuration ──────────────────────────────
PELICAN_BASE_URL: str = os.getenv("PELICAN_BASE_URL", "https://panel.example.com")
PELICAN_API_KEY: str | None = os.getenv("PELICAN_API_KEY")          # ptlc_…
PELICAN_SERVER_ID = ALLOWED_SERVER_IDS[0]

# ───────────────────── pydantic schema ──────────────────────────────────
class UploadArgs(py.BaseModel):
    file_name: str = py.Field(description="Name of a file inside downloads/")
    remote_path: str = py.Field("/", description="Destination directory (default '/')")

    @py.model_validator(mode="after")
    def _normalize(cls, v):
        # must start with a forward slash
        if not v.remote_path.startswith("/"):
            v.remote_path = "/" + v.remote_path
        return v

# ─────────────────────── tool class ─────────────────────────────────────
class UploadFileTool:
    NAME = "upload_file"
    DESC = (
        "Upload a file from the local downloads/ folder to the server using the "
        "Pterodactyl Client API."
    )

    # JSON-schema spec for the agent
    def function_spec(self) -> Dict[str, Any]:
        schema = UploadArgs.model_json_schema()
        schema["additionalProperties"] = False
        return {"name": self.NAME, "description": self.DESC, "parameters": schema}

    # executor
    def __call__(self, *args):
        arguments = args[-1]               # last positional arg = dict
        try:
            data = UploadArgs(**arguments)
        except Exception as exc:
            return f"Validation error: {exc}"

        # sanity checks
        if not PELICAN_API_KEY:
            return "Client API key (PELICAN_API_KEY) not configured."
        if not PELICAN_SERVER_ID:
            return "Server ID (PELICAN_SERVER_ID) not configured."

        local_path: Path = DOWNLOADS_DIR / data.file_name
        if not local_path.exists():
            return f"{data.file_name} not found in downloads/."

        url = (
            f"{PELICAN_BASE_URL.rstrip('/')}/api/client/servers/"
            f"{PELICAN_SERVER_ID}/files/upload"
        )

        headers = {
            "Authorization": f"Bearer {PELICAN_API_KEY}",
            "Accept": "application/vnd.pterodactyl.v1+json",
        }
        files = {"files[]": open(local_path, "rb")}
        form = {"directory": data.remote_path}

        try:
            log.info("Uploading %s to %s (%s)", local_path.name, data.remote_path, url)
            resp = requests.post(url, headers=headers, files=files, data=form, timeout=120)
        except Exception as ex:
            log.exception("Upload failed")
            return f"Request failed: {ex}"
        finally:
            files["files[]"].close()

        if resp.status_code != 200:
            return f"HTTP {resp.status_code}: {resp.text}"

        return f"Uploaded {local_path.name} → {data.remote_path}"
