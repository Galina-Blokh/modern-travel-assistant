# Travel Assistant — Agent Implementation Specification

This document is **implementation guidance for an autonomous coding agent** (or a human following the same steps). Treat it as the **source of truth** for what to build, how files should behave, and how to verify correctness. If the codebase diverges, **update either the code or this spec** so they stay aligned.

---

## 0. Mission & definition of done

**Product:** A **Streamlit** web app that behaves like a compact ChatGPT-style travel assistant. The LLM uses **LangGraph’s prebuilt ReAct agent** (`create_react_agent`) with **async tools** that call **real HTTP APIs** (weather, country facts) and **Wikipedia** (city / tourism context). The user sees **streaming** assistant text, optional **“fetching data”** status during tools, and **per-turn metrics** (latency, rough token counts, optional flags).

**Definition of done (agent checklist):**

1. `uv sync` succeeds on Python **≥ 3.12**; app starts with `streamlit run app.py`.
2. With valid **primary** LLM credentials in `.env`, a user can chat; tools run when appropriate; answers are **natural language** (no raw tool JSON in the UI).
3. **Primary** model is used by default; on **connection-class** failures, the app **retries once** with a **fallback** model if configured.
4. **Three** external data integrations exist as specified (Open-Meteo, RESTCountries, Wikipedia), plus an optional **fourth composite tool** that runs three lookups **in parallel** for trip-style questions.
5. Conversation **memory** persists in the browser session; **long threads** do not blindly send unlimited history to the LLM unless configured otherwise.
6. **Input** is validated (trim, empty ignore, max length). **Output** is sanitized when providers leak tool-call JSON into streamed text; **empty** replies after sanitization get a **fallback user message**.
7. `.env.example` lists every environment variable the code reads, with comments. **README** explains setup and behavior at a user-facing level.

### 0.1 Assignment / rubric mapping (travel assistant brief)

Course briefs often require: **CoT prompting**, **concise responses**, **blending API data with knowledge**, **explicit decision logic for tools vs. knowledge**, **error handling**, and **context management**, plus evaluation of **conversation quality**, **prompts**, **edge cases**, and **data blending**.

| Brief theme | Primary implementation |
|-------------|-------------------------|
| Multi-step CoT | `agent/prompts.py` — silent five-step chain for planning-style queries only. |
| Concise / relevant | Same file — length and structure rules; `MAX_OUTPUT_TOKENS` in `agent/agent.py`. |
| Blend external + knowledge | Prompt: summarize tool output in prose; use knowledge when live data unnecessary. |
| When to use external data | ReAct agent + prompt *Data (silent)* and CoT step 3 (which lookups). |
| Errors / confusion / hallucinations | Tool error strings; honesty rules; `app.py` sanitization + empty fallback + model fallback. |
| Conversation context | `st.session_state.messages` + `MAX_LLM_CONTEXT_MESSAGES`; prompt follow-up tie-ins. |

The **README** section *Course rubric alignment* expands this table for human reviewers.

---

## 1. Repository layout (expected tree)

```
modern-travel-assistant/
├── pyproject.toml          # dependencies; requires-python >= 3.12
├── README.md               # human setup, features, env notes
├── .env.example            # template; no real secrets
├── spec.md                 # this file
├── app.py                  # Streamlit UI, streaming, guards, metrics, fallback orchestration
├── test_eval.py            # optional CLI smoke test for agent + tools (not pytest-required)
├── agent/
│   ├── __init__.py         # export create_agent
│   ├── agent.py            # LLM factory + create_react_agent
│   └── prompts.py          # SYSTEM_PROMPT string
└── tools/
    ├── __init__.py         # re-export all tools
    ├── weather.py          # get_weather
    ├── country.py          # get_country_info
    ├── attractions.py      # get_attractions
    └── destination_snapshot.py  # get_destination_snapshot (parallel batch)
```

**Do not** add a PyPI package named `asyncio` — it shadows the standard library and breaks LangGraph.

---

## 2. Dependencies (`pyproject.toml`)

Pin ranges consistent with a working LangGraph 1.x + Streamlit stack, for example:

- `streamlit`, `python-dotenv`, `httpx`
- `langgraph`, `langchain`, `langchain-openai`, `langchain-groq`, `langchain-community`
- `wikipedia` (for attractions; uses network + BeautifulSoup warnings may need filtering in `app.py`)

The agent should run `uv sync` and fix any resolver conflicts by adjusting bounds—not by vendoring fake stdlib modules.

---

## 3. Environment variables (complete contract)

**Loaded via `python-dotenv` in `agent/agent.py` (`load_dotenv()`).** Streamlit inherits the process environment; ensure `.env` is present when running locally.

### 3.1 Primary / fallback LLM (Groq or OpenAI-compatible)

| Variable | Role |
|----------|------|
| `PRIMARY_API_BASE` | Base URL (e.g. `https://api.groq.com/openai/v1` or local `http://localhost:11434/v1`) |
| `PRIMARY_API_KEY` | API key (Groq/hosted); for localhost, code may use a placeholder if documented |
| `PRIMARY_MODEL` | Model id (e.g. `llama-3.3-70b-versatile`) |
| `FALLBACK_API_BASE` | Same shape as primary, for backup model |
| `FALLBACK_API_KEY` | Fallback key |
| `FALLBACK_MODEL` | Smaller/faster model (e.g. `llama-3.1-8b-instant`) |

### 3.2 Ollama shortcut (primary only, when `PRIMARY_API_BASE` unset)

If `PRIMARY_API_BASE` is missing, the factory may fall back to:

| Variable | Role |
|----------|------|
| `OLLAMA_BASE_URL` or `OPENAI_API_BASE` | Local OpenAI-compatible endpoint |
| `OPENAI_MODEL_NAME` | Default model name when using that path |
| `OPENAI_API_KEY` | Placeholder like `not-needed-for-local` when required by client |

**The application does not download Ollama models.** The user (or deployer) must run `ollama pull <model>` separately. Document this in README.

### 3.3 Model behavior tuning

| Variable | Default (if unset) | Purpose |
|----------|-------------------|---------|
| `MAX_OUTPUT_TOKENS` | `768` | Passed to the chat model as `max_tokens` / equivalent |
| `MAX_USER_INPUT_CHARS` | `4000` | Reject user messages longer than this **before** any LLM call |
| `MAX_LLM_CONTEXT_MESSAGES` | `40` | Max **messages** (each Human or AI turn = 1) passed to the agent; `0` = unlimited full history |

### 3.4 Groq-specific branch

When `PRIMARY_API_BASE` (or fallback) contains `groq.com`, use **`ChatGroq`** from `langchain_groq` (better tool-calling support than a generic OpenAI client for Groq). Otherwise use **`ChatOpenAI`** from `langchain_openai` with `base_url` + `api_key`.

Set `temperature=0.0`, `max_retries=2`, and `max_tokens` from `MAX_OUTPUT_TOKENS`.

---

## 4. Agent module (`agent/agent.py`)

**Responsibilities:**

1. **`_build_model(config_prefix: str)`** where `config_prefix` is `"PRIMARY"` or `"FALLBACK"`:
   - Read `*_API_BASE`, `*_API_KEY`, `*_MODEL` from env.
   - If fallback base is missing, return `None` for fallback (caller must handle).
   - Validate: model name required; API key required for non-localhost bases.
   - Return a LangChain chat model instance.

2. **`create_agent(use_fallback: bool = False)`**:
   - Build LLM for primary or fallback; if fallback requested but not configured, raise a clear `ValueError`.
   - Import tools from `tools`: `get_destination_snapshot`, `get_weather`, `get_country_info`, `get_attractions` (order: composite first helps model docs list the batch tool prominently).
   - Import `SYSTEM_PROMPT` from `prompts.py`.
   - Return `create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)` from `langgraph.prebuilt`.

**Export:** `from agent import create_agent` via `agent/__init__.py`.

### 4.1 Agentic behavior and reasoning loops (terminology)

Use this section when reviewers ask whether the app is **agentic** or has a **reasoning loop**.

- **Agentic (tool-using agent):** The LLM **chooses** tool vs internal knowledge and **which** tools and parameters. Routing is **not** implemented as application `if/else` over user text. The prebuilt **ReAct** graph (`create_react_agent`) supplies the multi-step **act–observe** cycle. This is standard single-agent **function-calling** / **agentic** behavior; it is **not** a separate planner service, multi-agent system, or persistent autonomous worker.

- **Reasoning loop (runtime, in the graph):** Each user turn may involve **several** graph steps: generate → **tool calls** → tool messages → generate again → … until the model returns a final answer. That iteration is the **ReAct reasoning loop** (implemented by LangGraph, not by a manual `while` in `app.py`).

- **Reasoning (prompt-level):** `SYSTEM_PROMPT` (see §5) requires **silent chain-of-thought** for planning-class queries. That guides **how** the model thinks **within** a generation; it does **not** add a second programmatic loop.

**README** summarizes the same ideas for readers; **§4–§6** and **§7** are the implementation anchors.

---

## 5. System prompt (`agent/prompts.py`)

**Format:** Single string `SYSTEM_PROMPT` suitable for `create_react_agent(..., prompt=...)`.

**Required themes (behavioral contract):**

1. **User-facing voice:** Warm, concise, no stiff openers; match brevity to the question; at most **one** clarifying question when vague.
2. **Length:** Default ~**150 words** unless user asks for depth; short paragraphs or small bullet lists.
3. **Silent chain-of-thought (CoT):** For **planning-style** queries (itinerary, multi-day, budget, family/kids, comparing places), instruct the model to think **internally** through goal → constraints → which live data → synthesis → reply shape — **never** output numbered “Step 1…” reasoning to the user.
4. **Tool use:** Prefer **one** combined tool when **city + country** are known and multiple data types are needed; otherwise single-purpose tools. Do not name tools, JSON, or APIs in user-visible text.
5. **Honesty:** Do not invent live weather, visas, or prices; on tool failure, acknowledge and use general knowledge where safe.

The reference implementation is prose-heavy and tuned for Groq; an agent may rephrase but **must not** drop the “no tool leakage” or “silent CoT for planning” rules.

---

## 6. Tools package (`tools/`)

**General tool contract:**

- Decorate with `@tool` from `langchain_core.tools`.
- Implement as **`async def`** where I/O is involved.
- Validate string args (non-empty after strip); return **plain-language error strings** on failure so the LLM can respond gracefully—do not raise uncaught exceptions for expected API failures.
- Use **`httpx.AsyncClient`** for HTTP tools (context manager per call or per tool invocation).

### 6.1 `get_weather(city: str)`

- Geocode: `GET https://geocoding-api.open-meteo.com/v1/search` with `name`, `count=1`, `language=en`, `format=json`.
- Forecast: `GET https://api.open-meteo.com/v1/forecast` with `current` fields for temperature, humidity, weather code, wind.
- Return a readable one-line summary; handle missing results and HTTP errors.

### 6.2 `get_country_info(country: str)`

- `GET https://restcountries.com/v3.1/name/{url_encoded_country}`.
- Handle 404 / empty list; format capital, region, population (numeric formatting), languages, currencies.

### 6.3 `get_attractions(city: str)`

- Wikipedia is **synchronous** in the `wikipedia` library; run blocking work with `asyncio.get_running_loop().run_in_executor(None, ...)`.
- Implement **title disambiguation** so generic pages do not dominate: require the article title to **match the city** (substring / word checks); try stable titles like `"{city}"`, `"{city} (city)"`, `Tourism in {city}`, then search.
- Cap summary length (e.g. 2000 chars) to avoid huge tool payloads.

### 6.4 `get_destination_snapshot(city: str, country: str)` (composite)

- **Docstring must** tell the model: use when planning/overview and **both** city and country are known; otherwise use atomic tools.
- Implement with `asyncio.gather(..., return_exceptions=True)` calling the **same** underlying tool logic (`get_weather.ainvoke`, `get_country_info.ainvoke`, `get_attractions.ainvoke` with dict args).
- Format three sections (Weather / Country / Attractions); map exceptions to short section-level error lines.

---

## 7. Streamlit application (`app.py`)

### 7.1 Session state memory

- **`st.session_state.messages`**: list of `HumanMessage` and `AIMessage` from `langchain_core.messages`.
- **Persistence scope:** Per browser session only (lost on refresh unless extended later).
- **Full history** is always rendered in the UI loop over `msgs`.
- **LLM context:** Before calling the agent, compute `context_msgs = _messages_for_llm(msgs)`:
  - If `MAX_LLM_CONTEXT_MESSAGES <= 0`, pass full `msgs`.
  - Else pass **only the last N** messages. This is a **sliding window**, not summarization.

### 7.2 Chat UX pattern (critical)

Streamlit is **rerun-driven**. A robust pattern:

1. Render **all** messages from `session_state`.
2. If the **last** message is a `HumanMessage` (user just added, assistant not yet generated), open an assistant placeholder, **run the agent**, append `AIMessage`, **`st.rerun()`**.
3. **`st.chat_input`** at bottom: on submit, validate input, append `HumanMessage`, **`st.rerun()`** so the next pass draws the user bubble **before** blocking on the LLM.

### 7.3 Streaming

- Use **`agent.astream_events(..., version="v2")`** with `{"messages": context_msgs}`.
- Handle **`on_chat_model_stream`**: extract text from chunks (string or structured list blocks); skip tool-only blocks where possible.
- Handle **`on_tool_start`**: show a small caption like “Fetching live travel data…”, then clear it when done.

### 7.4 Provider quirk: leaked tool JSON in `content`

Some OpenAI-compatible streams echo `{"type": "function", ...}` inside **text content**. Implement **`_strip_leaked_tool_json`** using a regex start marker and brace-depth parsing to remove those blobs from accumulated text before display and before saving to history.

### 7.5 Empty output fallback

After stripping, if the assistant text is empty/whitespace, substitute a **short** helpful message (e.g. ask user to retry in one short sentence).

### 7.6 Metrics (per assistant turn)

Attach to `AIMessage` as **`message.metrics`** (dynamic attribute) a dict including:

- `latency` (seconds, float rounded)
- `input_tokens` — **rough** estimate (e.g. sum of word counts of `str(m.content)` over **`context_msgs`**, not necessarily full UI history)
- `output_tokens` — rough (e.g. stream chunk count or word count after invoke)
- `sanitized_tool_json` — bool if leak pattern was present
- `empty_output_fallback` — bool if empty-after-strip path ran
- `context_trimmed` — bool if `len(context_msgs) < len(msgs)` (optional but recommended)

Show metrics as **`st.caption`** under assistant bubbles.

### 7.7 Primary → fallback orchestration

- Cache agents with **`@st.cache_resource`**: `get_agent(use_fallback=False|True)` → `create_agent(...)`.
- Wrap `asyncio.run(_stream_agent_response(...))` in try/except:
  - On exception, if `_is_recoverable_with_fallback_model` is true (**connection-style** errors, **HTTP 429** / `status_code`, `rate_limit`, `rate_limit_exceeded`, **tokens per day / TPD** in message text), retry once with fallback agent and same `context_msgs`. If fallback config is missing, re-raise the primary error.
  - Other errors: show formatted error via `_format_error`; optionally append assistant message with error text.

**Note:** Org-wide daily caps may still exhaust **both** models; fallback helps when limits are **per-model** or the backup model has headroom. User-facing `_format_error` summarizes 429 / rate-limit cases when fallback is not used or also fails.

### 7.8 Input validation

- `strip()` user input; ignore empty.
- If `len(text) > MAX_USER_INPUT_CHARS`, **do not** call the model; set a **transient** session key (e.g. `st.session_state["_chat_input_error"]`) and `st.warning` on next run.

### 7.9 Optional warnings hygiene

Filter `bs4.GuessedAtParserWarning` if BeautifulSoup warns via the `wikipedia` package.

---

## 8. Security & abuse (minimum bar)

- **Secrets:** Never commit `.env`; only `.env.example` with placeholders.
- **SSRF:** Tools must only call **fixed** public API hostnames; user strings are **query parameters**, not URL bases.
- **Input size:** Enforce `MAX_USER_INPUT_CHARS`.
- **No** claim of full prompt-injection immunity; system prompt instructs behavior but is not a security boundary for hostile users.

---

## 9. Testing & smoke checks

1. **Manual:** Run `uv run streamlit run app.py`; ask for weather, country facts, attractions, and a multi-part trip question that should trigger `get_destination_snapshot` or multiple tools.
2. **`test_eval.py`:** Optional `asyncio.run` script that streams a few fixed queries and prints tool start events—useful for headless checks when API keys exist.

---

## 10. Implementation order (for a greenfield agent)

1. `pyproject.toml` + `uv sync`.
2. `tools/` atomic tools (weather, country, attractions) with async HTTP / executor pattern.
3. `tools/destination_snapshot.py` with `asyncio.gather`.
4. `agent/prompts.py` then `agent/agent.py` + `__init__.py`.
5. `app.py` minimal chat → add streaming → sanitization → metrics → input cap → context window → fallback.
6. `.env.example` + README.
7. Run manual + `test_eval.py` if desired.

---

## 11. Non-goals (out of scope unless explicitly requested)

- User accounts, auth, or multi-tenant persistence.
- Automatic `ollama pull` or model downloads.
- Full ML evaluation harness (judge model, labeled datasets).
- Production-grade rate limiting, PII scanning, or toxicity classifiers.

---

## 12. Maintenance rule

When changing behavior (new env var, new tool, fallback rules, memory strategy), **update this spec in the same change** so future agents can rely on a single document.
