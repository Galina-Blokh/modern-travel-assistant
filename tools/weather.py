import httpx
from langchain_core.tools import tool


@tool
async def get_weather(city: str) -> str:
    """
    Get current weather for a specific city or town the user named (or that was explicitly
    established in the conversation). Do not call with a guessed or default city when the user
    did not specify a place — answer by asking which city they mean instead.
    Args:
        city: Real place name only (e.g. "London", "Kyoto", "Austin").
    """
    if not city or not city.strip():
        return "Please provide a city name."
    city = city.strip()

    try:
        timeout = httpx.Timeout(12.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            geo_response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": city,
                    "count": 1,
                    "language": "en",
                    "format": "json",
                },
            )
            geo_response.raise_for_status()
            geo_data = geo_response.json()

            if not geo_data.get("results"):
                return f"Could not find location coordinates for {city}."

            location = geo_data["results"][0]
            lat = location["latitude"]
            lon = location["longitude"]
            country = location.get("country", "")
            display_name = location.get("name", city)

            weather_response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "timezone": "auto",
                },
            )
            weather_response.raise_for_status()
            weather_data = weather_response.json()

            current = weather_data.get("current", {})
            temp = current.get("temperature_2m", "Unknown")
            humidity = current.get("relative_humidity_2m", "Unknown")
            wind = current.get("wind_speed_10m", "Unknown")

            return (
                f"Current weather in {display_name} ({country}): "
                f"Temperature: {temp}°C, Humidity: {humidity}%, Wind Speed: {wind} km/h."
            )
    except Exception as e:
        return f"Error fetching weather for {city}: {str(e)}"
