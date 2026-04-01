import asyncio
import re

import wikipedia
from langchain_core.tools import tool


def _title_matches_city(title: str, city: str) -> bool:
    """Require the article title to mention the city (avoids generic 'attractions' hits)."""
    t = title.lower()
    c = city.lower().strip()
    if c in t:
        return True
    words = [w for w in re.split(r"\W+", c) if len(w) > 2]
    if not words:
        return c in t
    return all(w in t for w in words)


def _fetch_wiki_sync(city: str) -> str | None:
    wikipedia.set_lang("en")
    city_q = city.strip()

    def try_page(title: str, auto_suggest: bool) -> str | None:
        try:
            page = wikipedia.page(title, auto_suggest=auto_suggest)
        except wikipedia.DisambiguationError as e:
            for opt in e.options[:10]:
                if not _title_matches_city(opt, city_q):
                    continue
                try:
                    page = wikipedia.page(opt, auto_suggest=False)
                    break
                except Exception:
                    continue
            else:
                return None
        except (wikipedia.PageError, wikipedia.RedirectError):
            return None
        except Exception:
            return None

        if not _title_matches_city(page.title, city_q):
            return None
        snippet = (page.summary or "")[:2000]
        return f"**{page.title}**\n\n{snippet}"

    # Try stable article titles first (major cities resolve correctly)
    for query in (city_q, f"{city_q} (city)", f"Tourism in {city_q}"):
        out = try_page(query, auto_suggest=True)
        if out:
            return out

    # Search and pick the first result whose title matches the city
    try:
        hits = wikipedia.search(f"{city_q} city travel tourism", results=10)
    except Exception:
        hits = []

    for hit in hits:
        if not _title_matches_city(hit, city_q):
            continue
        out = try_page(hit, auto_suggest=False)
        if out:
            return out

    return None


@tool
async def get_attractions(city: str) -> str:
    """
    Get tourist context for a city from Wikipedia (summary of the city-anchored article).
    Args:
        city: The name of the city (e.g. "London", "Tokyo", "Paris").
    Use when a user asks for things to do, places to visit, or local attractions.
    """
    if not city or not city.strip():
        return "Please provide a city name."
    city = city.strip()

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _fetch_wiki_sync, city)

        if not result:
            return (
                f"Could not find a Wikipedia article clearly about **{city}**. "
                f"Try a slightly different spelling or add the country (e.g. “Paris, France”)."
            )

        return f"Attractions and visitor context for **{city}**:\n\n{result}"

    except Exception as e:
        return f"Error fetching attractions for {city}: {str(e)}"
