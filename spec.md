# Travel Assistant — Agentic Tools Architecture (Option 1)

Detailed specification for building the travel assistant using the Agentic Tools (Function Calling) architecture on the `agentic-tool-mcp` branch.

---

## Project Overview

A conversational travel assistant where the LLM autonomously decides when to call external tools (weather, country info, attractions) vs. answer from its own knowledge. Built with Streamlit, LangChain, and DeepSeek (or Ollama).

---

## Goals

- Natural multi-turn conversation across 3+ travel query types
- LLM-driven tool-use decision making (no hardcoded routing)
- Demonstrable chain-of-thought reasoning
- Async parallel API fetching for low latency
- Clean prompt engineering notes

---

## Tech Stack

| Layer         | Technology                          |
|---------------|-------------------------------------|
| UI            | Streamlit                           |
| LLM           | DeepSeek API (fallback: Ollama)     |
| Agent         | LangChain `initialize_agent` / LCEL |
| Memory        | `ConversationBufferMemory`          |
| Weather API   | Open-Meteo (free, no key required)  |
| Country API   | RestCountries (free, no key)        |
| Attractions   | OpenTripMap API (free tier)         |
| Async         | `asyncio` + `nest-asyncio`          |
| Config        | `python-dotenv`                     |

---

## Project Structure

```
modern-travel-assistant/
├── app.py                  # Streamlit entry point
├── agent/
│   ├── __init__.py
│   ├── agent.py            # LangChain agent setup
│   ├── memory.py           # ConversationBufferMemory wrapper
│   └── prompts.py          # System prompt + CoT templates
├── tools/
│   ├── __init__.py
│   ├── weather.py          # get_weather(city) → Open-Meteo
│   ├── country.py          # get_country_info(country) → RestCountries
│   └── attractions.py      # get_attractions(city) → OpenTripMap
├── utils/
│   ├── __init__.py
│   ├── async_tools.py      # asyncio.gather() parallel fetcher
│   └── error_handler.py    # Retry + hallucination guard
├── transcripts/
│   └── sample_conversations.md
├── .env.example
├── requirements.txt
├── README.md
├── PROMPT_ENGINEERING_NOTES.md
└── spec.md
```

---

## Core Components

### 1. Tools

#### `get_weather(city: str) → str`
- Calls Open-Meteo geocoding + forecast endpoint
- Returns: current temp, condition, 3-day forecast summary
- No API key required

#### `get_country_info(country: str) → str`
- Calls `https://restcountries.com/v3.1/name/{country}`
- Returns: capital, currency, language, region, calling code
- No API key required

#### `get_attractions(city: str) → str`
- Calls OpenTripMap `/geoname` + `/radius` endpoints
- Returns: top 5 POIs with name, kind, distance
- Free tier: 1000 req/day (requires free key in `.env`)

---

### 2. Agent Setup (`agent/agent.py`)

```python
tools = [get_weather_tool, get_country_info_tool, get_attractions_tool]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=3,
)
```

- Agent type: `CONVERSATIONAL_REACT_DESCRIPTION` — reasons about which tool to call per turn
- `handle_parsing_errors=True` — graceful recovery from malformed tool-call JSON
- `max_iterations=3` — prevents infinite loops

---

### 3. Async & Parallel Tool Execution (`utils/async_tools.py`) <!-- section 3 -->

When a query requires multiple tools (e.g. itinerary: weather + country + attractions), they are fetched **concurrently** using `asyncio.gather()` instead of serially.

```python
import asyncio

async def fetch_all(city: str, country: str) -> dict:
    weather, info, places = await asyncio.gather(
        asyncio.to_thread(get_weather, city),
        asyncio.to_thread(get_country_info, country),
        asyncio.to_thread(get_attractions, city),
    )
    return {"weather": weather, "country": info, "attractions": places}
```

- `asyncio.to_thread()` wraps the synchronous HTTP calls so they run in a thread pool without blocking the event loop
- The agent calls `fetch_all()` via `asyncio.run()` when it detects a multi-tool intent
- Single-tool queries (e.g. pure weather) still go through the standard synchronous tool path — no overhead
- Streamlit compatibility: use `nest_asyncio.apply()` at app startup to allow `asyncio.run()` inside Streamlit's own event loop

**Latency improvement:** 3 serial API calls (~1.5s each) → ~1.5s total (parallel). Saves ~3s per complex query.

**Updated `requirements.txt`:**
```
nest-asyncio>=1.6.0
```

---

### 4. Prompt Engineering (`agent/prompts.py`)

#### System Prompt
```
You are an expert travel assistant. You have access to real-time tools for weather,
country information, and local attractions. 

DECISION RULES:
- Use get_weather when the user asks about current or upcoming weather at a destination.
- Use get_country_info when the user asks about visas, currency, language, or general country facts.
- Use get_attractions when the user asks what to do, see, or visit in a city.
- Answer from your own knowledge for packing advice, general travel tips, and cultural guidance.

Always be concise, warm, and practical.
```

#### Chain-of-Thought Prompt (injected for itinerary/recommendation queries)
```
Before providing a recommendation, think step-by-step:
1. Consider the user's stated budget and trip duration.
2. Check the seasonal weather for the destination.
3. Identify attractions matching their stated interests.
4. Flag any visa or currency considerations.
Only then output the final structured advice.
```

---

### 5. Memory (`agent/memory.py`)

- `ConversationBufferMemory(memory_key="chat_history", return_messages=True)`
- Passed directly to the agent so all prior turns are visible
- Reset button in Streamlit sidebar clears memory for a new session

---

### 6. Streamlit UI (`app.py`)

- Chat input at bottom, message history scrolls above
- Sidebar: model selector (DeepSeek / Ollama), memory reset button, API status indicators
- Each tool call shown as an expandable "Thinking..." block (via `st.expander`)
- Error messages shown inline in the chat as assistant messages

---

## Query Types Covered

| Type                  | Tool Used             | Example Query                              |
|-----------------------|-----------------------|--------------------------------------------|
| Weather               | `get_weather`         | "What's the weather in Barcelona in June?" |
| Country facts         | `get_country_info`    | "Do I need a visa for Japan?"              |
| Attractions/POIs      | `get_attractions`     | "What should I visit in Lisbon?"           |
| Packing advice        | LLM knowledge         | "What should I pack for a beach trip?"     |
| Itinerary planning    | CoT + multiple tools  | "Plan a 3-day trip to Rome on a budget"    |

---

## Error Handling

| Scenario                     | Handling Strategy                                              |
|------------------------------|----------------------------------------------------------------|
| API timeout / 5xx            | `try/except` in each tool, returns graceful fallback string    |
| LLM malformed tool-call JSON | `handle_parsing_errors=True` + retry with simplified prompt    |
| Hallucinated hotel/flight    | Disclaimer appended: "Please verify bookings independently"    |
| Rate limit (OpenTripMap)     | Cached results per city using `functools.lru_cache`            |
| No internet                  | Tools return "data unavailable" string, LLM falls back to knowledge |

---

## Environment Variables (`.env.example`)

```
DEEPSEEK_API_KEY=your_key_here
OPENTRIPMAP_API_KEY=your_key_here
OLLAMA_BASE_URL=http://localhost:11434  # optional
```

---

## Requirements (`requirements.txt`)

```
streamlit>=1.32.0
langchain>=0.1.16
langchain-community>=0.0.32
langchain-openai>=0.1.0
openai>=1.23.0
requests>=2.31.0
python-dotenv>=1.0.0
nest-asyncio>=1.6.0
```

---

## Sample Conversations

To be added in `transcripts/sample_conversations.md` after implementation, covering:
1. Single-tool call (weather query)
2. Multi-tool call (plan a trip → weather + country + attractions)
3. LLM-only response (packing advice)
4. Error recovery (bad city name)
5. Follow-up context retention (multi-turn)

---

## Further Documentation

- See `README.md` for setup and run instructions.
- See `PROMPT_ENGINEERING_NOTES.md` for prompt design rationale.
- See `transcripts/sample_conversations.md` for example conversations.
