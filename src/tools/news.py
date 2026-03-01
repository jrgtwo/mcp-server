from __future__ import annotations

import os

import httpx
from fastmcp import FastMCP

from model import _log

_BASE = "https://newsapi.org/v2"


async def _news_headlines(topic: str = "", country: str = "us", max_results: int = 5) -> str:
    """Core news fetch logic, callable by both the MCP tool and the agent."""
    api_key = os.environ.get("NEWSAPI_KEY", "")
    if not api_key:
        return (
            "NEWSAPI_KEY environment variable is not set. "
            "Get a free key at https://newsapi.org and set it with: "
            "export NEWSAPI_KEY=your_key_here"
        )

    max_results = min(max(1, max_results), 10)
    _log(f"[news] topic='{topic}', country='{country}', max_results={max_results}")

    async with httpx.AsyncClient(timeout=10) as client:
        if topic:
            resp = await client.get(
                f"{_BASE}/everything",
                params={
                    "q": topic,
                    "sortBy": "publishedAt",
                    "pageSize": max_results,
                    "language": "en",
                    "apiKey": api_key,
                },
            )
        else:
            resp = await client.get(
                f"{_BASE}/top-headlines",
                params={
                    "country": country,
                    "pageSize": max_results,
                    "apiKey": api_key,
                },
            )

    resp.raise_for_status()
    data = resp.json()
    articles = data.get("articles", [])

    if not articles:
        return "No headlines found."

    lines: list[str] = []
    for i, article in enumerate(articles, 1):
        source    = article.get("source", {}).get("name", "Unknown")
        title     = article.get("title") or "No title"
        url       = article.get("url", "")
        published = (article.get("publishedAt") or "")[:10]
        lines.append(f"{i}. [{source}] {title}\n   Published: {published}\n   {url}")

    result = "\n\n".join(lines)
    _log(f"[news] Returning {len(articles)} article(s).")
    return result


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def news_headlines(topic: str = "", country: str = "us", max_results: int = 5) -> str:
        """
        Fetch the latest news headlines, optionally filtered by topic.

        Requires the NEWSAPI_KEY environment variable (free key at https://newsapi.org).

        Args:
            topic:       Keyword(s) to search for (e.g. "AI", "climate change").
                         Leave blank to get general top headlines.
            country:     2-letter country code used when topic is blank (default "us").
                         Options: us, gb, au, ca, de, fr, jp, in, etc.
            max_results: Number of headlines to return (1–10, default 5).

        Returns:
            Numbered list of headlines with source, publication date, and URL.
        """
        return await _news_headlines(topic, country, max_results)
