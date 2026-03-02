from __future__ import annotations

from fastmcp import FastMCP

from model import _log, generate_tokens

_VALID_LEVELS = ("beginner", "intermediate", "advanced")

_LEVEL_GUIDANCE = {
    "beginner": (
        "Assume the reader is new to programming. "
        "Use plain language, avoid jargon, and explain every concept from first principles. "
        "Use analogies and short examples where helpful."
    ),
    "intermediate": (
        "Assume the reader knows the basics of the language. "
        "Focus on how and why the code works, highlight any non-obvious patterns, "
        "and mention relevant language features or idioms."
    ),
    "advanced": (
        "Assume an experienced developer. Be concise and precise. "
        "Focus on design decisions, algorithmic complexity, edge cases, "
        "and any subtle behaviour worth noting."
    ),
}


def _explain_code(
    code: str,
    language: str = "python",
    level: str = "beginner",
    max_new_tokens: int = 768,
) -> str:
    """Explain a code snippet at the requested skill level."""
    if level not in _VALID_LEVELS:
        return (
            f"Invalid level '{level}'. "
            f"Must be one of: {', '.join(_VALID_LEVELS)}."
        )

    code = code[:6000]
    guidance = _LEVEL_GUIDANCE[level]

    prompt = (
        f"[SYSTEM]\n"
        f"You are a patient, knowledgeable coding tutor. "
        f"Explain the following {language} code clearly and accurately.\n"
        f"{guidance}\n\n"
        f"[USER]\n"
        f"Please explain this {language} code:\n\n"
        f"```{language}\n{code}\n```\n\n"
        f"[ASSISTANT]\n"
    )

    _log(f"[explain_code] Explaining {len(code)}-char {language} snippet at level={level}...")
    result = generate_tokens(prompt, max_new_tokens, 0.5, 0.9)
    _log(f"[explain_code] Done — {len(result)} chars generated.")
    return result.strip()


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def explain_code(
        code: str,
        language: str = "python",
        level: str = "beginner",
        max_new_tokens: int = 1024,
    ) -> str:
        """
        Explain a code snippet using the local LLM, tailored to the learner's level.

        Args:
            code:           The source code to explain (capped at 6000 chars).
            language:       Programming language of the snippet (default "python").
            level:          Explanation depth — "beginner", "intermediate", or "advanced".
            max_new_tokens: Maximum tokens for the explanation (default 1024).

        Returns:
            A plain-text explanation of the code at the requested level.
        """
        return _explain_code(code, language, level, max_new_tokens)
