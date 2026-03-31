import requests
from langchain_core.tools import tool


@tool
def get_country_info(country: str) -> str:
    """Get country information including capital, currency, language, and region."""
    try:
        resp = requests.get(
            f"https://restcountries.com/v3.1/name/{country}",
            params={"fields": "name,capital,currencies,languages,region,subregion,idd"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return f"No information found for country: '{country}'."

        c = data[0]
        name = c["name"]["common"]
        capital = ", ".join(c.get("capital", ["N/A"]))
        region = c.get("region", "N/A")
        subregion = c.get("subregion", "")

        currencies = ", ".join(
            f"{v['name']} ({v.get('symbol', '')})"
            for v in c.get("currencies", {}).values()
        )
        languages = ", ".join(c.get("languages", {}).values())

        idd = c.get("idd", {})
        root = idd.get("root", "")
        suffixes = idd.get("suffixes", [""])
        calling_code = f"{root}{suffixes[0]}" if root else "N/A"

        return (
            f"{name}:\n"
            f"  Capital: {capital}\n"
            f"  Region: {region}{' / ' + subregion if subregion else ''}\n"
            f"  Currency: {currencies}\n"
            f"  Languages: {languages}\n"
            f"  Calling code: {calling_code}\n"
            f"  Visa note: Check your government's travel advisory for current visa requirements."
        )

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return f"Country '{country}' not found. Please check the spelling."
        return f"Country information unavailable for '{country}'. ({e})"
    except requests.exceptions.Timeout:
        return f"Country service timed out for '{country}'. Please try again."
    except Exception as e:
        return f"Country information unavailable for '{country}'. ({type(e).__name__}: {e})"
