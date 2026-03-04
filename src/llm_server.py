"""
FastMCP server exposing a local HuggingFace LLM as MCP tools.

Usage:
    python src/llm_server.py --model models/Qwen2.5-7B-Instruct

Tools exposed:
    generate(prompt, ...)            - raw text completion
    chat(messages, ...)              - chat-style with role/content messages
    get_weather(location, units)     - current weather via Open-Meteo (no key needed)
    get_datetime(timezone)           - current date and time for any IANA timezone
    fetch_url(url, max_chars)        - fetch and extract text from any URL
    news_headlines(topic, ...)       - latest news via NewsAPI (requires NEWSAPI_KEY)

Resources:
    llm://info               - model metadata
"""

from __future__ import annotations

import argparse
import shutil
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastmcp import FastMCP

from model import _log, lifespan, state

load_dotenv()
import resources
import tools
import upload


@asynccontextmanager
async def _lifespan(server):
    async with lifespan(server):
        yield
    # Delete uploaded files on shutdown
    if upload.UPLOAD_DIR.exists():
        shutil.rmtree(upload.UPLOAD_DIR)
        _log("[upload] Upload directory removed on shutdown.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FastMCP local-LLM server")
    parser.add_argument("--model", required=True, help="Path to .gguf file or directory containing one")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "http"],
        help="Transport to use (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port for MCP HTTP transport")
    parser.add_argument(
        "--llama-server", required=True,
        help="Path to llama-server executable",
    )
    parser.add_argument(
        "--server-port", type=int, default=8080,
        help="Port for the llama-server backend (default: 8080)",
    )
    parser.add_argument(
        "--gpu-layers", type=int, default=-1,
        help="Number of model layers to offload to GPU; -1 = all (default: -1)",
    )
    parser.add_argument(
        "--context-size", type=int, default=16384,
        help="Context window size in tokens (default: 16384)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    state.model_path = args.model
    state.server_bin = args.llama_server
    state.server_port = args.server_port
    state.n_gpu_layers = args.gpu_layers
    state.n_ctx = args.context_size

    mcp = FastMCP("local-llm", lifespan=_lifespan)
    tools.register_all(mcp)
    resources.register(mcp)
    upload.register(mcp)

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
