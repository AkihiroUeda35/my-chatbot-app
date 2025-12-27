from starlette.testclient import TestClient
from log_setting import getLogger

import app as app_module

logger = getLogger()

def test_health_check():
    client = TestClient(app_module.app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_api_search():
    client = TestClient(app_module.app)
    res = client.post("/api/search", json={"query": "hello"})
    assert res.status_code == 200
    logger.info(res.json())

def test_api_get_threads():
    client = TestClient(app_module.app)

    # Now test getting threads
    res = client.get("/api/threads")
    assert res.status_code == 200
    data = res.json()
    assert "threads" in data
    threads = data["threads"]
    assert isinstance(threads, list)

    logger.info(f"Found {len(threads)} threads: {threads}")

    for thread in threads:
        assert "thread_id" in thread
        assert "title" in thread
        logger.info(f"Thread ID: {thread['thread_id']}, Title: {thread['title']}")


def test_api_get_thread():
    client = TestClient(app_module.app)

    # First, create a thread by performing a search
    res = client.post("/api/search", json={"query": "Test query for thread"})
    assert res.status_code == 200
    search_data = res.json()
    thread_id = search_data["thread_id"]
    assert thread_id is not None

    # Now test getting the thread
    res = client.get(f"/api/thread/{thread_id}")
    assert res.status_code == 200
    data = res.json()
    assert "messages" in data
    messages = data["messages"]
    assert isinstance(messages, list)
    assert len(messages) > 0  # Should have at least one message

    logger.info(f"Thread {thread_id} has {len(messages)} messages:")
    for msg in messages:
        assert "type" in msg
        assert "content" in msg
        logger.info(f"  {msg['type']}: {msg['content'][:50]}...")  # logger.info first 50 chars


def test_api_rename_thread():
    client = TestClient(app_module.app)

    # First, create a thread by performing a search
    res = client.post("/api/search", json={"query": "Original query for rename test"})
    assert res.status_code == 200
    search_data = res.json()
    thread_id = search_data["thread_id"]
    assert thread_id is not None

    # Rename the thread
    new_title = "My Custom Thread Title"
    res = client.put(f"/api/thread/{thread_id}", json={"title": new_title})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data.get("message") is None

    # Verify the rename by getting thread list
    res = client.get("/api/threads")
    assert res.status_code == 200
    threads_data = res.json()
    threads = threads_data["threads"]
    
    # Find our thread and verify the title
    thread_found = False
    for thread in threads:
        if thread["thread_id"] == thread_id:
            assert thread["title"] == new_title
            thread_found = True
            logger.info(f"Thread {thread_id} successfully renamed to: {thread['title']}")
            break
    
    assert thread_found, f"Thread {thread_id} not found in thread list"

    # Test renaming a non-existent thread
    res = client.put("/api/thread/non-existent-thread-id", json={"title": "Should fail"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["message"] == "Thread not found"


def test_api_delete_thread():
    client = TestClient(app_module.app)

    # First, create a thread by performing a search
    res = client.post("/api/search", json={"query": "Query for delete test"})
    assert res.status_code == 200
    search_data = res.json()
    logger.info(search_data)
    thread_id = search_data["thread_id"]
    assert thread_id is not None

    # Verify the thread exists in the thread list
    res = client.get("/api/threads")
    assert res.status_code == 200
    threads_data = res.json()
    thread_ids_before = [thread["thread_id"] for thread in threads_data["threads"]]
    assert thread_id in thread_ids_before

    # Delete the thread
    res = client.delete(f"/api/thread/{thread_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data.get("message") is None
    logger.info(f"Thread {thread_id} successfully deleted")

    # Verify the thread no longer exists in the thread list
    res = client.get("/api/threads")
    assert res.status_code == 200
    threads_data = res.json()
    thread_ids_after = [thread["thread_id"] for thread in threads_data["threads"]]
    assert thread_id not in thread_ids_after

    # Verify we cannot get the deleted thread
    res = client.get(f"/api/thread/{thread_id}")
    assert res.status_code == 200
    data = res.json()
    # Should return empty messages since thread is deleted
    assert data["messages"] == []

    # Test deleting a non-existent thread
    res = client.delete("/api/thread/non-existent-thread-id")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["message"] == "Thread not found"
