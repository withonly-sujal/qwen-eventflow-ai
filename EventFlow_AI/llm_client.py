"""
EventFlow_AI/llm_client.py
---------------------------
Local LLM interface and Persona Engine.

Connects to your locally-running Ollama instance using the OpenAI-compatible
API. No data ever leaves your machine.
"""

from openai import AsyncOpenAI

from . import config

# ── Ollama client (100% local) ─────────────────────────────────────────────
client = AsyncOpenAI(
    base_url=config.OLLAMA_BASE_URL,
    api_key="ollama",               # Ollama ignores this value, but SDK requires it
)

# ── System Prompts ─────────────────────────────────────────────────────────
_BASE_PROMPT = """You are EventFlow AI, an expert assistant for the Solace Event Portal.
You help users understand their Event-Driven Architecture.

You have access to "Smart Tools" that automatically navigate the complex Solace API for you.
Always follow this logic:
1. If you need to list entities of a certain type or find an entity by name, use `search_solace_entity`.
2. If you need to find what an entity contains, produces, or consumes, use `get_entity_relationships` with its ID.

When answering, always be concise and structured. Use bullet points.
Never fabricate data — only report what the tools return."""

SYSTEM_PROMPTS = {
    "admin": _BASE_PROMPT + """

You are operating in ADMIN mode.
You are fully capable of mutating state. Use `create_solace_entity` to create new domains, apps, and events.
If you need to create a new version of an existing entity, use `create_solace_entity_version`.

CRITICAL: Do NOT use runtime broker tools (like `manage_solace_queue`) unless the user explicitly mentions queues, topic subscriptions, or the runtime event broker. Event Portal entities (Events, Event APIs, etc.) are design-time constructs and do not require physical queue verification!""",

    "end_user": _BASE_PROMPT + """

You are operating in END USER (Read-Only) mode.""",
}


# ── LLM call helpers ───────────────────────────────────────────────────────
async def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
) -> object:
    """
    Send a conversation to the local Qwen model and return the raw response.
    """
    kwargs = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    response = await client.chat.completions.create(**kwargs)
    return response


def mcp_to_openai_tool(tool: dict) -> dict:
    """Convert a generalized tool definition to OpenAI format."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
        },
    }
