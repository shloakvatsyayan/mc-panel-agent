"""
Minimal Pelican (Pterodactyl v1) *client* API wrapper
====================================================

Only the endpoints required by the Minecraft‑panel agent are implemented.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List

import requests

from .config import (
    ALLOWED_SERVER_IDS,
    PELICAN_BASE_URL,
    PELICAN_API_KEY,
)
from .utils.logging import get_logger

log = get_logger("PelicanClient")


class PelicanError(RuntimeError):
    """Raised for HTTP errors or whitelist violations."""


class PelicanClient:
    """
    Thin convenience wrapper around the Pterodactyl Client API.
    Every public method first checks that *server_id* is in the hard whitelist.
    """

    _HEADERS = {
        "Authorization": f"Bearer {PELICAN_API_KEY}",
        "Accept": "application/vnd.pterodactyl.v1+json",
        "User-Agent": "MC-Panel-Agent/0.2",
    }

    # ---------- internal helpers ------------------------------------------ #
    def _url(self, path: str) -> str:
        return f"{PELICAN_BASE_URL.rstrip('/')}{path}"

    def _request(self, method: str, path: str, **kw):
        url = self._url(path)
        log.debug("%s %s", method.upper(), url)

        resp = requests.request(method, url, headers=self._HEADERS, timeout=30, **kw)
        if resp.status_code >= 400:
            raise PelicanError(f"{resp.status_code} {resp.reason}: {resp.text}")

        # JSON when possible, else raw text (directory listings are JSON)
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            return resp.json()
        return resp.text
    
    def upload_file(self, server_id: str, local_path: Path, remote_path: str) -> None:
        """
        Upload *local_path* to *remote_path* using the `/files/write` endpoint.

        The older `/files/upload` route rejects POST for the Client API, so we
        base64‑encode the JAR and send it to `/files/write` instead.
        """
        self._assert_allowed(server_id)

        file_b64 = base64.b64encode(local_path.read_bytes()).decode()
        payload = {
            "file": remote_path,          # e.g. "/plugins/EssentialsX.jar"
            "content": file_b64,
            "path": remote_path,
            "encoding": "base64",
        }
        self._request(
            "POST",
            f"/api/client/servers/{server_id}/files/write",
            json=payload,
        )

    # ---------- guard ------------------------------------------------------ #
    @staticmethod
    def _assert_allowed(server_id: str) -> None:
        if server_id not in ALLOWED_SERVER_IDS:
            raise PelicanError("Server ID not in whitelist")
