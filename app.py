import nest_asyncio
nest_asyncio.apply()

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.agent import TravelAgent, MODEL_OPTIONS

st.set_page_config(page_title="Travel Assistant", page_icon="✈️", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("✈️ Travel Assistant")
    st.markdown("Powered by LangChain + DeepSeek/Ollama")
    st.markdown("---")

    model_label = st.selectbox(
        "LLM Model",
        options=list(MODEL_OPTIONS.keys()),
        index=0,
        help="deepseek-chat needs DEEPSEEK_API_KEY. Ollama models run locally for free.",
    )
    model = MODEL_OPTIONS[model_label]

    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state.pop("agent", None)
        st.session_state.pop("messages", None)
        st.rerun()

    st.markdown("---")
    st.markdown("**Data APIs (all free):**")
    st.markdown("- Open-Meteo — weather")
    st.markdown("- RestCountries — country facts")
    st.markdown("- OpenTripMap — attractions")

    st.markdown("---")
    st.markdown("**Try asking:**")
    example_queries = [
        "What's the weather in Tokyo?",
        "Do I need a visa for Japan?",
        "What should I visit in Lisbon?",
        "Plan a 3-day trip to Rome on a budget",
        "What to pack for a beach holiday in Thailand?",
    ]
    for q in example_queries:
        st.markdown(f"- *{q}*")

# ── Session state init ────────────────────────────────────────────────────────
if "agent" not in st.session_state or st.session_state.get("model") != model:
    st.session_state.agent = TravelAgent(model=model)
    st.session_state.model = model
    st.session_state.messages = []

# ── Chat header ───────────────────────────────────────────────────────────────
st.title("✈️ Modern Travel Assistant")
st.caption("Ask me about destinations, weather, packing, attractions, or trip planning.")

# ── Display chat history ──────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("steps"):
            with st.expander("🔍 Tool calls", expanded=False):
                for action, observation in msg["steps"]:
                    st.markdown(f"**Tool:** `{action.tool}` &nbsp;|&nbsp; **Input:** `{action.tool_input}`")
                    st.code(observation, language="text")

# ── Chat input ────────────────────────────────────────────────────────────────
if user_input := st.chat_input("Ask me about travel..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if len(user_input) > 800:
        st.warning(
            f"Message too long ({len(user_input)} chars). Please keep it under 800 characters.",
            icon="⚠️",
        )
    else:
        with st.chat_message("assistant"):
            stream_placeholder = st.empty()
            # Show "Thinking…" while tool calls run (before first streaming token)
            stream_placeholder.markdown("_Thinking…_")

            response, steps = st.session_state.agent.run(
                user_input, stream_container=stream_placeholder
            )
            # Remove streaming cursor — show final text cleanly
            stream_placeholder.markdown(response)

            if steps:
                with st.expander("🔍 Tool calls", expanded=False):
                    for action, observation in steps:
                        st.markdown(
                            f"**Tool:** `{action.tool}` &nbsp;|&nbsp; "
                            f"**Input:** `{action.tool_input}`"
                        )
                        st.code(observation, language="text")

            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "steps": steps,
            })
