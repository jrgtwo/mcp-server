from __future__ import annotations

from typing import Literal

import httpx
from fastmcp import FastMCP

from model import _log

Category = Literal["Any", "Programming", "Misc", "Dark", "Pun", "Spooky", "Christmas"]
JokeType = Literal["any", "single", "twopart"]


async def _fetch_joke(category: Category, joke_type: JokeType, safe_mode: bool) -> dict:
    """Core joke fetch logic, callable by both the MCP tool and the agent."""
    _log(f"[joke] Fetching joke — category={category}, type={joke_type}, safe={safe_mode}")

    params: dict = {"amount": 1}
    if joke_type != "any":
        params["type"] = joke_type
    if safe_mode:
        params["safe-mode"] = ""  # presence of the key enables it

    url = f"https://v2.jokeapi.dev/joke/{category}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)

    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        msg = data.get("message", "Unknown error from JokeAPI.")
        _log(f"[joke] API error: {msg}")
        return {"success": False, "joke": None, "error": msg}

    joke_type_returned = data.get("type")
    if joke_type_returned == "single":
        joke_text = data["joke"]
    else:
        joke_text = f"{data['setup']}\n\n— {data['delivery']}"

    _log(f"[joke] Got a {joke_type_returned!r} joke from category '{data.get('category')}'.")
    return {
        "success": True,
        "category": data.get("category"),
        "type": joke_type_returned,
        "joke": joke_text,
        "error": None,
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_random_joke(
        category: Category = "Any",
        joke_type: JokeType = "any",
        safe_mode: bool = True,
    ) -> dict:
        """
        Fetch a random joke from the free JokeAPI (v2.jokeapi.dev). No API key required.

        Args:
            category:  Joke category to pull from. Options:
                         "Any"         — any category (default)
                         "Programming" — tech/dev humour
                         "Misc"        — miscellaneous
                         "Dark"        — dark humour (not available in safe mode)
                         "Pun"         — puns
                         "Spooky"      — Halloween-themed
                         "Christmas"   — festive jokes
            joke_type: Filter by joke format:
                         "any"      — no filter (default)
                         "single"   — one-liner
                         "twopart"  — setup + punchline
            safe_mode: If True (default), excludes explicit, racist, sexist, and
                       religious jokes.

        Returns:
            A dict with keys:
                - success:   True if a joke was returned.
                - category:  The category the joke belongs to.
                - type:      "single" or "twopart".
                - joke:      The joke text. Two-part jokes are formatted as
                             "setup\\n\\n— delivery".
                - error:     Error message if success is False (None otherwise).
        """
        return await _fetch_joke(category, joke_type, safe_mode)
