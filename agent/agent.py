import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.callbacks import BaseCallbackHandler
from agent.memory import ConversationHistory
from agent.prompts import build_prompt
from tools.weather import get_weather
from tools.country import get_country_info
from tools.attractions import get_attractions
from utils.error_handler import add_hallucination_disclaimer

TOOLS = [get_weather, get_country_info, get_attractions]

_MAX_INPUT = 800  # chars — keep prompts within context budget


def _validate(text: str) -> str | None:
    """Return an error string if the input should be rejected, else None."""
    text = text.strip()
    if not text:
        return "Please type a message."
    if len(text) > _MAX_INPUT:
        return (
            f"Your message is {len(text)} characters — please shorten it to "
            f"under {_MAX_INPUT} characters so I can respond accurately."
        )
    return None


MODEL_OPTIONS = {
    "deepseek-chat (API)": "deepseek",
    "deepseek-r1:7b (Ollama, free)": "deepseek-r1",
    "llama3 (Ollama, free)": "ollama",
}


class _StreamHandler(BaseCallbackHandler):
    """Streams LLM tokens into a Streamlit placeholder in real-time."""

    def __init__(self, container):
        self.container = container
        self.text = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.text += token
        self.container.markdown(self.text + "▌")


def _get_llm(model: str, streaming: bool = False, callbacks: list | None = None) -> ChatOpenAI:
    kwargs = dict(temperature=0.7, streaming=streaming, callbacks=callbacks or [])
    if model == "deepseek":
        return ChatOpenAI(
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
            **kwargs,
        )
    if model == "deepseek-r1":
        return ChatOpenAI(
            model="deepseek-r1:7b",
            api_key="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            **kwargs,
        )
    return ChatOpenAI(
        model="llama3",
        api_key="ollama",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        **kwargs,
    )


class TravelAgent:
    """Conversational travel agent with tool calling, streaming, and persistent memory."""

    def __init__(self, model: str = "deepseek"):
        self.model = model
        self.memory = ConversationHistory()

    def run(self, user_input: str, stream_container=None) -> tuple[str, list]:
        """
        Run one turn of the conversation.

        Args:
            user_input: The user's message.
            stream_container: Optional st.empty() placeholder for token streaming.

        Returns:
            (response_text, intermediate_steps)
        """
        user_input = user_input.strip()
        validation_error = _validate(user_input)
        if validation_error:
            return validation_error, []

        callbacks = [_StreamHandler(stream_container)] if stream_container is not None else []
        llm = _get_llm(self.model, streaming=stream_container is not None, callbacks=callbacks)

        prompt = build_prompt(user_input)
        agent = create_openai_tools_agent(llm=llm, tools=TOOLS, prompt=prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=TOOLS,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3,
            return_intermediate_steps=True,
        )

        try:
            result = executor.invoke({
                "input": user_input,
                "chat_history": self.memory.get(),
            })
        except Exception as exc:
            err = (
                f"I ran into a technical problem and couldn't complete that request. "
                f"({type(exc).__name__}: {exc}) — please try again or rephrase your question."
            )
            return err, []

        response = result["output"]
        steps = result.get("intermediate_steps", [])

        self.memory.add_user(user_input)
        self.memory.add_assistant(response)

        return add_hallucination_disclaimer(response), steps

    def reset(self) -> None:
        self.memory.clear()
