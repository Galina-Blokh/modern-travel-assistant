from langchain_core.messages import HumanMessage, AIMessage


class ConversationHistory:
    """Lightweight conversation history manager for the travel agent."""

    def __init__(self):
        self.messages: list = []

    def add_user(self, content: str) -> None:
        self.messages.append(HumanMessage(content=content))

    def add_assistant(self, content: str) -> None:
        self.messages.append(AIMessage(content=content))

    def clear(self) -> None:
        self.messages = []

    def get(self) -> list:
        return self.messages
