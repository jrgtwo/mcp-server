from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP
from pypdf import PdfReader

from model import _log


async def _read_pdf(file_path: str, max_chars: int = 8000) -> str:
    """Core PDF extraction logic, callable by both the MCP tool and the agent."""
    path = Path(file_path)
    if not path.exists():
        return f"File not found: '{file_path}'"
    if path.suffix.lower() != ".pdf":
        return f"File does not appear to be a PDF: '{file_path}'"

    _log(f"[read_pdf] Reading '{file_path}' (max_chars={max_chars})...")
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        return f"Could not open PDF '{file_path}': {exc}"

    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text:
            pages.append(f"[Page {i + 1}]\n{text}")

    if not pages:
        return "The PDF was opened but no readable text could be extracted (may be scanned/image-only)."

    full_text = "\n\n".join(pages)
    _log(f"[read_pdf] Extracted {len(full_text)} chars from {len(pages)} page(s).")

    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + f"\n... [truncated at {max_chars} chars]"

    return full_text


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def read_pdf(file_path: str, max_chars: int = 8000) -> str:
        """
        Extract and return the text content of a PDF file.

        Args:
            file_path: Absolute or relative path to the PDF file.
            max_chars: Maximum characters to return (default 8000).

        Returns:
            Extracted text, organised by page, truncated to max_chars if needed.
        """
        return await _read_pdf(file_path, max_chars)
