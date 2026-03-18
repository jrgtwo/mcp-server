from __future__ import annotations

import httpx
from fastmcp import FastMCP

from model import _log


async def _define_word(word: str) -> dict:
    """Core definition lookup logic, callable by both the MCP tool and the agent."""
    word = word.strip().lower()
    _log(f"[word_definition] Looking up '{word}'...")

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)

    if resp.status_code == 404:
        _log(f"[word_definition] '{word}' not found.")
        return {"success": False, "word": word, "results": None, "error": f"No definition found for '{word}'."}

    resp.raise_for_status()
    data = resp.json()

    results = []
    for entry in data:
        phonetic = entry.get("phonetic") or next(
            (p.get("text") for p in entry.get("phonetics", []) if p.get("text")), None
        )
        for meaning in entry.get("meanings", []):
            part_of_speech = meaning.get("partOfSpeech", "")
            definitions = [
                {
                    "definition": d.get("definition", ""),
                    "example": d.get("example"),
                    "synonyms": d.get("synonyms", [])[:5],
                    "antonyms": d.get("antonyms", [])[:5],
                }
                for d in meaning.get("definitions", [])[:3]
            ]
            results.append({
                "phonetic": phonetic,
                "part_of_speech": part_of_speech,
                "definitions": definitions,
                "synonyms": meaning.get("synonyms", [])[:5],
                "antonyms": meaning.get("antonyms", [])[:5],
            })

    _log(f"[word_definition] Found {len(results)} meaning(s) for '{word}'.")
    return {"success": True, "word": word, "results": results, "error": None}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def define_word(word: str) -> dict:
        """
        Look up the definition, phonetics, synonyms, and antonyms of an English word
        using the free Dictionary API (dictionaryapi.dev). No API key required.

        Args:
            word: The English word to look up (e.g. "ephemeral", "serendipity").

        Returns:
            A dict with keys:
                - success:  True if the word was found.
                - word:     The normalised word that was looked up.
                - results:  List of meanings, each containing:
                    - phonetic:       IPA phonetic spelling (may be None).
                    - part_of_speech: e.g. "noun", "verb", "adjective".
                    - definitions:    Up to 3 definitions, each with:
                        - definition: The definition text.
                        - example:    Example sentence (may be None).
                        - synonyms:   Up to 5 synonyms.
                        - antonyms:   Up to 5 antonyms.
                    - synonyms:       Up to 5 synonyms for this part of speech.
                    - antonyms:       Up to 5 antonyms for this part of speech.
                - error:    Error message if success is False (None otherwise).
        """
        return await _define_word(word)
