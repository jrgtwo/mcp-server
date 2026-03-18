from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path

from fastmcp import FastMCP

from model import _log


def _synthesize(text: str, output_path: str, lang: str, slow: bool) -> dict:
    """Synchronous gTTS synthesis — run in a thread executor."""
    try:
        from gtts import gTTS
    except ImportError:
        return {
            "success": False,
            "output_path": None,
            "error": "gTTS is not installed. Run: pip install gtts",
        }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    _log(f"[tts] Synthesising {len(text)} chars → '{out.name}' (lang={lang}, slow={slow})...")
    tts = gTTS(text=text, lang=lang, slow=slow)
    tts.save(str(out))
    _log(f"[tts] Saved to '{out}'.")

    return {"success": True, "output_path": str(out.resolve()), "error": None}


async def _text_to_speech(
    text: str,
    output_path: str,
    lang: str = "en",
    slow: bool = False,
) -> dict:
    """Core TTS logic, callable by both the MCP tool and the agent."""
    _log(f"[tts] Request: lang={lang}, slow={slow}, output='{output_path}'")
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, partial(_synthesize, text, output_path, lang, slow)
        )
    except Exception as exc:
        _log(f"[tts] Unexpected error: {exc}")
        return {"success": False, "output_path": None, "error": str(exc)}
    return result


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def text_to_speech(
        text: str,
        output_path: str,
        lang: str = "en",
        slow: bool = False,
    ) -> dict:
        """
        Convert text to speech and save the result as an MP3 file using Google TTS (gTTS).
        Requires an internet connection. No API key needed.

        Args:
            text:        The text to convert to speech.
            output_path: File path where the MP3 will be saved (e.g. "output/speech.mp3").
                         Parent directories are created automatically.
            lang:        BCP-47 language code (e.g. "en", "fr", "es", "de", "ja").
                         Defaults to "en".
            slow:        If True, speech is generated at a slower rate. Default: False.

        Returns:
            A dict with keys:
                - success:      True if the file was saved successfully.
                - output_path:  Absolute path to the saved MP3 (None on failure).
                - error:        Error message if success is False (None otherwise).
        """
        return await _text_to_speech(text, output_path, lang, slow)
