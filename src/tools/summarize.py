from __future__ import annotations

from fastmcp import FastMCP

from model import _log, generate_chat

# Characters per chunk when splitting long text
_CHUNK_SIZE = 3000
# Rough token budget for the final summary
_SUMMARY_TOKENS = 512


def _split_chunks(text: str, chunk_size: int) -> list[str]:
    """Split text into overlapping-free chunks on paragraph/newline boundaries."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Try to break at a paragraph boundary near the end of the window
        split = text.rfind("\n\n", start, end)
        if split == -1:
            split = text.rfind("\n", start, end)
        if split == -1 or split <= start:
            split = end
        chunks.append(text[start:split])
        start = split
    return [c.strip() for c in chunks if c.strip()]


def _summarize_chunk(chunk: str, focus: str) -> str:
    focus_instruction = f" Focus on: {focus}." if focus else ""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a concise summarizer. Summarize the provided text clearly "
                "and accurately, preserving the key information."
                + focus_instruction
            ),
        },
        {
            "role": "user",
            "content": f"Summarize the following text:\n\n{chunk}",
        },
    ]
    return generate_chat(messages, max_new_tokens=_SUMMARY_TOKENS, temperature=0.3, top_p=0.9)


def _merge_summaries(summaries: list[str], focus: str) -> str:
    combined = "\n\n".join(f"[Part {i+1}]\n{s}" for i, s in enumerate(summaries))
    focus_instruction = f" Focus on: {focus}." if focus else ""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a concise summarizer. You will be given several partial summaries "
                "of a long document. Combine them into one coherent, concise final summary."
                + focus_instruction
            ),
        },
        {
            "role": "user",
            "content": f"Combine these partial summaries into one:\n\n{combined}",
        },
    ]
    return generate_chat(messages, max_new_tokens=_SUMMARY_TOKENS, temperature=0.3, top_p=0.9)


async def _summarize_text(text: str, focus: str, max_length: int) -> str:
    """Core summarization logic, callable by both the MCP tool and the agent."""
    text = text.strip()
    if not text:
        return "No text provided to summarize."

    _log(f"[summarize] Input: {len(text)} chars, focus='{focus}', max_length={max_length}")

    chunk_size = max(500, max_length * 6)  # rough chars-per-token ratio of ~6
    chunks = _split_chunks(text, chunk_size)
    _log(f"[summarize] Split into {len(chunks)} chunk(s).")

    if len(chunks) == 1:
        summary = _summarize_chunk(chunks[0], focus)
    else:
        partial_summaries = [_summarize_chunk(c, focus) for c in chunks]
        _log(f"[summarize] Merging {len(partial_summaries)} partial summaries...")
        summary = _merge_summaries(partial_summaries, focus)

    _log(f"[summarize] Done — {len(summary)} chars returned.")
    return summary


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def summarize_text(
        text: str,
        focus: str = "",
        max_length: int = 200,
    ) -> str:
        """
        Summarize a block of text using the local LLM.

        Long texts are automatically split into chunks, each summarized
        independently, then merged into a single coherent summary.

        Args:
            text:       The text to summarize. Can be arbitrarily long.
            focus:      Optional instruction to guide the summary
                        (e.g. "key risks", "action items", "technical details").
                        Leave blank for a general summary.
            max_length: Approximate maximum length of the summary in tokens
                        (default 200). Controls verbosity of the output.

        Returns:
            A concise summary of the input text.
        """
        return await _summarize_text(text, focus, max_length)
