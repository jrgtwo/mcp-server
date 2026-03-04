from __future__ import annotations

import uuid
from pathlib import Path

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from model import _log

# Uploads folder at the project root (one level above src/)
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"

# In-memory registry: upload_id -> absolute path on disk
_uploads: dict[str, str] = {}


def resolve(upload_id: str) -> str | None:
    """Return the file path for an upload ID, or None if unknown."""
    return _uploads.get(upload_id)


def register(mcp: FastMCP) -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)

    @mcp.custom_route("/upload", methods=["POST"])
    async def upload_pdf(request: Request) -> JSONResponse:
        """
        Upload a PDF file and receive an upload_id to pass to run_agent.

        Accepts multipart/form-data with a single field named 'file'.
        Returns: {"upload_id": "<id>", "filename": "<original name>", "size": <bytes>}
        """
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            return JSONResponse(
                {"error": "Expected multipart/form-data"},
                status_code=415,
            )

        form = await request.form()
        file = form.get("file")
        if file is None:
            return JSONResponse(
                {"error": "No 'file' field in form data"},
                status_code=400,
            )

        filename: str = getattr(file, "filename", None) or "upload.pdf"
        data: bytes = await file.read()

        if not data:
            return JSONResponse({"error": "Uploaded file is empty"}, status_code=400)

        upload_id = uuid.uuid4().hex
        dest = UPLOAD_DIR / f"{upload_id}.pdf"
        dest.write_bytes(data)

        _uploads[upload_id] = str(dest)
        _log(f"[upload] Saved '{filename}' ({len(data)} bytes) → id={upload_id}")

        return JSONResponse({
            "upload_id": upload_id,
            "filename": filename,
            "size": len(data),
        })
