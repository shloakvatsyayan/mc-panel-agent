"""
Simply expose the list of JARs available in ./downloads so the LLM can decide
whether it needs to call `web_download` first.
"""
from pathlib import Path
import json
from typing import Dict, Any
import pydantic as py

from ..config import DOWNLOADS_DIR

class ListArgs(py.BaseModel):
    dummy: bool = py.Field(False, description="No arguments needed.")

class ListDownloadsTool:
    NAME = "list_downloads"
    DESC = "Return the list of files currently in the downloads/ folder."

    def function_spec(self):
        schema = ListArgs.model_json_schema()
        schema["additionalProperties"] = False
        return {
            "name": self.NAME,
            "description": self.DESC,
            "parameters": schema,
        }

    def __call__(self, *_a, **_kw) -> str:
        files = [p.name for p in DOWNLOADS_DIR.iterdir() if p.is_file()]
        return json.dumps(files)
