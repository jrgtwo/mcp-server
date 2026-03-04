from __future__ import annotations

import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastmcp import FastMCP


def _log(msg: str) -> None:
    print(f"[llm-server] {msg}", file=sys.stderr, flush=True)


class ModelState:
    process: subprocess.Popen | None = None
    client: httpx.Client | None = None
    model_path: str = ""
    n_gpu_layers: int = -1
    n_ctx: int = 16384
    server_bin: str = ""
    server_port: int = 8080


state = ModelState()


def _find_gguf(path: str) -> str:
    """Return path as-is if it's a .gguf file, or pick the best one in the directory.

    Excludes mmproj-*.gguf (multimodal projector files, not language models).
    Prefers Q4_K_M; falls back to the first file alphabetically.
    """
    p = Path(path)
    if p.is_file():
        return str(p)
    candidates = sorted(f for f in p.glob("*.gguf") if not f.name.startswith("mmproj"))
    if not candidates:
        raise FileNotFoundError(f"No model .gguf file found in {path!r}")
    preferred = next((f for f in candidates if "Q4_K_M" in f.name), None)
    chosen = preferred or candidates[0]
    if len(candidates) > 1:
        _log(f"Multiple .gguf files found; using {chosen.name}")
    return str(chosen)


@asynccontextmanager
async def lifespan(server: FastMCP):
    model_file = _find_gguf(state.model_path)
    base_url = f"http://127.0.0.1:{state.server_port}"

    cmd = [
        state.server_bin,
        "--model", model_file,
        "--n-gpu-layers", str(state.n_gpu_layers),
        "--ctx-size", str(state.n_ctx),
        "--port", str(state.server_port),
        "--host", "127.0.0.1",
        "--no-mmap",
    ]
    _log(f"Starting llama-server: {' '.join(cmd)}")
    # Inherit parent's stdout/stderr so llama-server logs flow to the terminal
    # and the pipe buffer never fills up and stalls the process.
    state.process = subprocess.Popen(cmd)

    # Wait for the server to become ready (up to 120 s for large models)
    state.client = httpx.Client(base_url=base_url, timeout=300.0)
    for attempt in range(120):
        time.sleep(1)
        if state.process.poll() is not None:
            raise RuntimeError(f"llama-server exited unexpectedly (code {state.process.returncode}).")
        try:
            r = state.client.get("/health")
            if r.status_code == 200:
                _log(f"llama-server ready on port {state.server_port} (took {attempt + 1}s).")
                break
        except httpx.ConnectError:
            pass
    else:
        state.process.terminate()
        raise RuntimeError("llama-server did not become ready within 120 s.")

    yield  # MCP server runs here

    _log("Shutting down llama-server.")
    state.process.terminate()
    try:
        state.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        state.process.kill()
    state.client.close()
    state.process = None
    state.client = None


def generate_tokens(
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    top_k: int = 0,
    repetition_penalty: float = 1.0,
    stop_sequences: list[str] | None = None,
    seed: int | None = None,
) -> str:
    """Raw text completion via llama-server /v1/completions."""
    client = state.client
    if client is None:
        raise RuntimeError("Model is not loaded.")

    payload: dict = {
        "prompt": prompt,
        "max_tokens": max_new_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k if top_k > 0 else 40,
        "repeat_penalty": repetition_penalty,
        "stop": stop_sequences or [],
    }
    if seed is not None:
        payload["seed"] = seed

    t0 = time.perf_counter()
    r = client.post("/v1/completions", json=payload)
    r.raise_for_status()
    data = r.json()
    t_done = time.perf_counter()

    text: str = data["choices"][0]["text"]
    gen_tokens = data.get("usage", {}).get("completion_tokens", 0)
    _log(
        f"[generate] {gen_tokens} tokens in {t_done - t0:.2f}s "
        f"({gen_tokens / max(t_done - t0, 0.001):.1f} tok/s)"
    )
    return text


def generate_chat(
    messages: list[dict[str, str]],
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    top_k: int = 0,
    repetition_penalty: float = 1.0,
    stop_sequences: list[str] | None = None,
    seed: int | None = None,
) -> str:
    """Chat completion via llama-server /v1/chat/completions."""
    client = state.client
    if client is None:
        raise RuntimeError("Model is not loaded.")

    payload: dict = {
        "messages": messages,
        "max_tokens": max_new_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k if top_k > 0 else 40,
        "repeat_penalty": repetition_penalty,
        "stop": stop_sequences or [],
    }
    if seed is not None:
        payload["seed"] = seed

    t0 = time.perf_counter()
    r = client.post("/v1/chat/completions", json=payload)
    r.raise_for_status()
    data = r.json()
    t_done = time.perf_counter()

    text: str = data["choices"][0]["message"]["content"] or ""
    gen_tokens = data.get("usage", {}).get("completion_tokens", 0)
    _log(
        f"[chat] {gen_tokens} tokens in {t_done - t0:.2f}s "
        f"({gen_tokens / max(t_done - t0, 0.001):.1f} tok/s)"
    )
    return text
