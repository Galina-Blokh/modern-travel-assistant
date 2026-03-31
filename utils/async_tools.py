import asyncio
from tools.weather import get_weather
from tools.country import get_country_info
from tools.attractions import get_attractions


async def fetch_all(city: str, country: str) -> dict:
    """Fetch weather, country info, and attractions concurrently using asyncio.gather()."""
    weather, info, places = await asyncio.gather(
        asyncio.to_thread(get_weather.func, city),
        asyncio.to_thread(get_country_info.func, country),
        asyncio.to_thread(get_attractions.func, city),
    )
    return {"weather": weather, "country": info, "attractions": places}


def run_fetch_all(city: str, country: str) -> dict:
    """Synchronous wrapper — runs fetch_all in the current event loop (nest_asyncio required)."""
    return asyncio.run(fetch_all(city, country))
