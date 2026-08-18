"""
LangGraph Agent Service.
Creates a ReAct agent with ChatGroq, conversation memory,
and a shared Bitrix24 client for all tools.
"""

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from config import GROQ_API_KEY, DEFAULT_MODEL, AVAILABLE_MODELS
from prompt import SYSTEM_PROMPT
from services.bitrix24_client import Bitrix24Client


#  Shared client : single instance for all tools
client = Bitrix24Client()


#  Import all tools (they use the shared client above)

from tools.create_task import create_task
from tools.list_tasks import list_tasks, list_overdue_tasks
from tools.search_tasks import search_tasks
from tools.update_task import update_task
from tools.delete_task import delete_task
from tools.find_user import find_user

ALL_TOOLS = [
    create_task,
    list_tasks,
    list_overdue_tasks,
    search_tasks,
    update_task,
    delete_task,
    find_user,
]


class TaskAgent:
    "Conversational Bitrix24 agent built with LangGraph, Groq, and Memory."
    def __init__(self, model: str = None):
        self.client = client  # Shared client reference
        self.model = model or DEFAULT_MODEL
        self.memory = MemorySaver()
        self._build_agent()

    def _build_agent(self):
        "Build  the LangGraph ReAct agent with memory."
        llm = ChatGroq(
            model=self.model,
            api_key=GROQ_API_KEY,
            temperature=0.0,
        )
        self.agent = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
            prompt=SYSTEM_PROMPT,
            checkpointer=self.memory,
        )

    def set_model(self, model: str):
        "Switch the LLM model and rebuild the agent."
        self.model = model
        self._build_agent()

    def handle(self, message: str, thread_id: str = "default") -> str:
        "Process a user message and return the agent's response."
        try:
            return self._invoke(message, thread_id)

        except Exception as e:
            error_str = str(e)

            # Auto-recover from invalid/corrupt chat history
            if "INVALID_CHAT_HISTORY" in error_str or "ToolMessage" in error_str:
                try:
                    # Clear corrupted thread memory and retry
                    if hasattr(self.memory, 'storage') and thread_id in self.memory.storage:
                        del self.memory.storage[thread_id]
                    return self._invoke(message, thread_id)
                except Exception:
                    pass

            # Handle Groq rate limit errors gracefully
            if "rate_limit" in error_str or "429" in error_str:
                other_models = [
                    m for m in AVAILABLE_MODELS.keys() if m != self.model
                ]
                suggestions = ", ".join(other_models[:2])
                return (
                    f"Rate limit reached for model `{self.model}`.\n"
                    f"Switch to a different model: {suggestions}"
                )

            return f"Agent error: {e}"

    def _invoke(self, message: str, thread_id: str) -> str:
        "Invoke the agent and extract the response."
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        messages = result.get("messages", [])

        # Check if any tool was called
        tool_messages = [
            m for m in messages
            if hasattr(m, "type") and m.type == "tool"
        ]

        # If tools were called, prefer showing the tool result directly
        if tool_messages:
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content and msg.type == "ai":
                    last_tool_content = tool_messages[-1].content
                    if len(msg.content) < len(last_tool_content) // 2:
                        return last_tool_content
                    return msg.content

        # No tools called — return the AI's direct response
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content and msg.type == "ai":
                return msg.content

        return "I couldn't generate a response. Please try again."
