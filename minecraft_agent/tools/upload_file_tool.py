"""
UploadFileTool
──────────────
Uploads a file that already exists in the local downloads/ folder to a
specific directory on a Pelican (Pterodactyl) server.

Environment vars required
-------------------------
PELICAN_BASE_URL   – e.g. https://panel.example.com  (defaults to that URL)
PELICAN_API_KEY    – *Client* API token with file-upload permission
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import pydantic as py
import requests

from ..config import DOWNLOADS_DIR, ALLOWED_SERVER_IDS
from ..utils.logging import get_logger

log = get_logger("UploadFileTool")

PELICAN_BASE_URL: str = os.getenv("PELICAN_BASE_URL", "https://panel.example.com")
PELICAN_API_KEY: str | None = os.getenv("PELICAN_API_KEY")


class UploadArgs(py.BaseModel):
    server_id: str = py.Field(
        description="UUID or short ID of the target server (as shown in the panel)."
    )
    file_name: str = py.Field(
        description="Exact name of the file that exists inside the downloads/ folder."
    )
    directory: str = py.Field(
        "/",
        description="Destination path inside the server (leading slash, e.g. /plugins).",
    )

    @py.model_validator(mode="after")
    def _validate_file(cls, v: "UploadArgs") -> "UploadArgs":
        if "/" in v.file_name or ".." in v.file_name:
            raise ValueError("file_name must not contain path separators.")
        local_path = DOWNLOADS_DIR / v.file_name
        if not local_path.is_file():
            raise ValueError(f"{v.file_name} not found in downloads/.")
        return v


class UploadFileTool:
    NAME = "upload_file"
    DESC = (
        "Upload a file (from downloads/) to a Pelican server. "
        "Arguments: server_id, file_name, directory."
    )

    def function_spec(self) -> Dict[str, Any]:
        schema = UploadArgs.model_json_schema()
        schema["additionalProperties"] = False
        return {"name": self.NAME, "description": self.DESC, "parameters": schema}

    def __call__(self, *args):
        if not PELICAN_API_KEY:
            return "Client API token not configured (PELICAN_API_KEY env var)."

        arguments = args[-1]
        try:
            data = UploadArgs(**arguments)
        except Exception as exc:
            return f"Validation error: {exc}"

        file_path = DOWNLOADS_DIR / data.file_name
        if data.server_id not in ALLOWED_SERVER_IDS:
            return f"Access denied: You do not have permission to upload to {data.server_id}."
        
        url = (
            PELICAN_BASE_URL.rstrip("/")
            + f"/api/client/servers/{data.server_id}/files/upload"
        )
        headers = {
            "Authorization": f"Bearer {PELICAN_API_KEY}",
            "Accept": "application/vnd.pterodactyl.v1+json",
        }

        form = {
            "directory": (None, data.directory),
            "files[]": (data.file_name, file_path.open("rb"), "application/octet-stream"),
        }

        try:
            resp = requests.post(url, headers=headers, files=form, timeout=120)
        except Exception as ex:
            log.exception("Upload failed")
            return f"Upload failed: {ex}"

        if resp.status_code >= 400:
            return f"HTTP {resp.status_code}: {resp.text}"

        return (
            f"Uploaded **{data.file_name}** → `{data.directory}` on server "
            f"`{data.server_id}`."
        )
