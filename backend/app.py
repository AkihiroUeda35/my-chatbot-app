import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import (
    ThreadMetadata,
    delete_thread,
    get_search_agent,
    get_thread,
    get_thread_list,
    rename_thread,
    search,
    search_streaming,
)
from log_setting import getLogger, initialize

logger = getLogger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup: Initialize the agent to avoid cold start delays
    logger.info("Initializing search agent...")
    get_search_agent()  # Pre-warm the agent cache
    logger.info("Search agent initialized")
    yield
    # Shutdown: cleanup if needed
    logger.info("Shutting down...")


app = FastAPI(title="Search Agent API", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    thread_id: str | None = None
    message_id: str | None = None


class SearchResponse(BaseModel):
    response: str
    thread_id: str
    message_id: str | None = None


class Message(BaseModel):
    type: str
    content: str
    id: str | None = None


class ThreadResponse(BaseModel):
    messages: list[Message]


class ThreadListResponse(BaseModel):
    threads: list[ThreadMetadata]


class RenameThreadRequest(BaseModel):
    title: str


class RenameThreadResponse(BaseModel):
    success: bool
    message: str | None = None


@app.get("/")
def health_check():
    """Health check endpoint."""
    logger.debug("Health check called")
    return {"status": "ok"}


@app.get("/api/threads", response_model=ThreadListResponse)
async def api_get_threads():
    """Get list of threads with their IDs and titles."""
    threads = get_thread_list()

    logger.debug(f"api_get_threads: Retrieved {len(threads)} threads")
    return ThreadListResponse(threads=threads)


@app.get("/api/thread/{thread_id}", response_model=ThreadResponse)
async def api_get_thread(thread_id: str):
    """Get all messages for a specific thread."""
    messages_data = get_thread(thread_id)
    messages = [Message(**msg) for msg in messages_data]
    logger.debug(f"api_get_thread: Retrieved {len(messages)} messages for thread_id={thread_id}")
    return ThreadResponse(messages=messages)


@app.put("/api/thread/{thread_id}", response_model=RenameThreadResponse)
async def api_rename_thread(thread_id: str, request: RenameThreadRequest):
    """Rename a thread."""
    success = rename_thread(thread_id, request.title)
    if success:
        return RenameThreadResponse(success=True)
    return RenameThreadResponse(success=False, message="Thread not found")


@app.delete("/api/thread/{thread_id}", response_model=RenameThreadResponse)
async def api_delete_thread(thread_id: str):
    """Delete a thread."""
    success = delete_thread(thread_id)
    if success:
        return RenameThreadResponse(success=True)
    return RenameThreadResponse(success=False, message="Thread not found")


@app.post("/api/search", response_model=SearchResponse)
async def api_search(request: SearchRequest):
    """Search API endpoint."""
    result = await search(
        query=request.query,
        thread_id=request.thread_id,
        message_id=request.message_id,
    )
    return SearchResponse(
        response=result["response"],
        thread_id=result["thread_id"],
        message_id=result["message_id"],
    )


@app.post("/api/chat")
async def api_chat(request: SearchRequest):
    """Chat API endpoint compatible with Vercel AI SDK Data Stream Protocol.

    This endpoint streams responses in Vercel AI SDK format for use with useChat hook.
    """
    import json

    def escape_text(text: str) -> str:
        """Escape text for JSON string embedding."""
        return json.dumps(text, ensure_ascii=False)

    def event_generator():
        thread_id = None
        message_id = None
        try:
            for evt in search_streaming(
                query=request.query,
                thread_id=request.thread_id,
                message_id=request.message_id,
            ):
                evt_type = evt.get("type")
                if evt_type == "meta":
                    thread_id = evt.get("thread_id")
                    message_id = evt.get("message_id")
                elif evt_type == "delta":
                    content = evt.get("content", "")
                    # Vercel AI SDK text format: 0:"text"\n
                    yield f"0:{escape_text(content)}\n"
                elif evt_type == "final":
                    thread_id = evt.get("thread_id", thread_id)
                    message_id = evt.get("message_id", message_id)

            # Send finish message with metadata
            # Format: d:{"finishReason":"stop","usage":{}}\n
            finish_data = {
                "finishReason": "stop",
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }
            yield f"d:{json.dumps(finish_data, ensure_ascii=False)}\n"

            # Send custom metadata as message annotation
            # Format: 8:[{"thread_id":"...","message_id":"..."}]\n
            if thread_id:
                metadata = [{"thread_id": thread_id, "message_id": message_id}]
                yield f"8:{json.dumps(metadata, ensure_ascii=False)}\n"

        except Exception as exc:  # pragma: no cover
            # Error format: 3:"error message"\n
            yield f"3:{escape_text(str(exc))}\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/plain; charset=utf-8",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/plain; charset=utf-8",
        headers=headers,
    )


if __name__ == "__main__":
    initialize(log_level=logging.DEBUG)
    logger.info("Starting Search Agent API server...")
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
