"""
Tool registry – when you add a new executor, import it here so `all_tools()`
returns it automatically.
"""
from typing import List
from .list_downloads_tool import ListDownloadsTool
from .web_tool import SafeWebDownloadTool
from .wait_tool import WaitTool
from .custom_api_tool import CustomAPITool


def all_tools() -> List:
    return [
        ListDownloadsTool(),
        SafeWebDownloadTool(),
        WaitTool(),
        CustomAPITool(),
        ]
