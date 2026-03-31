# Travel Assistant — Architecture Plan & Implementation Status

## Selected Architecture: Option 1 — Agentic Tools ✅ IMPLEMENTED

**Branch:** `agentic-tool-mcp`

**Core idea:** LLM acts as a reasoning engine that autonomously decides when to call
external tools vs. answer from its own knowledge, with real-time streaming output.

---

## Implementation Status

### Stack
- `Streamlit` — chat UI with streaming via `st.empty()` + `_StreamHandler`
- `LangChain 0.2.x` + `create_openai_tools_agent` — function-calling agent
- `DeepSeek-V3` (API) or `deepseek-r1:7b` / `llama3` via Ollama (free local)
- `Open-Meteo` — weather (free, no key)
- `RestCountries` — country facts (free, no key)
- `OpenTripMap` — attractions (free tier, key required)
- `uv` + `Python 3.12`

### Assignment Checklist
- ✅ 3+ query types via distinct tools (`get_weather`, `get_country_info`, `get_attractions`)
- ✅ Context: `ConversationHistory` (HumanMessage / AIMessage) passed per turn
- ✅ Selective CoT: injected on planning/itinerary keywords, silent reasoning
- ✅ Decision method: 3-step decision tree in system prompt (scope → tool → honesty)
- ✅ External APIs: weather + country + attractions
- ✅ Honesty rules: explicit "I don't have that info" for prices, visas, advisories
- ✅ Edge case handling: input validation, tool error messages, off-topic deflection
- ✅ Token streaming: `_StreamHandler` callback, "Thinking…" state during tool calls
- ✅ Async parallel fetch: `utils/async_tools.py` with `asyncio.gather()`

### Key Prompt Engineering Decisions
1. **3-step decision method** in system prompt: scope → tool selection → honesty check
2. **Honesty rules** with specific triggers and suggested alternative sources
3. **Selective CoT** only for planning queries — avoids latency on simple questions
4. **Function-calling agent** (not text REACT) — tool calls are JSON, never pollute stream
5. **Conversation rules** enforce natural prose synthesis, no filler openers, no repetition
6. **Hallucination disclaimer** auto-appended when booking keywords detected

### Files
```
app.py                        Streamlit entry point — streaming UI, model selector
agent/agent.py                TravelAgent, _StreamHandler, input validation
agent/memory.py               ConversationHistory wrapper
agent/prompts.py              System prompt with decision method + CoT variant
tools/weather.py              get_weather → Open-Meteo
tools/country.py              get_country_info → RestCountries
tools/attractions.py          get_attractions → OpenTripMap (LRU cached)
utils/async_tools.py          asyncio.gather() parallel fetcher
utils/error_handler.py        retry decorator + hallucination disclaimer
transcripts/sample_conversations.md
pyproject.toml                uv + Python 3.12
requirements.txt
.env.example
README.md                     Full docs (setup, prompts, samples, edge cases)
spec.md                       Detailed architecture specification
```

---

## Alternative Architectures (not implemented)

### Option 2 — Stateful Graph (LangGraph)
**Stack:** `LangGraph` · `DeepSeek` · `Tavily Search API` · `Open-Meteo`

Graph: `[Intent Classifier] → [Data Fetcher] → [CoT Reasoner] → [Quality Validator] → [Formatter]`
with a retry loop if hallucinations detected.

**When to choose:** Detailed multi-day itinerary planning, advanced error correction.

### Option 3 — Hybrid RAG + Router
**Stack:** `ChromaDB` · `DeepSeek` · `Open-Meteo` · `sentence-transformers`

Router classifies intent (`PACKING | WEATHER | ATTRACTIONS | ITINERARY`), then either
retrieves from a local knowledge base (RAG) or calls a live API.

**When to choose:** General travel FAQ, fast offline-first answers.

---

## Architecture Comparison

| Feature          | Option 1 · Agentic (IMPL.) | Option 2 · LangGraph | Option 3 · RAG + Router |
|------------------|:--------------------------:|:--------------------:|:-----------------------:|
| Complexity       | Low                        | High                 | Medium                  |
| Context          | Buffer per turn            | Persistent state     | Intent-scoped           |
| CoT              | Selective injection        | Dedicated node       | Synthesis prompt        |
| Error handling   | Validation + honesty rules | Validation loop      | Router prevents noise   |
| External data    | Live APIs + streaming      | Live search + API    | RAG + live API          |
| Free model       | Ollama deepseek-r1:7b      | —                    | —                       |
