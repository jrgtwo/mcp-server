from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any

import torch
from fastmcp import FastMCP
from transformers import AutoModelForCausalLM, AutoTokenizer


def _log(msg: str) -> None:
    print(f"[llm-server] {msg}", file=sys.stderr, flush=True)


class ModelState:
    model: AutoModelForCausalLM | None = None
    tokenizer: AutoTokenizer | None = None
    model_path: str = ""
    device: str = "cpu"


state = ModelState()


@asynccontextmanager
async def lifespan(server: FastMCP):
    _log(f"Loading model from '{state.model_path}' ...")
    _log(f"CUDA available: {torch.cuda.is_available()}")
    _log(f"PyTorch CUDA build version: {torch.version.cuda}")
    if torch.cuda.is_available():
        _log(f"GPU: {torch.cuda.get_device_name(0)}")
    state.device = "cuda" if torch.cuda.is_available() else "cpu"

    state.tokenizer = AutoTokenizer.from_pretrained(state.model_path)
    state.model = AutoModelForCausalLM.from_pretrained(
        state.model_path,
        dtype=torch.float16 if state.device == "cuda" else torch.float32,
        device_map=state.device,
    )
    state.model.eval()
    _log(f"Model ready on {state.device}.")

    yield  # server runs here

    _log("Shutting down, releasing model.")
    del state.model
    del state.tokenizer
    state.model = None
    state.tokenizer = None


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
    """Tokenise, run model.generate, decode only the new tokens."""
    model = state.model
    tokenizer = state.tokenizer
    if model is None or tokenizer is None:
        raise RuntimeError("Model is not loaded.")

    if seed is not None:
        torch.manual_seed(seed)
        if state.device == "cuda":
            torch.cuda.manual_seed(seed)

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]

    do_sample = temperature > 0.0
    gen_kwargs: dict[str, Any] = dict(
        max_new_tokens=max_new_tokens,
        do_sample=do_sample,
        pad_token_id=tokenizer.eos_token_id,
    )
    if do_sample:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["top_p"] = top_p
        if top_k > 0:
            gen_kwargs["top_k"] = top_k
    if repetition_penalty != 1.0:
        gen_kwargs["repetition_penalty"] = repetition_penalty
    if stop_sequences:
        gen_kwargs["stop_strings"] = stop_sequences
        gen_kwargs["tokenizer"] = tokenizer

    with torch.no_grad():
        output_ids = model.generate(**inputs, **gen_kwargs)

    new_ids = output_ids[0][input_len:]
    return tokenizer.decode(new_ids, skip_special_tokens=True)


def build_chat_prompt(messages: list[dict[str, str]]) -> str:
    """Apply the tokenizer's chat template, or fall back to a plain format."""
    tokenizer = state.tokenizer
    if tokenizer is None:
        raise RuntimeError("Model is not loaded.")

    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    # Fallback: simple "role: content" lines
    lines = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages]
    lines.append("assistant:")
    return "\n".join(lines)
