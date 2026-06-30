"""
Weather Service — fetches live data from IMD / OpenWeatherMap.
Falls back to mock data if no API key configured.
"""

import os
import logging
import httpx
from datetime import datetime
from typing import Optional

logger = logging.getLogger("tarang.weather")

OWM_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"


async def get_weather(lat: float, lng: float) -> dict:
    """
    Fetch current weather and marine conditions for given coordinates.
    Returns a standardised dict regardless of data source.
    """
    if OWM_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(OWM_URL, params={
                    "lat": lat, "lon": lng,
                    "appid": OWM_API_KEY,
                    "units": "metric",
                })
                data = resp.json()
                return {
                    "source": "OpenWeatherMap",
                    "temp_c":       data["main"]["temp"],
                    "wind_speed_ms": data["wind"]["speed"],
                    "wind_dir_deg": data["wind"].get("deg", 0),
                    "visibility_m": data.get("visibility", 10000),
                    "description":  data["weather"][0]["description"],
                    "wave_height_m": _estimate_wave(data["wind"]["speed"]),
                    "fetched_at":   datetime.utcnow().isoformat() + "Z",
                }
        except Exception as e:
            logger.warning(f"OWM fetch failed: {e}")

    # ── Open-Meteo Marine API (no key needed) ──────────────
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(MARINE_URL, params={
                "latitude": lat,
                "longitude": lng,
                "current": "wave_height,wave_direction,wave_period",
                "timezone": "Asia/Kolkata",
            })
            data = resp.json()
            current = data.get("current", {})
            wave_h = current.get("wave_height", 1.0)
            return {
                "source": "Open-Meteo Marine",
                "temp_c": None,
                "wind_speed_ms": 6.0,
                "wind_dir_deg":  current.get("wave_direction", 270),
                "visibility_m":  8000,
                "description":   "Coastal marine data",
                "wave_height_m": wave_h,
                "wave_period_s": current.get("wave_period", 8),
                "fetched_at":    datetime.utcnow().isoformat() + "Z",
            }
    except Exception as e:
        logger.warning(f"Open-Meteo failed: {e} — using mock data")

    # ── Mock fallback ──────────────────────────────────────
    return {
        "source":        "mock",
        "temp_c":        29.5,
        "wind_speed_ms": 7.2,
        "wind_dir_deg":  245,
        "visibility_m":  9000,
        "description":   "Partly cloudy, moderate sea",
        "wave_height_m": 1.4,
        "fetched_at":    datetime.utcnow().isoformat() + "Z",
    }


def _estimate_wave(wind_ms: float) -> float:
    """Beaufort-based wave height estimate from wind speed."""
    if wind_ms < 3:    return 0.3
    elif wind_ms < 6:  return 0.8
    elif wind_ms < 10: return 1.5
    elif wind_ms < 14: return 2.5
    elif wind_ms < 18: return 3.5
    return 5.0
