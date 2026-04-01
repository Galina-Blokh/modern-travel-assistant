from urllib.parse import quote

import httpx
from langchain_core.tools import tool


@tool
async def get_country_info(country: str) -> str:
    """
    Get facts, currency, population, and language for a country.
    Args:
        country: The name of the country (e.g. "France", "Japan").
    Use this when a user needs country facts.
    """
    if not country or not country.strip():
        return "Please provide a country name."
    country = country.strip()
    encoded = quote(country, safe="")

    try:
        async with httpx.AsyncClient() as client:
            url = f"https://restcountries.com/v3.1/name/{encoded}"
            response = await client.get(url)

            if response.status_code == 404:
                return f"Could not find information for country: {country}."

            response.raise_for_status()
            data = response.json()

            if not data:
                return f"No data returned for country: {country}."

            country_data = data[0]

            name = country_data.get("name", {}).get("common", country)
            capital = ", ".join(country_data.get("capital", ["Unknown"]))
            population = country_data.get("population", "Unknown")
            if isinstance(population, bool):
                pop_str = str(population)
            elif isinstance(population, (int, float)):
                pop_str = f"{int(round(population)):,}"
            else:
                pop_str = str(population)

            currencies = []
            for curr_code, curr_info in country_data.get("currencies", {}).items():
                currencies.append(f"{curr_info.get('name', '')} ({curr_info.get('symbol', '')})")
            currency_str = ", ".join(currencies) if currencies else "Unknown"

            languages = list(country_data.get("languages", {}).values())
            language_str = ", ".join(languages) if languages else "Unknown"

            region = country_data.get("region", "Unknown")
            subregion = country_data.get("subregion", "Unknown")

            return (
                f"Country: {name}\n"
                f"Capital: {capital}\n"
                f"Region: {region} ({subregion})\n"
                f"Population: {pop_str}\n"
                f"Languages: {language_str}\n"
                f"Currency: {currency_str}"
            )

    except Exception as e:
        return f"Error fetching information for {country}: {str(e)}"
