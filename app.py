import asyncio
import os
import re
import time
import warnings

# Reject oversized input before it hits the model (cost / abuse). Override in .env.
MAX_USER_INPUT_CHARS = int(os.getenv("MAX_USER_INPUT_CHARS", "4000"))
# How many recent HumanMessage/AIMessage pairs (each counts as one) to send to the LLM.
# Full history still shows in the UI; older turns are dropped from model context only.
# Set to 0 for unlimited (entire session_state list — can hit context limits on long chats).
MAX_LLM_CONTEXT_MESSAGES = int(os.getenv("MAX_LLM_CONTEXT_MESSAGES", "40"))

try:
    from bs4 import GuessedAtParserWarning
except ImportError:
    GuessedAtParserWarning = None

# PyPI `wikipedia` calls BeautifulSoup(html) without `features=`; warning is raised from bs4.
if GuessedAtParserWarning is not None:
    warnings.filterwarnings("ignore", category=GuessedAtParserWarning)

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from agent import create_agent

# Groq / OpenAI-compatible streams sometimes echo tool calls as JSON in `content`; strip before UI/history.
_TOOL_JSON_START = re.compile(r'\{\s*\"type\"\s*:\s*\"function\"', re.IGNORECASE)


def _strip_leaked_tool_json(text: str) -> str:
    """Remove {... "type": "function" ...} blobs (possibly nested) from model text."""
    s = text
    while True:
        m = _TOOL_JSON_START.search(s)
        if not m:
            break
        start = m.start()
        depth = 0
        i = start
        while i < len(s):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    s = s[:start] + s[i + 1 :]
                    break
            i += 1
        else:
            s = s[:start] + s[start + 1 :]
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _chunk_to_str(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            bt = block.get("type")
            if bt in ("tool_use", "function", "tool_call"):
                continue
            if bt == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def _extract_text_content(message):
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return str(content)


def _messages_for_llm(full_messages):
    """Return the tail of chat history sent to the agent; UI keeps full_messages."""
    if not full_messages:
        return full_messages
    cap = MAX_LLM_CONTEXT_MESSAGES
    if cap <= 0 or len(full_messages) <= cap:
        return list(full_messages)
    return list(full_messages[-cap:])


def _is_recoverable_with_fallback_model(error: BaseException) -> bool:
    """Primary failed in a way where trying FALLBACK_* may help (connectivity, 429, rate caps)."""
    status = getattr(error, "status_code", None)
    if status == 429:
        return True
    cause = getattr(error, "__cause__", None)
    if cause is not None and getattr(cause, "status_code", None) == 429:
        return True

    text = str(error).lower()
    if "connection error" in text or "failed to connect" in text or "connection refused" in text:
        return True
    if "429" in text:
        return True
    if "rate_limit" in text or "rate limit" in text:
        return True
    if "rate_limit_exceeded" in text:
        return True
    # Groq TPD / token daily caps often include these phrases
    if "tokens per day" in text or "tpd" in text:
        return True
    return False


def _format_error(error):
    error_text = str(error)
    lowered = error_text.lower()
    if "connection error" in lowered or "failed to connect" in lowered or "connection refused" in lowered:
        return (
            "Could not reach the configured model provider. "
            "The app can retry with a fallback model if one is configured. "
            "If you are using hosted providers, verify the primary and fallback API settings in `.env`."
        )
    if (
        "429" in lowered
        or "rate_limit" in lowered
        or "rate limit" in lowered
        or "rate_limit_exceeded" in lowered
        or "tokens per day" in lowered
    ):
        return (
            "The model provider returned a **rate limit** (requests per minute or daily token cap). "
            "Wait and try again, configure a **FALLBACK_*** model in `.env` (often a smaller model), "
            "or review limits and billing on your provider dashboard (e.g. Groq console)."
        )
    return f"An error occurred: {error_text}"


async def _stream_agent_response(agent, messages, response_placeholder, status_placeholder=None):
    """
    Streams model text only. Tool-call JSON leaked into content is stripped before display/history.
    """
    full_text = ""
    start_time = time.perf_counter()
    input_tokens = sum(len(str(m.content).split()) for m in messages)
    output_tokens = 0

    try:
        async for event in agent.astream_events({"messages": messages}, version="v2"):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                content = getattr(chunk, "content", None) if chunk is not None else None
                piece = _chunk_to_str(content)
                if piece:
                    full_text += piece
                    output_tokens += 1
                    clean = _strip_leaked_tool_json(full_text)
                    response_placeholder.markdown(clean + "▌")

            elif kind == "on_tool_start" and status_placeholder is not None:
                status_placeholder.caption("Fetching live data (this can take a few seconds)…")

        if status_placeholder is not None:
            status_placeholder.empty()

        raw_streamed = full_text
        full_text = _strip_leaked_tool_json(full_text)
        sanitized_tool_json = _TOOL_JSON_START.search(raw_streamed) is not None
        empty_output_fallback = not full_text.strip()
        if empty_output_fallback:
            full_text = (
                "I checked live data for that, but nothing readable came through. "
                "Please ask again in one short sentence (e.g. the city name)."
            )
        response_placeholder.markdown(full_text)

        latency = max(0.0, time.perf_counter() - start_time)
        metrics = {
            "latency": round(latency, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "sanitized_tool_json": sanitized_tool_json,
            "empty_output_fallback": empty_output_fallback,
        }
        return full_text, metrics

    except Exception:
        final_state = await agent.ainvoke({"messages": messages})
        final_message = final_state["messages"][-1]
        raw_invoke = _extract_text_content(final_message)
        latest_text = _strip_leaked_tool_json(raw_invoke)
        sanitized_tool_json = _TOOL_JSON_START.search(raw_invoke) is not None
        empty_output_fallback = not latest_text.strip()
        if empty_output_fallback:
            latest_text = (
                "I checked live data for that, but nothing readable came through. "
                "Please ask again in one short sentence (e.g. the city name)."
            )
        response_placeholder.markdown(latest_text)

        latency = max(0.0, time.perf_counter() - start_time)
        metrics = {
            "latency": round(latency, 2),
            "input_tokens": input_tokens,
            "output_tokens": len(latest_text.split()),
            "sanitized_tool_json": sanitized_tool_json,
            "empty_output_fallback": empty_output_fallback,
        }
        return latest_text, metrics


def _run_agent_with_fallback(messages, response_placeholder, status_placeholder):
    try:
        try:
            agent = get_agent(use_fallback=False)
            return asyncio.run(
                _stream_agent_response(
                    agent, messages, response_placeholder, status_placeholder
                )
            )
        except Exception as primary_error:
            if _is_recoverable_with_fallback_model(primary_error):
                try:
                    fallback_agent = get_agent(use_fallback=True)
                except Exception:
                    raise primary_error from None
                response_placeholder.markdown(
                    "_Primary model unavailable or rate-limited. Switching to fallback model…_"
                )
                return asyncio.run(
                    _stream_agent_response(
                        fallback_agent,
                        messages,
                        response_placeholder,
                        status_placeholder,
                    )
                )
            raise
    except Exception as e:
        error_msg = _format_error(e)
        response_placeholder.error(error_msg)
        return error_msg, None


@st.cache_resource(show_spinner=False)
def get_agent(use_fallback: bool = False):
    return create_agent(use_fallback=use_fallback)


st.set_page_config(
    page_title="Travel Assistant",
    page_icon="🌍",
    layout="centered",
)

st.title("🌍 AI Travel Assistant")
st.markdown(
    "I can help you plan your trip, give you weather updates, facts about countries, "
    "and find local attractions! I use real-time data to give you the best advice."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "_chat_input_error" in st.session_state:
    st.warning(st.session_state.pop("_chat_input_error"))

msgs = st.session_state.messages

# Full history first (after a submit + rerun, the new user line appears here before the model runs).
for message in msgs:
    role = "user" if isinstance(message, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(message.content)
        if role == "assistant" and getattr(message, "metrics", None):
            m = message.metrics
            extra = []
            if m.get("sanitized_tool_json"):
                extra.append("tool JSON stripped")
            if m.get("empty_output_fallback"):
                extra.append("empty→fallback")
            if m.get("context_trimmed"):
                extra.append("older msgs omitted from model context")
            tail = f" | {'; '.join(extra)}" if extra else ""
            st.caption(
                f"⏱️ {m['latency']}s | 📝 In: ~{m['input_tokens']} tokens | "
                f"Out: ~{m['output_tokens']} tokens{tail}"
            )

# Pending reply: last message is user-only — run agent, append assistant, rerun (next pass is cheap).
if msgs and isinstance(msgs[-1], HumanMessage):
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        status_placeholder = st.empty()
        metrics_placeholder = st.empty()

        try:
            context_msgs = _messages_for_llm(msgs)
            with st.spinner("Working on your reply…"):
                result = _run_agent_with_fallback(
                    context_msgs, response_placeholder, status_placeholder
                )
            response_content, metrics = result

            if metrics is not None:
                metrics = dict(metrics)
                if len(context_msgs) < len(msgs):
                    metrics["context_trimmed"] = True
                extra = []
                if metrics.get("sanitized_tool_json"):
                    extra.append("tool JSON stripped")
                if metrics.get("empty_output_fallback"):
                    extra.append("empty→fallback")
                if metrics.get("context_trimmed"):
                    extra.append("older msgs omitted from model context")
                tail = f" | {'; '.join(extra)}" if extra else ""
                metrics_placeholder.caption(
                    f"⏱️ {metrics['latency']}s | 📝 In: ~{metrics['input_tokens']} tokens | "
                    f"Out: ~{metrics['output_tokens']} tokens{tail}"
                )
                ai_message = AIMessage(content=response_content)
                ai_message.metrics = metrics
                st.session_state.messages.append(ai_message)
            else:
                st.session_state.messages.append(AIMessage(content=response_content))

        except Exception as e:
            error_msg = _format_error(e)
            response_placeholder.error(error_msg)
            st.session_state.messages.append(AIMessage(content=error_msg))

    st.rerun()

# Input at bottom (correct chat layout). Quick rerun after submit so history paints before the LLM blocks.
if prompt := st.chat_input("Where would you like to travel?"):
    text = prompt.strip()
    if not text:
        st.rerun()
    if len(text) > MAX_USER_INPUT_CHARS:
        st.session_state["_chat_input_error"] = (
            f"Message too long ({len(text)} characters). "
            f"Maximum is {MAX_USER_INPUT_CHARS} (set MAX_USER_INPUT_CHARS in `.env` to change)."
        )
    else:
        st.session_state.messages.append(HumanMessage(content=text))
    st.rerun()
