import os
import functools
import requests
from langchain_core.tools import tool


@functools.lru_cache(maxsize=64)
def _fetch_attractions(city: str, api_key: str) -> str:
    geo_resp = requests.get(
        "https://api.opentripmap.com/0.1/en/places/geoname",
        params={"name": city, "apikey": api_key},
        timeout=5,
    )
    geo_resp.raise_for_status()
    geo_data = geo_resp.json()

    if geo_data.get("status") == "NOT FOUND" or "lat" not in geo_data:
        return f"Could not find location for attractions search: '{city}'."

    lat = geo_data["lat"]
    lon = geo_data["lon"]

    places_resp = requests.get(
        "https://api.opentripmap.com/0.1/en/places/radius",
        params={
            "radius": 5000,
            "lon": lon,
            "lat": lat,
            "limit": 5,
            "rate": 3,
            "format": "json",
            "apikey": api_key,
        },
        timeout=5,
    )
    places_resp.raise_for_status()
    places = places_resp.json()

    if not places:
        return f"No notable attractions found near '{city}'."

    lines = [f"Top attractions in {city}:"]
    for i, p in enumerate(places, 1):
        name = p.get("name") or "Unnamed site"
        kinds = p.get("kinds", "").replace(",", ", ")
        dist = p.get("dist", 0)
        lines.append(f"  {i}. {name} ({kinds}) — {int(dist)}m from city center")
    return "\n".join(lines)


@tool
def get_attractions(city: str) -> str:
    """Get top local attractions and points of interest for a city."""
    api_key = os.getenv("OPENTRIPMAP_API_KEY", "")
    if not api_key:
        return (
            f"OpenTripMap API key is not configured. "
            f"Add OPENTRIPMAP_API_KEY to your .env file to fetch attractions for '{city}'."
        )
    try:
        return _fetch_attractions(city, api_key)
    except requests.exceptions.Timeout:
        return f"Attractions service timed out for '{city}'. Please try again."
    except Exception as e:
        return f"Attractions data unavailable for '{city}'. ({type(e).__name__}: {e})"
