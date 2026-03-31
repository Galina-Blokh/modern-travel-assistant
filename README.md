# Modern Travel Assistant — Agentic Tools

A conversational travel assistant powered by DeepSeek or Ollama via LangChain.
The LLM acts as a reasoning engine that autonomously decides when to call
external APIs vs. answer from its own knowledge, with real-time token streaming.

## Features

- Real-time weather forecasts via Open-Meteo (free, no key needed)
- Country facts — visa, currency, language — via RestCountries (free, no key)
- Local attractions via OpenTripMap (free tier, key required)
- Multi-turn conversation memory across the session
- Selective Chain-of-Thought for itinerary planning
- Async parallel API fetching for low latency on complex queries
- Token streaming — responses appear word-by-word in the UI

---

## Setup

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) package manager

### 1. Clone & install

```bash
git clone https://github.com/Galina-Blokh/modern-travel-assistant.git
cd modern-travel-assistant
git checkout agentic-tool-mcp
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — add your API keys (see table below)
```

### 3. Run

```bash
uv run streamlit run app.py
```

---

## Model Options

Select the LLM in the sidebar at runtime:

| Label | Model | Cost | Requires |
|-------|-------|------|----------|
| `deepseek-chat (API)` | DeepSeek-V3 via cloud API | ~$0.07/1M tokens | `DEEPSEEK_API_KEY` |
| `deepseek-r1:7b (Ollama, free)` | DeepSeek-R1 7B, local | **Free** | Ollama + `ollama pull deepseek-r1:7b` |
| `llama3 (Ollama, free)` | Llama 3 8B, local | **Free** | Ollama + `ollama pull llama3` |

For the **free local option**:
```bash
# Install Ollama: https://ollama.com
ollama pull deepseek-r1:7b
# Select "deepseek-r1:7b (Ollama, free)" in the sidebar
```

---

## API Keys

| Service | Key Required | Free Tier | Get Key |
|---------|:---:|---|---|
| DeepSeek | Yes (if using API) | $5 free credit on signup | platform.deepseek.com |
| OpenTripMap | Yes | 1 000 req/day | opentripmap.io |
| Open-Meteo | No | Unlimited | — |
| RestCountries | No | Unlimited | — |

---

## Project Structure

```
modern-travel-assistant/
├── app.py                    # Streamlit entry point (streaming UI)
├── agent/
│   ├── agent.py              # TravelAgent class + StreamHandler
│   ├── memory.py             # ConversationHistory (HumanMessage/AIMessage)
│   └── prompts.py            # System prompt + selective CoT injection
├── tools/
│   ├── weather.py            # get_weather → Open-Meteo
│   ├── country.py            # get_country_info → RestCountries
│   └── attractions.py        # get_attractions → OpenTripMap (LRU cached)
├── utils/
│   ├── async_tools.py        # asyncio.gather() parallel fetcher
│   └── error_handler.py      # retry decorator + hallucination disclaimer
├── transcripts/
│   └── sample_conversations.md
├── pyproject.toml            # uv project config (Python 3.12)
├── requirements.txt
├── .env.example
└── spec.md
```

---

## Prompt Engineering Decisions

### 1. Three-step decision method

Every message is evaluated with a fixed sequence:
**Step 1** — Is it travel-related? If not, deflect politely.
**Step 2** — Which tool applies (weather / country / attractions) or is own-knowledge enough?
**Step 3** — Honesty check: uncertain about a fact → say so, suggest a better source.

This prevents both tool overuse (calling weather for a packing question) and
tool underuse (answering visa rules from stale training data).

### 2. Explicit honesty rules with named sources

The system prompt lists specific categories where the LLM must admit ignorance:
flight prices, visa processing times, medical requirements, recent advisories.
For each it names a concrete alternative source (Google Flights, embassy website,
cdc.gov/travel). This produces "I don't have current information on X — check Y"
rather than a confident but wrong answer.

### 3. Function-calling agent, not text REACT

`create_openai_tools_agent` uses JSON function calls for tool invocation.
Tool calls are **never text tokens**, so the streaming handler only fires for
the final prose response — users see a clean word-by-word stream, not JSON noise.

### 4. Selective CoT — planning queries only

Chain-of-Thought (budget → weather → attractions → visa) is injected only when
the query matches planning keywords (`plan`, `itinerary`, `trip`, `days`, etc.).
Simple factual queries skip CoT entirely — faster and less verbose.

### 5. Full conversation buffer, not summary

Exact `HumanMessage` / `AIMessage` objects are passed on every turn. Travel
conversations are short and detail-sensitive (city names, dates, budgets), so
summarisation would lose critical specifics.

### 6. Natural prose synthesis rule

The system prompt explicitly forbids pasting raw API output. Tool results are
always woven into readable paragraphs — the "Integrate tool results into natural
prose" rule stops the model from producing JSON-like responses.

### 7. Auto-appended hallucination disclaimer

`utils/error_handler.add_hallucination_disclaimer()` appends a booking caveat
whenever the response contains `hotel`, `flight`, `price`, etc. — honest about
LLM limits without disrupting the conversation tone.

### 8. Async parallel tool fetching

`utils/async_tools.run_fetch_all()` uses `asyncio.gather()` + `asyncio.to_thread()`
to fetch weather, country info, and attractions concurrently. Latency is capped
at the slowest single API call (~1.5 s) instead of accumulating per call.
`nest_asyncio` is applied at startup for Streamlit event-loop compatibility.

---

## Sample Conversations

### Weather query (single tool call)

**User:** What's the weather like in Barcelona right now?

**Assistant** *(calls `get_weather("Barcelona")`)*:
Barcelona is enjoying a mild spring — currently 18 °C with light wind. Expect
14–20 °C over the next three days with virtually no rain. Light layers work
during the day; bring a jacket for evenings.

---

### Itinerary planning (CoT + 3 parallel tool calls)

**User:** Plan a 3-day trip to Tokyo on a moderate budget.

**Assistant** *(CoT triggered; `get_weather`, `get_country_info`, `get_attractions` run in parallel)*:

**Before you go**
- Visa: many nationalities get 90-day visa-free entry. Check your government's
  travel advisory for the latest rules.
- Currency: Japanese Yen (¥). 7-Eleven and Japan Post ATMs are foreigner-friendly.
- Weather: 10–17 °C this week, low rain — perfect for walking.

**Day 1 — East Tokyo:** Senso-ji Temple → Akihabara electronics district → ramen dinner.
**Day 2 — Central:** Shinjuku Gyoen garden → Harajuku → Meiji Shrine → budget dinner in Shimokitazawa.
**Day 3 — West:** Shibuya crossing → teamLab digital art (book ahead) → Odaiba waterfront.

> ⚠️ Please verify bookings independently — specific availability and prices may vary.

---

### LLM-only response (no tool call)

**User:** What should I pack for two weeks in Thailand?

**Assistant** (no tool call — answered from knowledge):
Pack light: 5–7 lightweight outfits, 1–2 swimsuits, a sarong (beach cover + temple
visits), sandals, one pair of closed shoes. Essentials: SPF 50+ sunscreen (expensive
locally), DEET repellent, plug adapter (Type A/B), reusable water bottle. A small dry
bag is worth it for boat trips.

---

### Error recovery

**User:** What's the weather in Blorfington?

**Assistant** *(`get_weather` returns "Could not find location")*:
I couldn't find "Blorfington" in the weather database — could you double-check
the spelling? Did you mean **Burlington** or **Bloomington**?

---

### Multi-turn context retention

**User:** I'm planning a trip to Portugal next month.

**Assistant:** Portugal in May is wonderful — warm, sunny, and less crowded than
peak summer. Are you thinking Lisbon, Porto, the Algarve coast, or a mix?

**User:** Lisbon. What should I know about the country?

**Assistant** *(calls `get_country_info("Portugal")`)*:
- Capital: Lisbon | Region: Southern Europe
- Currency: Euro (€) — widely accepted
- Language: Portuguese — "Obrigado!" goes a long way
- Visa: Schengen area — EU/EEA citizens free; others check Schengen rules

**User:** What are the top things to see there?

**Assistant** *(calls `get_attractions("Lisbon")` — knows context is Lisbon from memory)*:
1. Castelo de São Jorge — hilltop Moorish castle with panoramic views
2. Belém Tower — iconic 16th-century riverside landmark
3. Jerónimos Monastery — Manueline architecture, UNESCO site
4. LX Factory — creative market hub in a converted factory
5. Alfama district — historic Moorish quarter, best explored on foot

---

### Off-topic deflection

**User:** What's the best programming language for AI?

**Assistant** *(scope check fails — not travel)*:
I'm a travel assistant — I can help with destinations, weather, packing, or trip
planning. Is there something travel-related I can help with?

---

### Honest "I don't know"

**User:** How much does a return flight from Tel Aviv to Paris cost?

**Assistant** *(no tool call — pricing is outside scope)*:
I don't have current information on flight prices. For up-to-date fares check
**Google Flights**, **Kayak**, or **Skyscanner** — prices change daily and depend
heavily on travel dates and booking lead time.

---

## Edge Cases & LLM Limitations

| Scenario | Behaviour |
|---|---|
| City not found by weather / attractions API | Tool returns clear error string; LLM relays it honestly and asks for clarification |
| API timeout | Tool catches `requests.Timeout` and returns a graceful fallback message |
| Input > 800 characters | Rejected before reaching LLM; UI shows a warning |
| Off-topic query (non-travel) | STEP 1 scope check triggers a polite redirect |
| Request for real-time prices / flights | Honesty rule fires; LLM names the right source |
| Request for visa processing times | Directed to official embassy website |
| Medical / vaccination query | Directed to CDC or WHO |
| Recent safety events / travel advisories | Directed to travel.state.gov or foreign ministry |
| LLM agent loop / max iterations exceeded | `max_iterations=3` + `handle_parsing_errors=True` prevents runaway loops |
| Response mentions hotel / flight / price | `add_hallucination_disclaimer()` appends a booking caveat automatically |
| Model API key missing | `ChatOpenAI` raises `AuthenticationError`; caught in `TravelAgent.run()` and shown as user-friendly message |
