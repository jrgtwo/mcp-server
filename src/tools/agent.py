from __future__ import annotations

import asyncio
import json
import re

from fastmcp import FastMCP

from model import _log, generate_tokens
from tools.date_time import _get_datetime
from tools.fetch_url import _fetch_url
from tools.news import _news_headlines
from tools.weather import _fetch_weather

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an autonomous agent. Accomplish the user's goal by reasoning step by step \
and calling tools when needed.

TOOLS AVAILABLE:
- get_weather(location: str, units: str = "metric") -> str
    Fetch current weather for a city. units: "metric" or "imperial".
- get_datetime(timezone: str = "UTC") -> str
    Return the current date and time. timezone: IANA name e.g. "America/New_York".
- fetch_url(url: str, max_chars: int = 4000) -> str
    Fetch and return the text content of any URL.
- news_headlines(topic: str = "", country: str = "us", max_results: int = 5) -> str
    Fetch latest news headlines. topic: keyword filter; leave blank for top headlines.

To call a tool, output EXACTLY this format (nothing else on those lines):
TOOL: <tool_name>
ARGS: <json object>

Example:
TOOL: get_weather
ARGS: {"location": "Tokyo", "units": "metric"}

When you have enough information to answer the user, output:
FINAL: <your answer>

Rules:
- Only call one tool per response.
- Always output either a TOOL block OR a FINAL block — never both.
- After receiving a tool result it will be shown as RESULT: ... — use it to continue.
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

_TOOL_RE  = re.compile(r"TOOL:\s*(\w+)\s*\nARGS:\s*(\{.*?\})", re.DOTALL)
_FINAL_RE = re.compile(r"FINAL:\s*(.*)", re.DOTALL)


def _parse_action(text: str) -> tuple[str, dict] | tuple[str, str] | tuple[None, None]:
    """Return ('tool', {args}) | ('FINAL', answer_str) | (None, None)."""
    m = _TOOL_RE.search(text)
    if m:
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            args = {}
        return m.group(1), args

    m = _FINAL_RE.search(text)
    if m:
        return "FINAL", m.group(1).strip()

    return None, None


async def _execute_tool(name: str, args: dict) -> str:
    """Dispatch a tool call and return its string result."""
    _log(f"[agent] >> tool call: {name}({args})")

    if name == "get_weather":
        result = await _fetch_weather(args.get("location", ""), args.get("units", "metric"))
    elif name == "get_datetime":
        result = _get_datetime(args.get("timezone", "UTC"))
    elif name == "fetch_url":
        result = await _fetch_url(args.get("url", ""), args.get("max_chars", 4000))
    elif name == "news_headlines":
        result = await _news_headlines(
            args.get("topic", ""),
            args.get("country", "us"),
            args.get("max_results", 5),
        )
    else:
        result = f"Unknown tool '{name}'."

    _log(f"[agent] << tool result: {result}")
    return result


def _build_prompt(messages: list[dict[str, str]]) -> str:
    """Format the conversation as a plain-text prompt for the LLM."""
    lines: list[str] = []
    for msg in messages:
        role    = msg["role"]
        content = msg["content"]
        if role == "system":
            lines.append(f"[SYSTEM]\n{content}\n")
        elif role == "user":
            lines.append(f"[USER]\n{content}\n")
        elif role == "assistant":
            lines.append(f"[ASSISTANT]\n{content}\n")
        elif role == "tool":
            lines.append(f"RESULT: {content}\n")
    lines.append("[ASSISTANT]\n")
    return "\n".join(lines)


# ── Registration ──────────────────────────────────────────────────────────────

def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def run_agent(goal: str, max_steps: int = 10) -> str:
        """
        Run an autonomous ReAct agent to accomplish a multi-step goal.

        The agent reasons step by step and calls available tools (e.g.
        get_weather) as many times as needed before producing a final answer.

        Args:
            goal:      The task or question for the agent to solve.
            max_steps: Maximum tool-call iterations before stopping (default 10).

        Returns:
            The agent's final answer, or a partial trace if max_steps is reached.
        """
        _log(f'[agent] Starting — goal: "{goal}"')

        messages: list[dict[str, str]] = [
            {"role": "system",  "content": _SYSTEM_PROMPT},
            {"role": "user",    "content": goal},
        ]

        for step in range(max_steps):
            _log(f"[agent] Step {step + 1}/{max_steps} — calling LLM...")
            prompt   = _build_prompt(messages)
            # generate_tokens is synchronous/CPU-bound — run off the event loop
            response = await asyncio.to_thread(
                generate_tokens,
                prompt,
                512,   # max_new_tokens
                0.3,   # temperature (lower = more deterministic for tool use)
                0.9,   # top_p
            )
            _log(f"[agent] LLM response: {response[:300]}{'...' if len(response) > 300 else ''}")

            action, payload = _parse_action(response)

            if action == "FINAL":
                _log(f"[agent] FINAL answer reached after {step + 1} step(s).")
                return payload  # type: ignore[return-value]

            if action is not None:
                _log(f"[agent] Parsed action: {action}")
                # Execute the requested tool
                tool_result = await _execute_tool(action, payload)  # type: ignore[arg-type]
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "tool",      "content": tool_result})
            else:
                # LLM didn't follow the format — treat its output as the answer
                _log("[agent] LLM did not follow format — returning raw output.")
                return response

        _log(f"[agent] Max steps ({max_steps}) reached without a FINAL answer.")
        return f"Agent stopped after {max_steps} steps without a FINAL answer."
