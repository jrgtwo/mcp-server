from __future__ import annotations

from fastmcp import FastMCP

from . import agent, chat, generate, weather


def register_all(mcp: FastMCP) -> None:
    generate.register(mcp)
    chat.register(mcp)
    weather.register(mcp)
    agent.register(mcp)
