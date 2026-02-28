from __future__ import annotations

import httpx
from fastmcp import FastMCP

_WMO_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ slight hail", 99: "Thunderstorm w/ heavy hail",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_weather(location: str, units: str = "metric") -> str:
        """
        Fetch the current weather for a location using the free Open-Meteo API.
        No API key required.

        Args:
            location: City name or region (e.g. "London", "New York", "Tokyo").
            units:    "metric" (°C, km/h) or "imperial" (°F, mph). Default: metric.

        Returns:
            A short summary of current conditions (temperature, humidity,
            wind speed, and weather description).
        """
        if units not in ("metric", "imperial"):
            return f"Invalid units '{units}'. Choose 'metric' or 'imperial'."

        async with httpx.AsyncClient(timeout=10) as client:
            # 1. Geocode the location name → lat/lon
            geo_resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1, "language": "en", "format": "json"},
            )
            geo_resp.raise_for_status()
            geo = geo_resp.json()

            results = geo.get("results")
            if not results:
                return f"Location '{location}' not found."

            r = results[0]
            lat, lon = r["latitude"], r["longitude"]
            display_name = ", ".join(
                filter(None, [r.get("name"), r.get("admin1"), r.get("country")])
            )

            # 2. Fetch current weather
            temp_unit = "celsius" if units == "metric" else "fahrenheit"
            wind_unit = "kmh" if units == "metric" else "mph"
            wx_resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                    "temperature_unit": temp_unit,
                    "wind_speed_unit": wind_unit,
                },
            )
            wx_resp.raise_for_status()
            wx = wx_resp.json()

        current = wx["current"]
        temp        = current["temperature_2m"]
        humidity    = current["relative_humidity_2m"]
        wind        = current["wind_speed_10m"]
        code        = current["weather_code"]
        description = _WMO_CODES.get(code, f"Unknown (WMO {code})")

        t_sym = "°C" if units == "metric" else "°F"
        w_sym = "km/h" if units == "metric" else "mph"

        return (
            f"Weather in {display_name}:\n"
            f"  Conditions:  {description}\n"
            f"  Temperature: {temp}{t_sym}\n"
            f"  Humidity:    {humidity}%\n"
            f"  Wind:        {wind} {w_sym}"
        )
