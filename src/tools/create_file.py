from __future__ import annotations

import codecs
from pathlib import Path

from fastmcp import FastMCP

from model import _log


async def _create_file(
    file_name: str,
    content: str,
    directory: str | None = None,
    encoding: str = "utf-8",
    overwrite: bool = False,
) -> dict[str, str | bool]:
    """
    Core file creation logic, callable by both the MCP tool and the agent.
    """
    # Validate filename - reject path components
    if not file_name:
        return {
            "success": False,
            "file_path": None,
            "error": "Filename cannot be empty",
            "message": "Please provide a valid filename",
        }

    # Reject path separators in filename
    if "/" in file_name or "\\" in file_name:
        return {
            "success": False,
            "file_path": None,
            "error": "Filename cannot contain path separators",
            "message": "Use only the basename without directories",
        }

    # Reject path traversal attempts
    if ".." in file_name:
        return {
            "success": False,
            "file_path": None,
            "error": "Security error: Path traversal detected",
            "message": "Use a safe filename without path components",
        }

    # Reject null bytes and control characters
    if "\x00" in file_name or any(ord(c) < 32 for c in file_name):
        return {
            "success": False,
            "file_path": None,
            "error": "Filename contains invalid characters",
            "message": "Use only printable ASCII characters",
        }

    # Validate encoding
    try:
        codecs.lookup(encoding)
    except LookupError as exc:
        return {
            "success": False,
            "file_path": None,
            "error": f"Invalid encoding: '{encoding}'",
            "message": f"Supported encodings depend on your Python installation",
        }

    # Determine target directory
    if directory:
        # Resolve directory path safely
        try:
            target_dir = Path(directory).resolve()
            # Check it's not trying to escape current directory
            base_dir = Path.cwd().resolve()
            try:
                target_dir.relative_to(base_dir)
            except ValueError:
                return {
                    "success": False,
                    "file_path": None,
                    "error": f"Directory path '{directory}' would escape current directory",
                    "message": "Directory must be within the current working directory",
                }
        except Exception as exc:
            return {
                "success": False,
                "file_path": None,
                "error": f"Invalid directory path: {exc}",
                "message": "Please provide a valid directory path",
            }
    else:
        target_dir = Path.cwd()

    # Ensure directory exists
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        _log(f"[create_file] Ensured directory exists: {target_dir}")
    except Exception as exc:
        return {
            "success": False,
            "file_path": None,
            "error": f"Cannot create directory: {exc}",
            "message": "Cannot create the specified directory",
        }

    # Construct file path
    file_path = (target_dir / file_name).resolve()

    # Check if file exists
    if file_path.exists():
        if overwrite:
            _log(f"[create_file] Overwriting existing file: {file_path}")
        else:
            return {
                "success": False,
                "file_path": None,
                "error": f"File already exists: '{file_name}'",
                "message": "Use overwrite=True or provide a different filename",
            }

    # Write file
    try:
        file_path.write_text(content, encoding=encoding)
        _log(f"[create_file] Created '{file_path}' ({len(content)} bytes)")
    except PermissionError:
        return {
            "success": False,
            "file_path": None,
            "error": f"Permission denied: cannot write to '{file_path}'",
            "message": "Check file permissions and directory ownership",
        }
    except OSError as exc:
        return {
            "success": False,
            "file_path": None,
            "error": f"Could not create file: {exc}",
            "message": "Ensure the directory exists and is writable",
        }

    return {
        "success": True,
        "file_path": str(file_path),
        "error": None,
        "message": f"File created successfully at {file_path}",
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def create_file(
        file_name: str,
        content: str,
        directory: str | None = None,
        encoding: str = "utf-8",
        overwrite: bool = False,
    ) -> dict[str, str | bool]:
        """
        Create a file with the given name and content.

        Args:
            file_name: Basename of the file to create (no path components).
            content: The content to write to the file.
            directory: Optional directory path where file should be created.
                      If relative, resolved from current working directory.
            encoding: Character encoding for the file (default: utf-8).
            overwrite: Whether to overwrite existing files (default: False).

        Returns:
            A dict with keys:
                - success: True if file was created, False otherwise
                - file_path: Absolute path to created file (None if failed)
                - error: Error message if success is False (None otherwise)
                - message: Human-readable status message

        Examples:
            # Create file in current directory
            create_file("notes.md", "# Notes\\n")

            # Create in subdirectory
            create_file("config.json", "{}", directory="src")

            # Overwrite existing file
            create_file("data.txt", "new content", overwrite=True)
        """
        return await _create_file(file_name, content, directory, encoding, overwrite)