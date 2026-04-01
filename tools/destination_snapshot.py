"""Single parallel batch for trip planning — one model step instead of three serial tool rounds."""

import asyncio

from langchain_core.tools import tool

from .weather import get_weather
from .country import get_country_info
from .attractions import get_attractions


def _section(label: str, result: object) -> str:
    if isinstance(result, Exception):
        return f"## {label}\n_(Could not load this part — {type(result).__name__})_"
    return f"## {label}\n{result}"


@tool
async def get_destination_snapshot(city: str, country: str) -> str:
    """Load weather, country facts, and city attractions together in parallel.

    Use when the user is planning a trip, wants an overview of a place, or asks for
    multiple of: weather + country info + things to do — and you know both the main
    city and the country. If you only need one kind of data, use a single-purpose tool
    instead (faster).

    Args:
        city: Main city for weather and attractions (e.g. the capital or base city).
        country: Country name as the user would say it (e.g. "France", "Japan").
    """
    if not city or not city.strip() or not country or not country.strip():
        return "Both a city and a country are required for a destination overview."
    city = city.strip()
    country = country.strip()

    weather_t, country_t, attr_t = await asyncio.gather(
        get_weather.ainvoke({"city": city}),
        get_country_info.ainvoke({"country": country}),
        get_attractions.ainvoke({"city": city}),
        return_exceptions=True,
    )

    return "\n\n".join(
        [
            _section("Weather", weather_t),
            _section("Country", country_t),
            _section("Attractions", attr_t),
        ]
    )
