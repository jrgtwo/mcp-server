from __future__ import annotations

from fastmcp import FastMCP

from . import agent, chat, coding_tutor, date_time, explain_code, fetch_url, generate, news, read_pdf, review_code, run_python, weather


def register_all(mcp: FastMCP) -> None:
    generate.register(mcp)
    chat.register(mcp)
    weather.register(mcp)
    date_time.register(mcp)
    fetch_url.register(mcp)
    news.register(mcp)
    read_pdf.register(mcp)
    agent.register(mcp)
    # Coding tutor tools
    explain_code.register(mcp)
    review_code.register(mcp)
    run_python.register(mcp)
    coding_tutor.register(mcp)
