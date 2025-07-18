"""
Restricted web‑downloader:
• Allows domains Modrinth, SpigotMC, Hangar
• Only permits .jar files
• Saves into DOWNLOADS_DIR
"""
import re
import requests
import pydantic as py

from ..config import DOWNLOADS_DIR
from ..utils.logging import get_logger

log = get_logger("SafeWebDownloadTool")

_ALLOWED_DOMAINS = (
    r"(?:^|\.)(modrinth\.com|api\.modrinth\.com)$",
    r"(?:^|\.)(spigotmc\.org)$",
    r"(?:^|\.)(hangar\.papermc\.io)$",
)
_DOM_RE = re.compile("|".join(_ALLOWED_DOMAINS), re.I)


class WebArgs(py.BaseModel):
    url: str = py.Field(description="Direct HTTPS link to the plugin JAR.")


class SafeWebDownloadTool:
    NAME = "web_download"
    DESC = (
        "Download a plugin JAR from Modrinth / SpigotMC / Hangar into the local "
        "downloads/ folder. Rejects any other domain or non‑jar content."
    )

    def function_spec(self):
        schema = WebArgs.model_json_schema()
        schema["additionalProperties"] = False
        return {"name": self.NAME, "description": self.DESC, "parameters": schema}

    # Accept both call signatures
    def __call__(self, *args):
        arguments = args[-1]
        data = WebArgs(**arguments)
        url = data.url.strip()

        if not _DOM_RE.search(url):
            return "Rejected – domain not allowed."
        if not url.lower().endswith(".jar"):
            return "Rejected – only .jar downloads permitted."

        local_path = DOWNLOADS_DIR / url.split("/")[-1]
        if local_path.exists():
            return f"{local_path.name} already present."

        try:
            log.info("Downloading %s", url)
            r = requests.get(url, timeout=60, stream=True)
            if r.status_code != 200:
                return f"Error – HTTP {r.status_code}"

            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            return f"Downloaded {local_path.name}"
        except Exception as ex:  # pragma: no cover
            log.exception("Download failed")
            return f"Download failed: {ex}"
