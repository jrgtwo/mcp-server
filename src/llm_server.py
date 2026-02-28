"""
FastMCP server exposing a local HuggingFace LLM as MCP tools.

Usage:
    python src/llm_server.py --model models/Qwen2.5-7B-Instruct

Tools exposed:
    generate(prompt, ...)            - raw text completion
    chat(messages, ...)              - chat-style with role/content messages
    get_weather(location, units)     - current weather via Open-Meteo (no key needed)

Resources:
    llm://info               - model metadata
"""

from __future__ import annotations

import argparse
import sys

from fastmcp import FastMCP

from model import _log, lifespan, state
import resources
import tools


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FastMCP local-LLM server")
    parser.add_argument("--model", required=True, help="Path to local model directory")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "http"],
        help="Transport to use (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    state.model_path = args.model

    mcp = FastMCP("local-llm", lifespan=lifespan)
    tools.register_all(mcp)
    resources.register(mcp)

    if args.transport == "http":
        from starlette.middleware import Middleware
        from starlette.middleware.cors import CORSMiddleware

        _log(f"Starting HTTP transport on port {args.port}.")
        mcp.run(
            "http",
            port=args.port,
            show_banner=False,
            middleware=[
                Middleware(
                    CORSMiddleware,
                    allow_origins=["*"],  # TODO: restrict to specific origins before exposing beyond localhost
                    allow_methods=["*"],
                    allow_headers=["*"],
                    expose_headers=["Mcp-Session-Id"],
                )
            ],
        )
    else:
        _log("Listening on stdio.")
        mcp.run("stdio", show_banner=False)
