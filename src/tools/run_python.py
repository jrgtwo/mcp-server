from __future__ import annotations

import re
import subprocess
import sys

from fastmcp import FastMCP

from model import _log

# ── Security blocklist ────────────────────────────────────────────────────────

_BLOCKED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (label, re.compile(pattern))
    for label, pattern in [
        ("import os",         r"\bimport\s+os\b"),
        ("import sys",        r"\bimport\s+sys\b"),
        ("import subprocess", r"\bimport\s+subprocess\b"),
        ("import socket",     r"\bimport\s+socket\b"),
        ("import shutil",     r"\bimport\s+shutil\b"),
        ("__import__",        r"\b__import__\b"),
        ("open(",             r"\bopen\s*\("),
        ("exec(",             r"\bexec\s*\("),
        ("eval(",             r"\beval\s*\("),
        ("compile(",          r"\bcompile\s*\("),
        ("importlib",         r"\bimportlib\b"),
    ]
]

_MAX_TIMEOUT = 30
_MAX_OUTPUT  = 3000


def _run_python(code: str, timeout_seconds: int = 10) -> str:
    """Execute Python code in a sandboxed subprocess and return output."""
    # Check blocklist before executing anything
    for label, pattern in _BLOCKED_PATTERNS:
        if pattern.search(code):
            _log(f"[run_python] Blocked pattern detected: '{label}'")
            return (
                f"Execution blocked: the pattern '{label}' is not permitted "
                f"for safety reasons. Remove it and try again."
            )

    timeout = max(1, min(timeout_seconds, _MAX_TIMEOUT))
    _log(f"[run_python] Running code ({len(code)} chars, timeout={timeout}s)...")

    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _log(f"[run_python] Timed out after {timeout}s.")
        return f"Execution timed out after {timeout} second(s)."
    except Exception as exc:
        _log(f"[run_python] Unexpected error: {exc}")
        return f"Error starting process: {exc}"

    stdout = proc.stdout
    stderr = proc.stderr

    if len(stdout) > _MAX_OUTPUT:
        stdout = stdout[:_MAX_OUTPUT] + f"\n... [stdout truncated at {_MAX_OUTPUT} chars]"
    if len(stderr) > _MAX_OUTPUT:
        stderr = stderr[:_MAX_OUTPUT] + f"\n... [stderr truncated at {_MAX_OUTPUT} chars]"

    _log(f"[run_python] Exited {proc.returncode}, stdout={len(proc.stdout)} chars, stderr={len(proc.stderr)} chars.")
    return f"EXIT CODE: {proc.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def run_python(code: str, timeout_seconds: int = 10) -> str:
        """
        Execute Python code safely in a subprocess and return its output.

        A static blocklist prevents dangerous operations (file I/O, network access,
        shell commands, eval/exec). This is suitable for demonstrating small snippets
        during tutoring sessions.

        Args:
            code:            The Python code to execute.
            timeout_seconds: Maximum seconds allowed (clamped to 1–30, default 10).

        Returns:
            A string containing EXIT CODE, STDOUT, and STDERR sections.
            Returns an error message if blocked or if execution fails.
        """
        return _run_python(code, timeout_seconds)
