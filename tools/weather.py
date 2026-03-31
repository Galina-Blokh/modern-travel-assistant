import requests
from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get current weather and 3-day forecast for a city."""
    try:
        geo_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=5,
        )
        geo_resp.raise_for_status()
        results = geo_resp.json().get("results")
        if not results:
            return f"Could not find location: '{city}'. Please check the city name and try again."

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        name = results[0].get("name", city)
        country = results[0].get("country", "")

        wx_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
                "forecast_days": 3,
            },
            timeout=5,
        )
        wx_resp.raise_for_status()
        data = wx_resp.json()

        current = data["current_weather"]
        daily = data["daily"]

        lines = [f"Weather in {name}, {country}:"]
        lines.append(f"Now: {current['temperature']}°C, wind {current['windspeed']} km/h")
        lines.append("3-day forecast:")
        for i in range(3):
            lines.append(
                f"  {daily['time'][i]}: "
                f"{daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}°C, "
                f"rain {daily['precipitation_sum'][i]}mm"
            )
        return "\n".join(lines)

    except requests.exceptions.Timeout:
        return f"Weather service timed out for '{city}'. Please try again."
    except Exception as e:
        return f"Weather data unavailable for '{city}'. ({type(e).__name__}: {e})"
