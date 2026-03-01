from __future__ import annotations

from fastmcp import FastMCP

from . import agent, chat, date_time, fetch_url, generate, news, weather


def register_all(mcp: FastMCP) -> None:
    generate.register(mcp)
    chat.register(mcp)
    weather.register(mcp)
    date_time.register(mcp)
    fetch_url.register(mcp)
    news.register(mcp)
    agent.register(mcp)
