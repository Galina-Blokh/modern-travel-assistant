# Travel Assistant — 3 Architectural Solutions

Three production-ready architectural options for the travel assistant home assignment, all using Python + Streamlit + DeepSeek/Ollama, ordered from lowest to highest complexity.

---

## Option 1 — Agentic Tools (Function Calling / MCP-Ready)

**Core idea:** LLM acts as a reasoning engine that decides when to invoke external tools vs. answer from its own knowledge.

**Stack:** `Streamlit` · `LangChain` · `DeepSeek` (or `Ollama`) · `Open-Meteo API` · `RestCountries API`

**How it works:**
- Register tools: `get_weather(city)`, `get_country_info(country)`, `get_attractions(city)`
- LLM is given tool definitions in the system prompt; it emits a tool-call JSON when external data is needed
- Results are injected back into the conversation context before final response

**Assignment checklist:**
- ✅ 3+ query types via distinct tools
- ✅ Context: LangChain `ConversationBufferMemory`
- ✅ CoT system prompt: "Think step-by-step: budget → season → interests → output advice"
- ✅ Decision method: LLM chooses tool vs. internal knowledge autonomously
- ✅ External APIs: weather + country facts

**Complexity:** Low | **Best for:** Flexible real-time queries

---

## Option 2 — Stateful Graph (LangGraph)

**Core idea:** Conversation follows an explicit directed graph; each node is a reasoning step, enabling true chain-of-thought and error correction loops.

**Stack:** `Streamlit` · `LangGraph` · `DeepSeek` · `Tavily Search API` · `Open-Meteo API`

**Graph nodes:**
```
[Intent Classifier] → [Data Fetcher] → [Chain-of-Thought Reasoner] → [Quality Validator] → [Response Formatter]
                                                                          ↑_______[Retry if hallucination]______|
```

**How it works:**
- `Intent Classifier`: routes query to correct data-fetch path
- `Chain-of-Thought Reasoner`: structured multi-step prompt (budget → weather → attractions → itinerary)
- `Quality Validator`: checks for hallucinated hotel/flight names, loops back if detected
- State persisted across turns via LangGraph `StateGraph`

**Assignment checklist:**
- ✅ CoT: explicit reasoning node
- ✅ Error handling: validation node catches and retries hallucinations
- ✅ Context: persistent graph state across full session
- ✅ External APIs: Tavily for live search + weather

**Complexity:** High | **Best for:** Detailed multi-day itinerary planning

---

## Option 3 — Hybrid RAG + Router

**Core idea:** Fast intent router classifies each query, then either retrieves from a local knowledge base (RAG) or calls a live API, minimizing token usage and maximizing accuracy.

**Stack:** `Streamlit` · `ChromaDB` · `DeepSeek` · `Open-Meteo API` · `sentence-transformers`

**How it works:**
1. **Router prompt** classifies intent: `PACKING` | `DESTINATION` | `WEATHER` | `ATTRACTIONS` | `ITINERARY`
2. **RAG** (ChromaDB): retrieves visa rules, local customs, packing guides from a curated local text corpus
3. **API layer**: fetches real-time weather for `WEATHER` intents
4. **Synthesis prompt**: blends RAG context + API data + conversation history into final response

**Assignment checklist:**
- ✅ 3+ query types: each router class maps to a different pipeline
- ✅ Decision method: explicit router separates static vs. dynamic data
- ✅ CoT: synthesis prompt uses step-by-step blending instruction
- ✅ Concise responses: router prevents irrelevant context from being sent to LLM

**Complexity:** Medium | **Best for:** General travel FAQ with fast, accurate answers

---

## Comparison

| Feature              | Option 1 · Agentic Tools | Option 2 · LangGraph | Option 3 · RAG + Router |
|----------------------|:------------------------:|:--------------------:|:-----------------------:|
| Complexity           | Low                      | High                 | Medium                  |
| Context handling     | Buffer memory            | Persistent state     | Intent-scoped           |
| Chain of Thought     | System prompt            | Dedicated node       | Synthesis prompt        |
| Error handling       | Basic retry              | Validation loop      | Router prevents noise   |
| External data        | Live APIs                | Live search + API    | RAG + live API          |
| Best for             | Real-time queries        | Itinerary planning   | FAQ / general travel    |

---

## Recommendation

**Option 1** is the best fit for the assignment's stated priority of _conversation quality over complex systems_ — low overhead, still hits every requirement, easy to demo with transcripts.

**Option 2** is ideal if you want to showcase advanced prompt engineering and error-handling depth.

**Option 3** is a strong middle ground if offline/fast responses matter.
