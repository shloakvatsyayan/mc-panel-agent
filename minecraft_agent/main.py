"""
Core agent runner.

Exposes:
• run_agent(prompt)               -> CLI
• run_agent_once(prompt, trace)   -> returns (reply, steps[])
• run_agent_stream(prompt)        -> generator yielding ('step', md) OR ('final', reply)
"""
from __future__ import annotations

import argparse
import base64
import inspect
import json
from pathlib import Path
from typing import Any, Dict, Generator, List, Tuple
from minecraft_agent.utils.logging import get_logger
import openai
from tqdm import trange

from .config import (
    ALLOWED_SERVER_IDS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMP,
)
from .tools import all_tools
from .utils.logging import get_logger

log = get_logger("AgentRunner")
with open(Path(__file__).parent.parent / "pelicanapidocs" / "pelican_api.md", "r") as file:
    apidocs = file.read()

# --------------------------------------------------------------------------- #
# Tool registry helpers                                                       #
# --------------------------------------------------------------------------- #
def _build_index():
    specs, funcs = {}, {}
    for tool in all_tools():
        if hasattr(tool, "function_specs"):  # wrapper with many functions
            for spec in tool.function_specs():
                specs[spec["name"]] = spec
                funcs[spec["name"]] = tool
        elif hasattr(tool, "function_spec"):  # single‑function tool
            spec = tool.function_spec()
            specs[spec["name"]] = spec
            funcs[spec["name"]] = tool
    return specs, funcs


SPEC_INDEX, FUNC_INDEX = _build_index()


def call_tool(name: str, arguments: Dict[str, Any]) -> str:
    """
    Dispatch to a tool whose __call__ signature can be:
       • (name, arguments)
       • (arguments)
    """
    tool = FUNC_INDEX[name]
    sig_len = len(inspect.signature(tool.__call__).parameters)
    return tool(name, arguments) if sig_len == 2 else tool(arguments)


# --------------------------------------------------------------------------- #
# OpenAI wrapper – temperature only when allowed                              #
# --------------------------------------------------------------------------- #
openai.api_key = OPENAI_API_KEY
MAX_STEPS = 20


def _chat(payload: Dict[str, Any]):
    if OPENAI_MODEL.lower() != "o3" and OPENAI_TEMP not in (None, "", 1):
        payload["temperature"] = OPENAI_TEMP
    return openai.chat.completions.create(**payload)


# --------------------------------------------------------------------------- #
# Prompts                                                                     #
# --------------------------------------------------------------------------- #
_SYSTEM_PROMPT = (
    "You are a helpful DevOps assistant that can manage ONLY the whitelisted "
    "Minecraft server(s). Always use the **restart** power signal (not stop→start). "
    "When adding a plugin you MUST: (1) call list_downloads; "
    "(2) upload if present; (3) otherwise download from an approved site."
    "When running a command, remove the / from the command."
    "If you need to run another command, use the custom api docs tool. These are the api docs: " + apidocs
)


def _user_prompt(txt: str) -> str:
    return f"{txt} Servers available: {', '.join(ALLOWED_SERVER_IDS)}"


# --------------------------------------------------------------------------- #
# Plugin upload override: write endpoint                                      #
# --------------------------------------------------------------------------- #
from .pelican_client import PelicanClient  # keep import local
PelicanClient  # silence flake8


def _patched_upload_file(self: "PelicanClient", server_id: str, local: Path, remote: str):
    """Use /files/write (binary) instead of the unsupported /files/upload."""
    self._assert_allowed(server_id)
    data = local.read_bytes()
    encoded = base64.b64encode(data).decode()
    payload = {"file": remote, "content": encoded, "encoding": "base64"}
    self._request(
        "POST",
        f"/api/client/servers/{server_id}/files/write",
        json=payload,
    )


# monkey‑patch once
from types import MethodType

PelicanClient.upload_file = MethodType(_patched_upload_file, PelicanClient)


# --------------------------------------------------------------------------- #
# Agent runners                                                               #
# --------------------------------------------------------------------------- #
def _completion(messages: List[Dict[str, Any]]):
    return _chat(
        {
            "model": OPENAI_MODEL,
            "messages": messages,  # type: ignore[arg-type]
            "tools": [{"type": "function", "function": s} for s in SPEC_INDEX.values()],
            "tool_choice": "auto",
        }
    )


def run_agent_once(prompt: str, *, trace: bool = False) -> Tuple[str, List[str]]:
    """
    Return (assistant_reply, steps[]) – steps are markdown.
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(prompt)},
    ]
    steps: List[str] = []

    for _ in range(MAX_STEPS):
        m = _completion(messages).choices[0].message

        if getattr(m, "tool_calls", None):
            tc = m.tool_calls[0]
            args = json.loads(tc.function.arguments or "{}")
            res = call_tool(tc.function.name, args)

            steps.append(
                f":wrench: **{tc.function.name}**\n\n"
                f"```json\n{json.dumps(args, indent=2)}\n```\n"
                f"➡️  `{res}`"
            )

            messages.extend(
                [
                    {"role": "assistant", "content": m.content or "", "tool_calls": [tc]},
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": res,
                    },
                ]
            )
            continue

        return (m.content or "", steps)

    return ("Reached tool‑loop limit.", steps)


def run_agent_stream(prompt: str) -> Generator[Tuple[str, str], None, None]:
    """
    Yield live events:
        ('step', markdown) for each tool call
        ('final', assistant_reply) once finished
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(prompt)},
    ]

    for _ in range(MAX_STEPS):
        m = _completion(messages).choices[0].message

        if getattr(m, "tool_calls", None):
            tc = m.tool_calls[0]
            args = json.loads(tc.function.arguments or "{}")
            res = call_tool(tc.function.name, args)

            md = (
                f":wrench: **{tc.function.name}**  \n"
                f"```json\n{json.dumps(args, indent=2)}\n```  \n"
                f"➡️ `{res}`"
            )
            yield ("step", md)

            messages.extend(
                [
                    {"role": "assistant", "content": m.content or "", "tool_calls": [tc]},
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": res,
                    },
                ]
            )
            continue

        yield ("final", m.content or "")
        return

    yield ("final", "Reached tool‑loop limit.")


def run_agent(prompt: str) -> None:
    reply, _ = run_agent_once(prompt, trace=False)
    print("\nAssistant:", reply)


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #
def cli():
    p = argparse.ArgumentParser()
    p.add_argument("prompt", nargs="+")
    run_agent(" ".join(p.parse_args().prompt))


if __name__ == "__main__":
    cli()
