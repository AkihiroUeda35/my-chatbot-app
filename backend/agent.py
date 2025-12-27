import os
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any, Literal, cast

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlmodel import Field, Session, SQLModel, create_engine, select
from tavily import TavilyClient

from log_setting import getLogger

logger = getLogger()

# Initialize Tavily client for web search
tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))

# SQLite database path for checkpoints
CHECKPOINT_DB_PATH = os.environ.get("CHECKPOINT_DB_PATH", "checkpoints.sqlite")

# DEFAULT_MODEL = "google_genai:gemini-2.5-flash"
DEFAULT_MODEL = "ollama:gpt-oss:120b-cloud"


# SQLModel for thread metadata
class ThreadMetadata(SQLModel, table=True):
    """Thread metadata model."""

    thread_id: str = Field(primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# Create SQLModel engine for thread metadata
_metadata_engine = None


def get_metadata_engine():
    """Get the SQLModel engine for thread metadata (lazy initialization)."""
    global _metadata_engine
    if _metadata_engine is None:
        _metadata_engine = create_engine(f"sqlite:///{CHECKPOINT_DB_PATH}", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(_metadata_engine)
    return _metadata_engine


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> dict:
    """Run a web search using Tavily API.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return.
        topic: Search topic type - "general", "news", or "finance".
        include_raw_content: Whether to include full page content.

    Returns:
        Search results from Tavily.
    """
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


# System prompt for the search agent
SEARCH_AGENT_PROMPT = """You are a helpful search assistant.
Your job is to search the web for information and provide accurate, well-organized answers.

When answering questions:
1. Use the internet_search tool to find relevant information
2. Synthesize the results into a clear, helpful response
3. Cite sources using proper markdown links, e.g., [Source Title](https://example.com)
4. Do NOT use citation formats like 【1†source】 or [1] - always use clickable markdown links
5. If information is uncertain or conflicting, acknowledge this
"""


def create_model(model_name: str = DEFAULT_MODEL):
    """Create a chat model instance.

    Args:
        model_name: The model identifier string.

    Returns:
        A chat model instance.
    """
    if "ollama" in model_name:
        # Set a reasonable HTTP timeout to avoid hanging on non-streaming models
        return init_chat_model(
            model_name,
            temperature=0,
            base_url=os.environ.get("OLLAMA_API_BASE_URL", "http://localhost:11434"),
            timeout=10,
            validate_model_on_init=True,
        )
    return init_chat_model(model_name, temperature=0)


# Singleton to hold the checkpointer instance
_checkpointer = None

# Singleton to hold the agent instance
_agent = None


def get_checkpointer():
    """Get the SQLite checkpointer (lazy initialization).

    Returns:
        SqliteSaver: The SQLite checkpointer instance.
    """
    global _checkpointer
    if _checkpointer is None:
        import sqlite3

        conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
    return _checkpointer


def get_search_agent(checkpointer=None):
    """Get the search agent with optional checkpointer.

    Args:
        checkpointer: Optional checkpointer for persistence.
                      If None, uses the default SQLite checkpointer.

    Returns:
        A compiled LangGraph agent.
    """
    global _agent

    # Return cached agent if no custom checkpointer is provided
    if checkpointer is None and _agent is not None:
        return _agent

    if checkpointer is None:
        checkpointer = get_checkpointer()

    model = create_model(DEFAULT_MODEL)

    agent = create_deep_agent(
        model=model,
        tools=[internet_search],
        system_prompt=SEARCH_AGENT_PROMPT,
        checkpointer=checkpointer,
    )

    # Cache the agent if using default checkpointer
    if checkpointer == get_checkpointer():
        _agent = agent

    return agent


async def search(
    query: str,
    thread_id: str | None = None,
    message_id: str | None = None,
) -> dict:
    """Execute a search query and return the result.

    Args:
        query: The search query from the user.
        thread_id: Optional thread ID for conversation continuity.
                   If None, a new thread is created.
        message_id: Optional message ID (checkpoint_id) for time travel.
                    If provided, resumes from that specific checkpoint.

    Returns:
        A dict containing:
            - response: The agent's response as a string.
            - thread_id: The thread ID used for this conversation.
            - message_id: The checkpoint ID of this response.
    """
    agent = get_search_agent()

    # Generate new thread_id if not provided
    if thread_id is None:
        thread_id = str(uuid.uuid4())

    # Build config with thread_id and optional checkpoint_id for time travel
    config = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})
    if message_id is not None:
        config_any = cast(dict[str, Any], config)
        configurable = cast(dict[str, Any], config_any.setdefault("configurable", {}))
        configurable["checkpoint_id"] = message_id

    result = agent.invoke({"messages": [{"role": "user", "content": query}]}, config)

    # Get the last AI message
    last_message = result["messages"][-1]
    content = last_message.content

    # Handle content that may be a list of content blocks
    if isinstance(content, list):
        # Extract text from content blocks
        text_parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
            elif isinstance(block, str):
                text_parts.append(block)
        response = "".join(text_parts)
    else:
        response = content

    # Get the checkpoint_id from the agent's state
    state = agent.get_state(config)
    configurable = cast(dict[str, Any], state.config.get("configurable") or {})
    checkpoint_id = configurable.get("checkpoint_id")

    return {
        "response": response,
        "thread_id": thread_id,
        "message_id": checkpoint_id,
    }


def search_streaming(
    query: str,
    thread_id: str | None = None,
    message_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Stream a search response as incremental deltas.

    This yields event dicts suitable for SSE or other streaming transports.

    Events:
        - {"type": "meta", "thread_id": str, "message_id": str | None}
        - {"type": "delta", "content": str}
        - {"type": "final", "response": str, "thread_id": str, "message_id": str | None}

    Args:
        query: The search query from the user.
        thread_id: Optional thread ID for conversation continuity.
        message_id: Optional message ID (checkpoint_id) for time travel.
    """
    agent = get_search_agent()

    if thread_id is None:
        thread_id = str(uuid.uuid4())

    config = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})
    if message_id is not None:
        config_any = cast(dict[str, Any], config)
        configurable = cast(dict[str, Any], config_any.setdefault("configurable", {}))
        configurable["checkpoint_id"] = message_id

    yield {"type": "meta", "thread_id": thread_id, "message_id": message_id}

    last_emitted = ""

    def _messages_from_stream_item(item):
        # LangGraph streaming shapes vary by stream_mode/version.
        # We prefer extracting from a state-like dict with a "messages" key.
        if isinstance(item, dict):
            return item.get("messages")
        if isinstance(item, tuple) and len(item) == 2:
            _, payload = item
            if isinstance(payload, dict):
                return payload.get("messages")
            if isinstance(payload, tuple) and len(payload) == 2:
                maybe_state, _metadata = payload
                if isinstance(maybe_state, dict):
                    return maybe_state.get("messages")
        return None

    def _extract_message_text(message) -> str | None:
        content = getattr(message, "content", None)
        if content is None:
            return None
        return _extract_content(content)

    try:
        # Use stream_mode="messages" for token-level streaming
        stream_iter = agent.stream(
            {"messages": [{"role": "user", "content": query}]},
            config,
            stream_mode="messages",
        )
    except TypeError:
        stream_iter = agent.stream(
            {"messages": [{"role": "user", "content": query}]},
            config,
        )

    for item in stream_iter:
        # stream_mode="messages" yields (message_chunk, metadata) tuples
        if isinstance(item, tuple) and len(item) >= 1:
            message_chunk = item[0]
        else:
            # Fallback for unexpected format
            messages = _messages_from_stream_item(item)
            if not messages:
                continue
            message_chunk = messages[-1]

        # Only process AI messages, skip user/tool messages
        message_type = type(message_chunk).__name__
        if message_type not in ("AIMessage", "AIMessageChunk"):
            continue

        # Extract content from the chunk
        text = _extract_message_text(message_chunk)
        if not text:
            continue

        # Calculate delta from last emitted text
        if text.startswith(last_emitted):
            delta = text[len(last_emitted) :]
        else:
            delta = text

        if delta:
            last_emitted = text
            yield {"type": "delta", "content": delta}

    state = agent.get_state(config)
    configurable = cast(dict[str, Any], state.config.get("configurable") or {})
    checkpoint_id = configurable.get("checkpoint_id")
    yield {
        "type": "final",
        "response": last_emitted,
        "thread_id": thread_id,
        "message_id": checkpoint_id,
    }


def get_thread_history(thread_id: str) -> list[dict]:
    """Get the conversation history for a thread.

    Args:
        thread_id: The thread ID to get history for.

    Returns:
        A list of checkpoints with message_id and metadata.
    """
    agent = get_search_agent()
    config = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})

    history = []
    for state in agent.get_state_history(config):
        configurable = cast(dict[str, Any], state.config.get("configurable") or {})
        checkpoint_id = configurable.get("checkpoint_id")
        # Get the last message if available
        messages = state.values.get("messages", [])
        last_message = messages[-1] if messages else None

        history.append(
            {
                "message_id": checkpoint_id,
                "created_at": state.created_at,
                "message_count": len(messages),
                "last_message_type": (type(last_message).__name__ if last_message else None),
                "last_message_content": (_extract_content(last_message.content) if last_message else None),
            }
        )

    return history


def get_thread(thread_id: str) -> list[dict]:
    """Get all messages for a thread.

    Args:
        thread_id: The thread ID to get messages for.

    Returns:
        A list of messages with their details.
    """
    agent = get_search_agent()
    config = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})

    # Get the latest state
    state = agent.get_state(config)
    messages = state.values.get("messages", [])

    message_list = []
    for msg in messages:
        message_list.append(
            {
                "type": msg.type if hasattr(msg, "type") else type(msg).__name__,
                "content": _extract_content(msg.content),
                "id": msg.id if hasattr(msg, "id") else None,
            }
        )

    return message_list


def _extract_content(content) -> str:
    """Extract text content from message content.

    Args:
        content: The message content (string or list of blocks).

    Returns:
        The extracted text content.
    """
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
            elif isinstance(block, str):
                text_parts.append(block)
        return "".join(text_parts)
    return content


def get_thread_list() -> list[ThreadMetadata]:
    """Get list of threads with their IDs and titles.

    Returns:
        List of ThreadMetadata instances.
    """
    checkpointer = get_checkpointer()

    # Get all thread_ids from checkpoints
    thread_ids = set()
    for tuple in checkpointer.list(config=None):
        config = tuple.config
        thread_id = config.get("configurable", {}).get("thread_id")
        if thread_id:
            thread_ids.add(thread_id)

    # Get custom titles from thread_metadata table using SQLModel
    engine = get_metadata_engine()
    with Session(engine) as session:
        statement = select(ThreadMetadata).where(ThreadMetadata.thread_id.in_(thread_ids))
        results = session.exec(statement).all()
        metadata_map = {metadata.thread_id: metadata for metadata in results}

    thread_list = []
    for thread_id in thread_ids:
        # Use existing metadata if available
        if thread_id in metadata_map:
            thread_list.append(metadata_map[thread_id])
        else:
            # Fallback to first user message
            config = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})
            state_tuple = checkpointer.get_tuple(config)
            title = None
            if state_tuple and state_tuple.checkpoint:
                # Messages are stored in channel_values
                channel_values = state_tuple.checkpoint.get("channel_values", {})
                messages = channel_values.get("messages", [])
                if messages:
                    # Find the first user message
                    for msg in messages:
                        if hasattr(msg, "type") and msg.type == "human":
                            title = msg.content
                            break

            if title:
                # Create a transient ThreadMetadata instance (not saved to DB)
                metadata = ThreadMetadata(
                    thread_id=thread_id, title=title, created_at=datetime.now(), updated_at=datetime.now()
                )
                thread_list.append(metadata)

    return thread_list


def rename_thread(thread_id: str, new_title: str) -> bool:
    """Rename a thread by updating its title in thread_metadata table.

    Args:
        thread_id: The thread ID to rename.
        new_title: The new title for the thread.

    Returns:
        True if successful, False if thread not found.
    """
    # Check if thread exists in checkpoints
    checkpointer = get_checkpointer()
    config = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})
    state_tuple = checkpointer.get_tuple(config)

    if state_tuple is None:
        return False

    engine = get_metadata_engine()
    try:
        with Session(engine) as session:
            # Check if metadata already exists
            statement = select(ThreadMetadata).where(ThreadMetadata.thread_id == thread_id)
            existing = session.exec(statement).first()

            if existing:
                # Update existing
                existing.title = new_title
                existing.updated_at = datetime.now()
            else:
                # Create new
                metadata = ThreadMetadata(thread_id=thread_id, title=new_title)
                session.add(metadata)

            session.commit()
        return True
    except Exception:
        return False


def delete_thread(thread_id: str) -> bool:
    """Delete all checkpoints and metadata associated with a thread.

    Args:
        thread_id: The thread ID to delete.

    Returns:
        True if successful, False if thread not found.
    """
    import sqlite3

    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    try:
        # Check if thread exists
        cursor.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (thread_id,))
        count = cursor.fetchone()[0]

        if count == 0:
            return False

        # Delete all checkpoints for this thread
        cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        # Also delete from writes table if it exists
        cursor.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
        conn.commit()

        # Delete thread metadata using SQLModel
        engine = get_metadata_engine()
        with Session(engine) as session:
            statement = select(ThreadMetadata).where(ThreadMetadata.thread_id == thread_id)
            metadata = session.exec(statement).first()
            if metadata:
                session.delete(metadata)
                session.commit()

        return True
    except (sqlite3.Error, Exception):
        conn.rollback()
        return False
    finally:
        conn.close()
