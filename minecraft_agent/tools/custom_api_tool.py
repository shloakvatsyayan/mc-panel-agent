"""
Generic Pelican Panel API tool
──────────────────────────────

Exposes a single “custom_api_call” function so the LLM can hit **any**
endpoint described in pelican_panel_api_reference.md.

Example calls
-------------
custom_api_call({
    "method": "POST",
    "path": "/api/client/servers/abcd-1234/power",
    "json": { "signal": "start" },
    "token_type": "client"
})

custom_api_call({
    "method": "GET",
    "path": "/api/application/servers",
    "token_type": "application"
})
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Literal, Optional
from dotenv import load_dotenv
import pydantic as py
from ..config import PELICAN_BASE_URL, PELICAN_API_KEY, ALLOWED_SERVER_IDS
import requests

from ..utils.logging import get_logger
load_dotenv()

log = get_logger("CustomAPITool")
class APICallArgs(py.BaseModel):
    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str
    params: Dict[str, Any] = {}
    json: Optional[Dict[str, Any]] = None
    token_type: Literal["client", "application"] = "client"

    @py.model_validator(mode="after")
    def ensure_prefix(cls, v):
        if not (
            v.path.startswith("/api/client")
            or v.path.startswith("/api/application")
        ):
            raise ValueError("path must start with /api/client or /api/application")
        return v

class CustomAPITool:
    NAME = "custom_api_call"
    DESC = (
        "Call any Pelican Panel REST endpoint."
        "If you need to upload a file, use the upload file tool instead of this tool."
    )

    def function_spec(self) -> Dict[str, Any]:
        schema = APICallArgs.model_json_schema()
        schema["additionalProperties"] = False
        return {"name": self.NAME, "description": self.DESC, "parameters": schema}

    def __call__(self, *args):
        arguments = args[-1]
        try:
            payload = APICallArgs(**arguments)
        except Exception as e:
            return f"Validation error: {e}"
            
        if not PELICAN_API_KEY:
            return "Client API token not configured (PELICAN_API_KEY env var).",
        headers = {
            "Authorization": f"Bearer {PELICAN_API_KEY}",
            "Accept": "application/vnd.pterodactyl.v1+json",
        }

        url = PELICAN_BASE_URL.rstrip("/") + payload.path

        try:
            resp = requests.request(
                payload.method,
                url,
                params=payload.params or None,
                json=payload.json,
                headers=headers,
                timeout=60,
            )
        except Exception as ex:
            log.exception("Request failed")
            return f"Request failed: {ex}"

        if resp.status_code >= 400:
            return f"HTTP {resp.status_code}: {resp.text}"

        try:
            return json.dumps(resp.json(), indent=2)
        except ValueError:
            return resp.text
