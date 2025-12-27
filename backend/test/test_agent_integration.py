"""Integration tests for the search agent.

These tests actually create and invoke the agent.
Requires TAVILY_API_KEY and GOOGLE_API_KEY environment variables.
"""

import os
import tempfile
import uuid

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from agent import (
    DEFAULT_MODEL,
    SEARCH_AGENT_PROMPT,
    create_deep_agent,
    create_model,
    get_search_agent,
    get_thread_history,
    internet_search,
    search,
    search_streaming,
)

from log_setting import getLogger

logger = getLogger()

class TestAgentCreation:
    """Tests for agent creation."""

    def test_create_model(self):
        """Test that the model is created correctly."""
        model = create_model(DEFAULT_MODEL)
        logger.info("model:", model)

        assert model is not None
        assert hasattr(model, "invoke")

    def test_create_agent_with_tools(self):
        """Test that the agent is created with the correct tools."""
        model = create_model(DEFAULT_MODEL)
        agent = create_deep_agent(
            model=model,
            tools=[internet_search],
            system_prompt=SEARCH_AGENT_PROMPT,
        )
        logger.info("agent:", agent)

        # Agent should be a compiled LangGraph
        assert agent is not None
        assert hasattr(agent, "invoke")
        assert hasattr(agent, "stream")

    def test_get_search_agent_returns_valid_agent(self):
        """Test that get_search_agent returns a valid agent."""
        # Use a temporary database for testing
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            temp_db = f.name

        try:
            import sqlite3

            conn = sqlite3.connect(temp_db, check_same_thread=False)
            checkpointer = SqliteSaver(conn)
            agent = get_search_agent(checkpointer=checkpointer)
            logger.info("agent:", agent)

            assert agent is not None
            assert hasattr(agent, "invoke")
        finally:
            conn.close()
            os.unlink(temp_db)


def test_model():
    """Test that the model can be created and invoked."""
    model = create_model(DEFAULT_MODEL)
    response = model.invoke([{"role": "user", "content": "Hello"}])
    logger.info("response:", response)

    assert model is not None
    assert hasattr(model, "invoke")


class TestAgentInvoke:
    """Tests for agent invocation."""

    def test_agent_invoke_returns_messages(self):
        """Test that agent invoke returns messages."""
        model = create_model(DEFAULT_MODEL)
        agent = create_deep_agent(
            model=model,
            tools=[internet_search],
            system_prompt=SEARCH_AGENT_PROMPT,
        )

        result = agent.invoke({"messages": [{"role": "user", "content": "What is 2 + 2?"}]})
        logger.info("result:", result)

        assert "messages" in result
        assert len(result["messages"]) > 0

        # Last message should be an AI message
        last_message = result["messages"][-1]
        logger.info("last_message:", last_message)
        assert isinstance(last_message, AIMessage)
        assert last_message.content is not None

    def test_agent_invoke_with_search_query(self):
        """Test that agent can handle search queries."""
        model = create_model(DEFAULT_MODEL)
        agent = create_deep_agent(
            model=model,
            tools=[internet_search],
            system_prompt=SEARCH_AGENT_PROMPT,
        )

        result = agent.invoke({"messages": [{"role": "user", "content": "What is LangGraph?"}]})
        logger.info("result:", result)

        assert "messages" in result
        last_message = result["messages"][-1]
        logger.info("last_message:", last_message)
        assert isinstance(last_message, AIMessage)
        assert len(last_message.content) > 0


class TestSearchFunction:
    """Tests for the search function."""

    @pytest.fixture
    def temp_checkpoint_db(self):
        """Create a temporary database for testing."""
        import agent as agent_module

        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            temp_db = f.name

        # Set the checkpoint path for tests
        original_path = agent_module.CHECKPOINT_DB_PATH
        agent_module.CHECKPOINT_DB_PATH = temp_db
        agent_module._checkpointer = None

        yield temp_db

        # Cleanup
        agent_module.CHECKPOINT_DB_PATH = original_path
        agent_module._checkpointer = None
        try:
            os.unlink(temp_db)
        except (OSError, PermissionError):
            pass

    @pytest.mark.asyncio
    async def test_search_returns_dict_with_response(self, temp_checkpoint_db):
        """Test that search function returns a dict with response."""
        result = await search("What is Python programming language?")
        logger.info(result)

        assert isinstance(result, dict)
        assert "response" in result
        assert "thread_id" in result
        assert "message_id" in result
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_search_generates_new_thread_id(self, temp_checkpoint_db):
        """Test that search generates a new thread_id when not provided."""
        result = await search("Hello!")
        logger.info(result)

        assert result["thread_id"] is not None
        # Validate it's a UUID format
        uuid.UUID(result["thread_id"])

    @pytest.mark.asyncio
    async def test_search_continues_conversation_with_thread_id(self, temp_checkpoint_db):
        """Test that search continues conversation with the same thread_id."""
        # First message
        result1 = await search("My name is Alice.")
        logger.info("First result:", result1)
        thread_id = result1["thread_id"]

        # Second message in same thread
        result2 = await search("What is my name?", thread_id=thread_id)
        logger.info("Second result:", result2)

        assert result2["thread_id"] == thread_id
        # The agent should remember the name from context
        assert "Alice" in result2["response"] or "alice" in result2["response"].lower()

    @pytest.mark.asyncio
    async def test_search_with_explicit_thread_id(self, temp_checkpoint_db):
        """Test that search uses the provided thread_id."""
        custom_thread_id = str(uuid.uuid4())
        result = await search("Hello!", thread_id=custom_thread_id)
        logger.info(result)

        assert result["thread_id"] == custom_thread_id

    @pytest.mark.asyncio
    async def test_search_handles_simple_questions(self, temp_checkpoint_db):
        """Test that search can handle simple questions."""
        result = await search("Hello, how are you?")
        logger.info(result)

        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0

    def test_search_streaming_yields_final_event(self, temp_checkpoint_db):
        """Test that search_streaming yields delta events and a final event."""
        deltas: list[str] = []
        meta = None
        final = None

        for evt in search_streaming("Hello!"):
            if evt.get("type") == "meta":
                meta = evt
            elif evt.get("type") == "delta":
                deltas.append(evt.get("content", ""))
            elif evt.get("type") == "final":
                final = evt
                break

        assert meta is not None
        assert meta["thread_id"] is not None

        assert final is not None
        assert final["thread_id"] == meta["thread_id"]
        assert "message_id" in final
        assert isinstance(final["response"], str)
        assert len(final["response"]) > 0 or len("".join(deltas)) > 0


class TestTimeTravelFunction:
    """Tests for time travel functionality with message_id."""

    @pytest.fixture
    def temp_checkpoint_db(self):
        """Create a temporary database for testing."""
        import agent as agent_module

        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            temp_db = f.name

        # Set the checkpoint path for tests
        original_path = agent_module.CHECKPOINT_DB_PATH
        agent_module.CHECKPOINT_DB_PATH = temp_db
        agent_module._checkpointer = None

        yield temp_db

        # Cleanup
        agent_module.CHECKPOINT_DB_PATH = original_path
        agent_module._checkpointer = None
        try:
            os.unlink(temp_db)
        except (OSError, PermissionError):
            pass

    @pytest.mark.asyncio
    async def test_time_travel_resumes_from_checkpoint(self, temp_checkpoint_db):
        """Test that providing message_id resumes from that checkpoint."""
        # Create a conversation
        result1 = await search("My favorite color is blue.")
        logger.info("Result 1:", result1)
        thread_id = result1["thread_id"]
        checkpoint1 = result1["message_id"]

        result2 = await search("My favorite food is pizza.", thread_id=thread_id)
        logger.info("Result 2:", result2)
        checkpoint2 = result2["message_id"]

        # Now time travel back to checkpoint1 and ask a different question
        result3 = await search(
            "What is my favorite color?",
            thread_id=thread_id,
            message_id=checkpoint1,
        )
        logger.info("Result 3 (time travel):", result3)

        # The agent should know about blue (from checkpoint1)
        # but the response is a new branch from that point
        assert result3["thread_id"] == thread_id
        assert "blue" in result3["response"].lower()

    @pytest.mark.asyncio
    async def test_get_thread_history(self, temp_checkpoint_db):
        """Test that get_thread_history returns conversation checkpoints."""
        # Create a conversation with multiple messages
        result1 = await search("First message")
        logger.info("Result 1:", result1)
        thread_id = result1["thread_id"]

        result2 = await search("Second message", thread_id=thread_id)
        logger.info("Result 2:", result2)

        result3 = await search("Third message", thread_id=thread_id)
        logger.info("Result 3:", result3)

        # Get history
        history = get_thread_history(thread_id)
        logger.info("History:", history)

        assert len(history) > 0
        # History should have message_ids
        for checkpoint in history:
            assert "message_id" in checkpoint
            assert checkpoint["message_id"] is not None

    @pytest.mark.asyncio
    async def test_separate_threads_are_independent(self, temp_checkpoint_db):
        """Test that different thread_ids maintain separate conversations."""
        # First thread
        result1 = await search("My name is Bob.")
        logger.info("Result 1 (Bob):", result1)
        thread1 = result1["thread_id"]

        # Second thread
        result2 = await search("My name is Carol.")
        logger.info("Result 2 (Carol):", result2)
        thread2 = result2["thread_id"]

        assert thread1 != thread2

        # Ask about name in first thread
        result3 = await search("What is my name?", thread_id=thread1)
        logger.info("Thread 1 response:", result3["response"])

        # Ask about name in second thread
        result4 = await search("What is my name?", thread_id=thread2)
        logger.info("Thread 2 response:", result4["response"])

        # Each should remember their respective names
        assert "Bob" in result3["response"] or "bob" in result3["response"].lower()
        assert "Carol" in result4["response"] or "carol" in result4["response"].lower()


class TestInternetSearchTool:
    """Tests for the internet_search tool."""

    def test_internet_search_returns_results(self):
        """Test that internet_search returns search results."""
        result = internet_search("Python programming", max_results=3)
        for res in result["results"]:
            logger.info("search result:", res)
        assert isinstance(result, dict)
        assert "results" in result
        assert len(result["results"]) <= 3

    def test_internet_search_results_have_required_fields(self):
        """Test that search results have required fields."""
        result = internet_search("machine learning", max_results=1)

        assert "results" in result
        if result["results"]:
            first_result = result["results"][0]
            assert "title" in first_result
            assert "url" in first_result
            assert "content" in first_result
            for result_item in result["results"]:
                logger.info("result item:", result_item)
                assert len(result_item["title"]) > 0
                assert len(result_item["url"]) > 0
                assert len(result_item["content"]) > 0


class TestAgentWithToolCalls:
    """Tests for agent tool calling behavior."""

    def test_agent_uses_search_tool_when_needed(self):
        """Test that agent uses search tool for queries requiring current info."""
        model = create_model(DEFAULT_MODEL)
        agent = create_deep_agent(
            model=model,
            tools=[internet_search],
            system_prompt=SEARCH_AGENT_PROMPT,
        )

        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Search the web and tell me about the latest AI news.",
                    }
                ]
            }
        )

        # Check that tool was called by looking at message history
        messages = result["messages"]
        tool_calls_found = False
        for msg in messages:
            logger.info("message:", msg)
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_found = True
                break
        # Agent should have made tool calls for this query
        assert tool_calls_found, "Agent should use internet_search tool for this query"
