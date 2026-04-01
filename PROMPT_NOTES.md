# Brief notes on key prompt engineering decisions

This file is for **reviewers**: it explains *why* the system prompt is shaped the way it is. The implementation lives in **`agent/prompts.py`** (`SYSTEM_PROMPT`). The focus here is **effective LLM conversations**, not backend complexity.

---

## 1. Silent chain of thought (CoT) — when and why

**Decision:** Use a **five-step internal chain** (goal → who/constraints → which data → synthesis → shape reply) only for **planning-style** turns: itineraries, multi-day trips, budget, family/kids, comparing places, broad “what should we do” questions.

**Why:** Those questions need **structured decomposition** before tool use and before advice. Showing numbered reasoning to the user would feel robotic and waste tokens.

**Counter-decision:** For **simple** turns (one city’s weather, one country fact, one attraction ask), the prompt says to **skip** the full CoT and answer after a quick “do I need a lookup?” check—so the assistant stays **fast** and **proportionate**.

---

## 2. Concise, relevant answers

**Decision:** Default **~150 words**, **direct answer first**, at most **one** short add-on, prefer short paragraphs or **≤7 bullet items**, no repeated facts in the same message.

**Why:** Travel questions often invite rambling; tight defaults keep answers **scannable** and **useful in chat**. Users can still ask for depth explicitly (“full itinerary”, “explain in detail”).

**Pairing with code:** **`MAX_OUTPUT_TOKENS`** in the chat model is a **hard ceiling**; the prompt is the **soft** target. Together they reduce wall-of-text and cost.

---

## 3. Voice and continuity

**Decision:** Warm, direct, **no** stock openers (“Certainly!”, “Great question!”). **One** clarifying question when something is vague—not a questionnaire. **Match length** to the user (short question → short answer first). On follow-ups, **tie back** to the thread (“For London with kids…”).

**Why:** Improves **coherence** across turns (rubric: “maintains coherent, helpful conversations”) without needing extra memory beyond normal chat history.

---

## 4. When to use tools vs. internal knowledge

**Decision (prompt):** Use live lookups only when **current or structured** facts matter (weather, country facts, city visitor context). Use **knowledge only** for packing tips, opinions, general travel advice when no live field is required.

**Decision (architecture):** **No** `if user said X then call Y` in application code. The **LLM** chooses tools inside a **ReAct** loop; the prompt **steers** that choice.

**Why:** Demonstrates **autonomous** tool use while keeping **clear policy** so the model does not call APIs for every message.

**Composite tool alignment:** When **city and country** are known and several data types help, the prompt nudges **one combined** parallel lookup (`get_destination_snapshot`) to reduce latency and repeated reasoning rounds.

---

## 5. Blending external data with the model

**Decision:** After tools run, **summarize in natural language** only—no raw JSON, no API dumps, no mention of “tools” or “functions.”

**Why:** Users want **advice**, not telemetry. This also reduces **leaked tool syntax** in the visible reply (the UI still sanitizes provider quirks).

---

## 6. Weather: avoiding wrong-but-confident answers

**Decision:** Require an **explicit place** (or a place **clearly** established in recent turns). If the user asks for weather **without** a location, **do not** guess a city (e.g. London) and **do not** call weather—ask **which city** in one short sentence.

**Why:** Models often **hallucinate a default location**; live APIs then return **real** numbers for the wrong place, which looks authoritative but is **wrong**. This rule targets that failure mode directly.

---

## 7. Honesty and “hallucination” mitigation (conversation layer)

**Decision:** Do not invent **live** weather, **visa outcomes**, or **prices**; if unsure, say so and point to **official** or trusted sources.

**Why:** Aligns the assistant with **trustworthy** travel help. Tool failures return **plain-language errors** so the model can **acknowledge** limits instead of fabricating.

---

## 8. Temperature and style

**Decision:** Model **`temperature=0.0`** in code for more **consistent** routing and factual summarization.

**Why:** Travel Q&A benefits from **stability** over creative variance; creativity is steered by **prompt** (tone, structure) rather than high randomness.

---

## Summary

| Goal | Main lever |
|------|------------|
| Multi-step reasoning for hard questions | Silent CoT, scoped to planning-style queries |
| Brevity and relevance | Length block + `max_tokens` |
| Tool vs. knowledge | Explicit *Data* rules + ReAct (model decides) |
| Trust and edge cases | Weather location rule, honesty block, tool error strings |
| Coherent threads | Follow-up tie-ins, one clarifying question |

For **setup and architecture**, see **`README.md`** and **`spec.md`**.
