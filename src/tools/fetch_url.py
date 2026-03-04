from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
from fastmcp import FastMCP

from model import _log

_SKIP_TAGS = ["script", "style", "head", "meta", "link", "noscript"]


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_SKIP_TAGS):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


async def _fetch_url(url: str, max_chars: int = 4000) -> str:
    """Core URL fetch logic, callable by both the MCP tool and the agent."""
    _log(f"[fetch_url] Fetching '{url}' (max_chars={max_chars})...")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        _log(f"[fetch_url] Connection error: {exc}")
        return f"Could not connect to '{url}': {exc}"
    except httpx.HTTPStatusError as exc:
        _log(f"[fetch_url] HTTP error: {exc}")
        return f"HTTP {exc.response.status_code} error fetching '{url}'."
    except httpx.TimeoutException:
        _log(f"[fetch_url] Request timed out.")
        return f"Request to '{url}' timed out."

    content_type = resp.headers.get("content-type", "")
    raw_len = len(resp.text)
    _log(f"[fetch_url] HTTP {resp.status_code}, content-type='{content_type}', raw={raw_len} chars.")

    if "html" in content_type:
        text = _extract_text(resp.text)
        _log(f"[fetch_url] HTML stripped — {raw_len} raw chars → {len(text)} text chars.")
    else:
        text = resp.text

    if not text:
        return "The page was fetched successfully but no readable text could be extracted."

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
