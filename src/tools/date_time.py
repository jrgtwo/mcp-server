from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastmcp import FastMCP

from model import _log


def _get_datetime(timezone_name: str = "UTC") -> str:
    """Core datetime logic, callable by both the MCP tool and the agent."""
    _log(f"[datetime] timezone='{timezone_name}'")
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return (
            f"Unknown timezone '{timezone_name}'. "
            "Use an IANA name like 'UTC', 'America/New_York', or 'Europe/London'. "
            "On Windows, install timezone data with: pip install tzdata"
        )
    now = datetime.now(tz)
    result = now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    _log(f"[datetime] {result}")
    return result


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_datetime(timezone: str = "UTC") -> str:
        """
        Return the current date and time for a given timezone.

        Args:
            timezone: IANA timezone name (e.g. "UTC", "America/New_York",
                      "Europe/London", "Asia/Tokyo"). Defaults to "UTC".
                      On Windows, requires: pip install tzdata

        Returns:
            Date and time string, e.g. "2025-03-01 14:30:00 EST (UTC-0500)".
        """
        return _get_datetime(timezone)
