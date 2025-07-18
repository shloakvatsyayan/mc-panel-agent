"""
High‑level server interaction tool (“function” in OpenAI terminology).
"""
import json
from pathlib import Path
from typing import Dict, Any
import pydantic as py

from ..pelican_client import PelicanClient, PelicanError
from ..config import DOWNLOADS_DIR
from ..utils.logging import get_logger

log = get_logger("ServerTool")
client = PelicanClient()

# ------------------ Pydantic schemas -------------------------------------- #
class PowerArgs(py.BaseModel):
    server_id: str = py.Field(
        description="The UUID of the Minecraft server (must match whitelist).")
    signal: str = py.Field(
        description="One of start, stop, restart, kill, hibernate.")

class StatusArgs(py.BaseModel):
    server_id: str

class CommandArgs(py.BaseModel):
    server_id: str
    command: str

class UploadArgs(py.BaseModel):
    server_id: str
    plugin_name: str = py.Field(
        description="Filename of the plugin JAR already present in downloads/.")

# ------------------ Tool --------------------------------------------------- #
class ServerTool:
    """ Wraps 4 sub‑functions: power, status, command, upload_plugin """

    _FUNCTIONS = {
        "power_control": (PowerArgs, "Change server power state."),
        "get_server_status": (StatusArgs, "Return state, RAM and CPU usage."),
        "send_console_command": (CommandArgs, "Send a command to the server console."),
        "upload_plugin": (UploadArgs, "Upload a plugin JAR from downloads/ into /plugins and restart."),
    }

    # ------------ OpenAI function spec ------------------------------------- #
    def function_specs(self):
        specs = []
        for name, (schema, desc) in self._FUNCTIONS.items():
            s = schema.model_json_schema()
            s["additionalProperties"] = False
            specs.append({
                "name": name,
                "description": desc,
                "parameters": s,
            })
        return specs

    # ------------ executor ------------------------------------------------- #
    def __call__(self, name: str, arguments: Dict[str, Any]) -> str:
        try:
            if name == "power_control":
                args = PowerArgs(**arguments)
                client.power(args.server_id, args.signal)
                return f"OK – power {args.signal} sent."

            if name == "get_server_status":
                args = StatusArgs(**arguments)
                res = client.get_resources(args.server_id)
                return json.dumps(res)

            if name == "send_console_command":
                args = CommandArgs(**arguments)
                client.send_command(args.server_id, args.command)
                return f"OK – command '{args.command}' dispatched."

            if name == "upload_plugin":
                args = UploadArgs(**arguments)
                local_path = DOWNLOADS_DIR / args.plugin_name
                if not local_path.exists():
                    return f"Error – {local_path} not found in downloads/"
                client.upload_file(args.server_id, local_path, f"/plugins/{args.plugin_name}")
                client.power(args.server_id, "restart")
                return "Plugin uploaded and restart signal sent."

        except PelicanError as e:
            return f"Pelican error: {e}"
        except Exception as ex:
            log.exception("Unhandled in ServerTool")
            return f"Unhandled error: {ex}"

        return "Unknown function call."
