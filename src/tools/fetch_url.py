from __future__ import annotations

from html.parser import HTMLParser

import httpx
from fastmcp import FastMCP

from model import _log


class _TextExtractor(HTMLParser):
    """Strip HTML tags and return only visible text."""

    _SKIP_TAGS = frozenset({"script", "style", "head", "meta", "link", "noscript"})

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self._parts)


async def _fetch_url(url: str, max_chars: int = 4000) -> str:
    """Core URL fetch logic, callable by both the MCP tool and the agent."""
    _log(f"[fetch_url] Fetching '{url}' (max_chars={max_chars})...")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; mcp-agent/1.0)"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type:
        parser = _TextExtractor()
        parser.feed(resp.text)
        text = parser.get_text()
    else:
        text = resp.text

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"

    _log(f"[fetch_url] Done — returned {len(text)} chars.")
    return text


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def fetch_url(url: str, max_chars: int = 4000) -> str:
        """
        Fetch the content of a URL and return its text.

        HTML pages are stripped of tags; only visible text is returned.
        For JSON or plain-text responses, the raw body is returned.

        Args:
            url:       The URL to fetch (must start with http:// or https://).
            max_chars: Maximum characters to return (default 4000).

        Returns:
            Extracted page text, truncated to max_chars if needed.
        """
        return await _fetch_url(url, max_chars)
