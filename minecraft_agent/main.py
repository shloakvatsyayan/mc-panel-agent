"""
Core agent runner.

Exports
▪ run_agent(prompt)               – CLI convenience
▪ run_agent_once(prompt, trace)   – (reply, steps[])
▪ run_agent_stream(prompt)        – generator yielding ('step' | 'final', text)
"""
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
from typing import Any, Dict, Generator, List, Tuple

import openai

from .config import ALLOWED_SERVER_IDS, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMP
from .tools import all_tools
from .utils.logging import get_logger

# --------------------------------------------------------------------------- #
# Constants & static data                                                     #
# --------------------------------------------------------------------------- #
log = get_logger("AgentRunner")
apidocs = (Path(__file__).parent.parent / "pelicanapidocs" / "pelican_api.md").read_text()

_SYSTEM_PROMPT = (
    "You are a helpful DevOps assistant that can manage ONLY the whitelisted Minecraft "
    "server(s). Instead of stopping and starting the server, you can use the restart power signal. "
    "When running a command, remove the / from the command. "
    "If you need to run another command, use the custom api docs tool. "
    f"These are the api docs: {apidocs}"
)
MAX_STEPS = 20

openai.api_key = OPENAI_API_KEY

# --------------------------------------------------------------------------- #
# Tool registry                                                               #
# --------------------------------------------------------------------------- #
def _build_registry() -> tuple[dict[str, dict], dict[str, Any]]:
    """Collect function specs and callables from every tool."""
    specs, funcs = {}, {}
    for tool in all_tools():
        getter = "function_specs" if hasattr(tool, "function_specs") else "function_spec"
        for spec in getattr(tool, getter)():
            specs[spec["name"]] = spec
            funcs[spec["name"]] = tool
    return specs, funcs


SPEC_INDEX, FUNC_INDEX = _build_registry()


def _call_tool(name: str, args: Dict[str, Any]) -> str:
    """Invoke a tool regardless of whether it expects (args) or (name, args)."""
    tool = FUNC_INDEX[name]
    return tool(name, args) if len(inspect.signature(tool.__call__).parameters) == 2 else tool(args)


# --------------------------------------------------------------------------- #
# OpenAI helper                                                               #
# --------------------------------------------------------------------------- #
def _chat(messages: List[Dict[str, Any]]):
    payload: Dict[str, Any] = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "tools": [{"type": "function", "function": s} for s in SPEC_INDEX.values()],
        "tool_choice": "auto",
    }
    if OPENAI_MODEL.lower() != "o3" and OPENAI_TEMP not in (None, "", 1):
        payload["temperature"] = OPENAI_TEMP
    return openai.chat.completions.create(**payload)


# --------------------------------------------------------------------------- #
# Core generator driving the loop                                             #
# --------------------------------------------------------------------------- #
def _agent(prompt: str) -> Generator[Tuple[str, str], None, None]:
    """
    Yields ('step', markdown) for each tool call, then ('final', reply) when done.
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"{prompt} Servers available: {', '.join(ALLOWED_SERVER_IDS)}"},
    ]

    for _ in range(MAX_STEPS):
        m = _chat(messages).choices[0].message

        # Tool call branch
        if getattr(m, "tool_calls", None):
            tc = m.tool_calls[0]
            args = json.loads(tc.function.arguments or "{}")
            result = _call_tool(tc.function.name, args)

            yield (
                "step",
                f":wrench: **{tc.function.name}**\n\n"
                f"```json\n{json.dumps(args, indent=2)}\n```\n"
                f"➡️  `{result}`",
            )

            messages += [
                {"role": "assistant", "content": m.content or "", "tool_calls": [tc]},
                {"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": result},
            ]
            continue

        # Normal assistant response
        yield ("final", m.content or "")
        return

    yield ("final", "Reached tool-loop limit.")


# --------------------------------------------------------------------------- #
# Public helpers                                                              #
# --------------------------------------------------------------------------- #
def run_agent_once(prompt: str, *, trace: bool = False) -> Tuple[str, List[str]]:
    """Return (assistant_reply, steps[]) – steps are markdown describing each tool call."""
    steps: List[str] = []
    for kind, text in _agent(prompt):
        if kind == "step":
            steps.append(text)
        else:  # 'final'
            return text, steps
    return "Reached tool-loop limit.", steps


def run_agent_stream(prompt: str) -> Generator[Tuple[str, str], None, None]:
    """Stream live events suitable for a UI."""
    return _agent(prompt)


def run_agent(prompt: str) -> None:
    """Print a single reply to stdout (CLI shortcut)."""
    print("\nAssistant:", run_agent_once(prompt)[0])


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #
def cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="+")
    run_agent(" ".join(parser.parse_args().prompt))


if __name__ == "__main__":
    cli()
