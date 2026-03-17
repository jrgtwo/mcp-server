from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

from model import _log

WhisperModel = Literal["tiny", "base", "small", "medium", "large-v3"]

# Model sizes and approximate VRAM/RAM requirements:
#   tiny    ~150 MB    fastest, least accurate
#   base    ~290 MB
#   small   ~970 MB    good balance of speed/accuracy
#   medium  ~3.1 GB
#   large-v3 ~6.2 GB  most accurate


def _transcribe(
    audio_path: str,
    model_size: WhisperModel,
    language: str | None,
    device: str,
    compute_type: str,
) -> dict:
    """Synchronous transcription — run in a thread executor."""
    try:
        from faster_whisper import WhisperModel as FasterWhisperModel
    except ImportError:
        return {
            "success": False,
            "text": None,
            "language": None,
            "duration_seconds": None,
            "error": "faster-whisper is not installed. Run: pip install faster-whisper",
        }

    path = Path(audio_path)
    if not path.exists():
        return {
            "success": False,
            "text": None,
            "language": None,
            "duration_seconds": None,
            "error": f"File not found: {audio_path}",
        }

    _log(f"[transcribe] Loading Whisper model '{model_size}' on {device}...")
    model = FasterWhisperModel(model_size, device=device, compute_type=compute_type)

    _log(f"[transcribe] Transcribing '{path.name}'...")
    segments, info = model.transcribe(str(path), language=language or None)

    text = " ".join(segment.text.strip() for segment in segments).strip()
    _log(f"[transcribe] Done. Detected language: {info.language}, duration: {info.duration:.1f}s")

    return {
        "success": True,
        "text": text,
        "language": info.language,
        "duration_seconds": round(info.duration, 2),
        "error": None,
    }


async def _transcribe_audio(
    audio_path: str,
    model_size: WhisperModel = "base",
    language: str | None = None,
    device: str = "auto",
    compute_type: str = "auto",
) -> dict:
    """Core transcription logic, callable by both the MCP tool and the agent."""
    # Resolve device/compute defaults
    resolved_device = device
    resolved_compute = compute_type

    if device == "auto":
        try:
            import torch
            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            resolved_device = "cpu"

    if compute_type == "auto":
        resolved_compute = "float16" if resolved_device == "cuda" else "int8"

    _log(f"[transcribe] device={resolved_device}, compute_type={resolved_compute}")

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            partial(_transcribe, audio_path, model_size, language, resolved_device, resolved_compute),
        )
    except Exception as exc:
        _log(f"[transcribe] Unexpected error: {exc}")
        return {
            "success": False,
            "text": None,
            "language": None,
            "duration_seconds": None,
            "error": str(exc),
        }

    return result


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def transcribe_audio(
        audio_path: str,
        model_size: WhisperModel = "base",
        language: str | None = None,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> dict:
        """
        Transcribe an audio file to text using a local Whisper model (via faster-whisper).
        Runs entirely on-device — no API key or internet connection required.

        Supported formats: mp3, mp4, wav, flac, ogg, m4a, webm, and most ffmpeg-readable formats.

        Args:
            audio_path: Absolute or relative path to the audio file.
            model_size: Whisper model to use. Larger models are more accurate but slower.
                "tiny"     — ~150 MB, fastest
                "base"     — ~290 MB, good for quick tasks (default)
                "small"    — ~970 MB, recommended balance
                "medium"   — ~3.1 GB
                "large-v3" — ~6.2 GB, most accurate
                Models are downloaded automatically on first use.
            language: ISO-639-1 language code to force (e.g. "en", "fr", "de").
                      Leave as null to auto-detect.
            device: Inference device. "auto" selects CUDA if available, else CPU.
                    Explicit options: "cuda", "cpu".
            compute_type: Precision used for inference. "auto" picks float16 on GPU,
                          int8 on CPU. Explicit options: "float16", "int8", "float32".

        Returns:
            A dict with keys:
                - success: True if transcription succeeded
                - text: The transcribed text (None on failure)
                - language: Detected or forced language code
                - duration_seconds: Audio duration in seconds
                - error: Error message if success is False (None otherwise)
        """
        return await _transcribe_audio(audio_path, model_size, language, device, compute_type)
