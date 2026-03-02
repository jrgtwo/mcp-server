from __future__ import annotations

from fastmcp import FastMCP

from model import _log, generate_tokens

_VALID_FOCUS = ("general", "security", "performance", "style")

_FOCUS_GUIDANCE = {
    "general": (
        "Review the code holistically. Look for bugs, logic errors, bad practices, "
        "readability issues, and any quick wins that would improve the code."
    ),
    "security": (
        "Focus on security vulnerabilities: injection risks, improper input validation, "
        "insecure data handling, authentication/authorisation flaws, secrets in code, "
        "and known CVE patterns relevant to the language or framework."
    ),
    "performance": (
        "Focus on performance: algorithmic complexity (Big-O), unnecessary allocations, "
        "redundant work, blocking calls, missing caching opportunities, and data-structure choices."
    ),
    "style": (
        "Focus on code style and maintainability: naming conventions, function/class length, "
        "code duplication, comment quality, adherence to idiomatic patterns for the language, "
        "and overall readability."
    ),
}

_REVIEW_FORMAT = """\
Structure your review in exactly these four sections:
1. **Overall Impression** — one or two sentences.
2. **Issues Found** — numbered list; each entry must state:
   - Severity: [critical / high / medium / low / info]
   - Location: line number or function name if identifiable
   - Description: what the problem is and why it matters
   - Fix: a concrete suggestion or corrected snippet
3. **Positives** — bullet list of things done well.
4. **Top Recommendation** — the single most important change to make first.
"""


def _review_code(
    code: str,
    language: str = "python",
    focus: str = "general",
    max_new_tokens: int = 768,
) -> str:
    """Review a code snippet for bugs, style, security, or performance issues."""
    if focus not in _VALID_FOCUS:
        return (
            f"Invalid focus '{focus}'. "
            f"Must be one of: {', '.join(_VALID_FOCUS)}."
        )

    code = code[:6000]
    guidance = _FOCUS_GUIDANCE[focus]

    prompt = (
        f"[SYSTEM]\n"
        f"You are an expert code reviewer. "
        f"Provide a thorough, actionable review of the following {language} code.\n"
        f"{guidance}\n\n"
        f"{_REVIEW_FORMAT}\n"
        f"[USER]\n"
        f"Please review this {language} code (focus: {focus}):\n\n"
        f"```{language}\n{code}\n```\n\n"
        f"[ASSISTANT]\n"
    )

    _log(f"[review_code] Reviewing {len(code)}-char {language} snippet, focus={focus}...")
    result = generate_tokens(prompt, max_new_tokens, 0.4, 0.9)
    _log(f"[review_code] Done — {len(result)} chars generated.")
    return result.strip()


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def review_code(
        code: str,
        language: str = "python",
        focus: str = "general",
        max_new_tokens: int = 768,
    ) -> str:
        """
        Review a code snippet for issues using the local LLM.

        Args:
            code:           The source code to review (capped at 6000 chars).
            language:       Programming language of the snippet (default "python").
            focus:          Review focus — "general", "security", "performance", or "style".
            max_new_tokens: Maximum tokens for the review (default 768).

        Returns:
            A structured review with overall impression, numbered issues (with severity),
            positives, and a top recommendation.
        """
        return _review_code(code, language, focus, max_new_tokens)
