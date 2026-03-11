from __future__ import annotations

import asyncio
from functools import partial

import yfinance as yf
from fastmcp import FastMCP

from model import _log


def _fetch_stock(ticker: str) -> str:
    """Synchronous yfinance fetch, run in a thread executor."""
    t = yf.Ticker(ticker)
    info = t.info

    # yfinance returns an empty / minimal dict for unknown tickers
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        return f"Could not retrieve price for ticker '{ticker.upper()}'. Check the symbol and try again."

    name        = info.get("shortName") or info.get("longName") or ticker.upper()
    currency    = info.get("currency", "")
    change      = info.get("regularMarketChange")
    change_pct  = info.get("regularMarketChangePercent")
    prev_close  = info.get("regularMarketPreviousClose")
    day_high    = info.get("regularMarketDayHigh")
    day_low     = info.get("regularMarketDayLow")
    volume      = info.get("regularMarketVolume")
    market_cap  = info.get("marketCap")
    fifty_two_high = info.get("fiftyTwoWeekHigh")
    fifty_two_low  = info.get("fiftyTwoWeekLow")

    lines = [f"{name} ({ticker.upper()})"]
    lines.append(f"  Price:       {price:,.2f} {currency}")

    if change is not None and change_pct is not None:
        sign = "+" if change >= 0 else ""
        lines.append(f"  Change:      {sign}{change:,.2f} ({sign}{change_pct:.2f}%)")

    if prev_close is not None:
        lines.append(f"  Prev close:  {prev_close:,.2f} {currency}")

    if day_high is not None and day_low is not None:
        lines.append(f"  Day range:   {day_low:,.2f} – {day_high:,.2f} {currency}")

    if fifty_two_high is not None and fifty_two_low is not None:
        lines.append(f"  52-wk range: {fifty_two_low:,.2f} – {fifty_two_high:,.2f} {currency}")

    if volume is not None:
        lines.append(f"  Volume:      {volume:,}")

    if market_cap is not None:
        # Format as B/T for readability
        if market_cap >= 1e12:
            cap_str = f"{market_cap / 1e12:.2f}T"
        elif market_cap >= 1e9:
            cap_str = f"{market_cap / 1e9:.2f}B"
        elif market_cap >= 1e6:
            cap_str = f"{market_cap / 1e6:.2f}M"
        else:
            cap_str = f"{market_cap:,}"
        lines.append(f"  Market cap:  {cap_str} {currency}")

    return "\n".join(lines)


async def _get_stock_price(ticker: str) -> str:
    """Core stock price logic, callable by both the MCP tool and the agent."""
    ticker = ticker.strip().upper()
    _log(f"[stock] Fetching price for '{ticker}'...")
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, partial(_fetch_stock, ticker)
        )
    except Exception as exc:
        _log(f"[stock] Error: {exc}")
        return f"Error fetching data for '{ticker}': {exc}"
    _log(f"[stock] Done for '{ticker}'.")
    return result


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_stock_price(ticker: str) -> str:
        """
        Get the current stock price and key market data for a ticker symbol.

        Uses the Yahoo Finance API (no API key required).

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL", "MSFT", "TSLA", "BTC-USD").

        Returns:
            Current price, daily change, day range, 52-week range, volume,
            and market cap for the given ticker.
        """
        return await _get_stock_price(ticker)
