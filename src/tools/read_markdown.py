from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from model import _log


async def _read_markdown(file_path: str, max_chars: int = 8000) -> str:
    """Core markdown extraction logic, callable by both the MCP tool and the agent."""
    path = Path(file_path)
    if not path.exists():
        return f"File not found: '{file_path}'"
    if path.suffix.lower() not in {".md", ".markdown"}:
        return f"File does not appear to be a Markdown file: '{file_path}'"

    _log(f"[read_markdown] Reading '{file_path}' (max_chars={max_chars})...")
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"Could not read '{file_path}': {exc}"

    if not text.strip():
        return "The file was opened but contains no readable text."

    _log(f"[read_markdown] Read {len(text)} chars.")

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"

    return text


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def read_markdown(file_path: str, max_chars: int = 8000) -> str:
        """
        Read and return the contents of a Markdown file.

        Args:
            file_path: Absolute or relative path to the .md or .markdown file.
            max_chars: Maximum characters to return (default 8000).

        Returns:
            The file's text content, truncated to max_chars if needed.
        """
        return await _read_markdown(file_path, max_chars)
