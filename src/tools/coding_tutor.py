from __future__ import annotations

import asyncio
import time

from fastmcp import FastMCP

from model import _log, generate_tokens
from tools.agent import (
    _build_prompt,
    _maybe_trim,
    _parse_action,
    _truncate_to_first_action,
)
from tools.explain_code import _explain_code
from tools.fetch_url import _fetch_url
from tools.review_code import _review_code
from tools.run_python import _run_python

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert coding tutor. Your goal is not just to solve problems, \
but to help the learner understand why the solution works.

TOOLS AVAILABLE:
- explain_code(code: str, language: str = "python", level: str = "beginner") -> str
    Explain what a piece of code does, tailored to the learner's level.
    level options: "beginner", "intermediate", "advanced"
- review_code(code: str, language: str = "python", focus: str = "general") -> str
    Review code for issues. focus options: "general", "security", "performance", "style"
- run_python(code: str, timeout_seconds: int = 10) -> str
    Execute a short Python snippet safely and return its output. Use this to \
demonstrate concepts with live examples. Dangerous imports and I/O are blocked.
- fetch_url(url: str, max_chars: int = 4000) -> str
    Fetch the text content of a URL. Use when the learner references specific docs \
or a GitHub link.

To call a tool, output EXACTLY this format (nothing else on those lines):
TOOL: <tool_name>
ARGS: <json object>

Example:
TOOL: run_python
ARGS: {"code": "print(2 + 2)"}

When you have enough information to give the learner a complete answer, output:
FINAL: <your teaching response>

PEDAGOGICAL GUIDELINES:
- Always explain the *why* before showing a fix — understanding beats copying.
- Use run_python to demonstrate concepts with live, runnable examples whenever helpful.
- Adapt your language to the learner's apparent skill level inferred from their question.
- Celebrate correct thinking before correcting mistakes ("Good intuition! The issue is…").
- Never hand over corrected code without explaining what was wrong and why.
- If a tool returns an error, treat it as a teachable moment ("Let's see what that error means…").
- Be encouraging, patient, and thorough.

Rules:
- Only call one tool per response.
- Always output either a TOOL block OR a FINAL block — never both.
- After receiving a tool result it will be shown as RESULT: ... — use it to continue.
- If a tool returns empty or no useful content, acknowledge it and answer from your own knowledge.
"""

# ── Tool dispatcher ───────────────────────────────────────────────────────────


async def _execute_tutor_tool(name: str, args: dict) -> str:
    """Dispatch a tool call for the tutor agent and return its string result."""
    _log(f"[tutor] >> tool call: {name}({args})")

    if name == "explain_code":
        result = await asyncio.to_thread(
            _explain_code,
            args.get("code", ""),
            args.get("language", "python"),
            args.get("level", "beginner"),
        )
    elif name == "review_code":
        result = await asyncio.to_thread(
            _review_code,
            args.get("code", ""),
            args.get("language", "python"),
            args.get("focus", "general"),
        )
    elif name == "run_python":
        result = await asyncio.to_thread(
            _run_python,
            args.get("code", ""),
            args.get("timeout_seconds", 10),
        )
    elif name == "fetch_url":
        result = await _fetch_url(args.get("url", ""), args.get("max_chars", 4000))
    else:
        result = f"Unknown tool '{name}'."

    _log(f"[tutor] << tool result ({len(result)} chars): {result[:200]}{'...' if len(result) > 200 else ''}")
    return result


# ── Registration ──────────────────────────────────────────────────────────────


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def coding_tutor(
        question: str,
        max_steps: int = 8,
        max_new_tokens: int = 1024,
        max_history_pairs: int = 4,
        summary_strategy: str = "deterministic",
    ) -> str:
        """
        Ask the coding tutor a programming question.

        The tutor reasons step by step, calling tools like explain_code, review_code,
        and run_python to give thorough, pedagogically sound answers. It explains the
        *why* before the *what*, uses live examples, and adapts to your skill level.

        Args:
            question:           Your coding question, code snippet, or error message.
            max_steps:          Maximum tool-call iterations before stopping (default 8).
            max_new_tokens:     Token ceiling for each LLM call (default 1024).
            max_history_pairs:  Number of recent assistant+tool rounds to keep in
                                full before older ones are summarised (default 4).
            summary_strategy:   How to summarise trimmed history — "deterministic"
                                (default) or "llm".

        Returns:
            The tutor's teaching response.
        """
        _log(f'[tutor] Starting — question: "{question[:120]}{"..." if len(question) > 120 else ""}"')

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": question},
        ]

        for step in range(max_steps):
            messages = await _maybe_trim(messages, max_history_pairs, summary_strategy)
            prompt = _build_prompt(messages)
            _log(
                f"[tutor] Step {step + 1}/{max_steps} — calling LLM "
                f"(prompt ~{len(prompt)} chars, {len(messages)} messages)..."
            )
            t_step = time.perf_counter()
            response = await asyncio.to_thread(
                generate_tokens,
                prompt,
                max_new_tokens,
                0.4,
                0.9,
                stop_sequences=["RESULT:", "(waiting"],
            )
            _log(
                f"[tutor] Step {step + 1} LLM done in {time.perf_counter() - t_step:.2f}s — "
                f"response: {response[:300]}{'...' if len(response) > 300 else ''}"
            )

            response = _truncate_to_first_action(response)
            action, payload = _parse_action(response)

            if action == "FINAL":
                _log(f"[tutor] FINAL answer reached after {step + 1} step(s).")
                return payload  # type: ignore[return-value]

            if action is not None:
                _log(f"[tutor] Parsed action: {action}")
                tool_result = await _execute_tutor_tool(action, payload)  # type: ignore[arg-type]
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "tool",      "content": tool_result})
            else:
                _log("[tutor] LLM did not follow format — returning raw output.")
                return response

        _log(f"[tutor] Max steps ({max_steps}) reached without a FINAL answer.")
        return f"Tutor stopped after {max_steps} steps without a FINAL answer."
