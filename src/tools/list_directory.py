from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from model import _log


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.0f} TB"


async def _list_directory(
    path: str,
    pattern: str = "*",
    recursive: bool = False,
    include_hidden: bool = False,
    max_results: int = 200,
) -> str:
    """Core directory listing logic, callable by both the MCP tool and the agent."""
    target = Path(path)

    if not target.exists():
        return f"Path not found: '{path}'"
    if not target.is_dir():
        return f"Path is not a directory: '{path}'"

    _log(f"[list_directory] Listing '{path}' (pattern={pattern!r}, recursive={recursive})")

    try:
        if recursive:
            entries = list(target.rglob(pattern))
        else:
            entries = list(target.glob(pattern))
    except Exception as exc:
        return f"Error listing '{path}': {exc}"

    if not include_hidden:
        entries = [e for e in entries if not any(part.startswith(".") for part in e.relative_to(target).parts)]

    entries.sort(key=lambda e: (e.is_file(), str(e).lower()))

    if not entries:
        return f"No entries found in '{path}' matching pattern '{pattern}'."

    truncated = len(entries) > max_results
    entries = entries[:max_results]

    lines: list[str] = [f"Directory: {target.resolve()}", ""]

    for entry in entries:
        try:
            rel = entry.relative_to(target)
            if entry.is_dir():
                lines.append(f"  [DIR]  {rel}/")
            else:
                size = _format_size(entry.stat().st_size)
                lines.append(f"  [FILE] {rel}  ({size})")
        except Exception:
            continue

    lines.append("")
    summary = f"{len(entries)} item(s) shown"
    if truncated:
        summary += f" (results capped at {max_results})"
    lines.append(summary)

    return "\n".join(lines)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_directory(
        path: str,
        pattern: str = "*",
        recursive: bool = False,
        include_hidden: bool = False,
        max_results: int = 200,
    ) -> str:
        """
        List files and directories at a given path.

        Args:
            path: Absolute or relative path to the directory to list.
            pattern: Glob pattern to filter results (default "*" matches everything).
                     Examples: "*.py", "*.txt", "data_*".
            recursive: If True, list all files in subdirectories as well (default False).
            include_hidden: If True, include hidden files/folders starting with "." (default False).
            max_results: Maximum number of entries to return (default 200).

        Returns:
            A formatted list of files and directories with sizes.
        """
        return await _list_directory(path, pattern, recursive, include_hidden, max_results)
