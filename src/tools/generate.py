from __future__ import annotations

from fastmcp import FastMCP

from model import generate_tokens


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def generate(
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 0,
        repetition_penalty: float = 1.0,
        stop_sequences: list[str] | None = None,
        seed: int | None = None,
    ) -> str:
        """
        Generate text from a raw prompt using the local LLM.

        Args:
            prompt:             The input text to continue.
            max_new_tokens:     Maximum tokens to generate (default 512).
            temperature:        Sampling temperature; 0 = greedy (default 0.7).
            top_p:              Nucleus-sampling probability (default 0.9).
            top_k:              Top-k vocabulary filtering; 0 = disabled (default 0).
            repetition_penalty: Penalty for repeating tokens; 1.0 = no penalty (default 1.0).
            stop_sequences:     List of strings that halt generation when produced.
            seed:               RNG seed for reproducible outputs.

        Returns:
            The generated text (input prompt NOT included).
        """
        return generate_tokens(
            prompt, max_new_tokens, temperature, top_p,
            top_k, repetition_penalty, stop_sequences, seed,
        )
