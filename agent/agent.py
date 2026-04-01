import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

load_dotenv()

# Caps reply length for concise UX; override in .env, e.g. MAX_OUTPUT_TOKENS=1200
_MAX_OUT = int(os.getenv("MAX_OUTPUT_TOKENS", "768"))

from tools import (
    get_weather,
    get_country_info,
    get_attractions,
    get_destination_snapshot,
)
from .prompts import SYSTEM_PROMPT


def _build_model(config_prefix: str):
    base_url = os.getenv(f"{config_prefix}_API_BASE")
    api_key = os.getenv(f"{config_prefix}_API_KEY")
    model_name = os.getenv(f"{config_prefix}_MODEL")

    if not base_url:
        if config_prefix == "PRIMARY":
            base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OLLAMA_BASE_URL")
            if base_url:
                model_name = model_name or os.getenv("OPENAI_MODEL_NAME", "llama3.1:8b")
                api_key = api_key or os.getenv("OPENAI_API_KEY", "not-needed-for-local")
            else:
                model_name = model_name or os.getenv("OPENAI_MODEL_NAME", "llama-3.3-70b-versatile")
                api_key = api_key or os.getenv("OPENAI_API_KEY")
        else:
            return None

    if not model_name:
        raise ValueError(f"Missing {config_prefix}_MODEL configuration.")

    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        raise ValueError(f"Missing {config_prefix}_API_KEY configuration.")

    # Use native Groq client if connecting to Groq for proper tool calling support
    if "groq.com" in base_url:
        return ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=0.0,
            max_tokens=_MAX_OUT,
            max_retries=2,
        )

    return ChatOpenAI(
        model=model_name,
        api_key=api_key or "not-needed-for-local",
        base_url=base_url,
        temperature=0.0,
        max_tokens=_MAX_OUT,
        max_retries=2,
    )


def create_agent(use_fallback: bool = False):
    """
    Initializes the agent using LangGraph's prebuilt react agent.
    This handles the parallel tool calling and CoT logic internally.
    """
    
    llm = _build_model("FALLBACK" if use_fallback else "PRIMARY")
    if llm is None:
        raise ValueError("Fallback model is not configured.")

    tools = [
        get_destination_snapshot,
        get_weather,
        get_country_info,
        get_attractions,
    ]
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT
    )
    
    return agent
