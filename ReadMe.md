# LLM practice application

## Software Stack

- Backend: FastAPI
    - LLM: Gemini or ollama(cloud, gpt-oss:120b)
    - Agent Framework: LangChain, LangGraph, DeepAgents
    - Virtual environment: uv
    - Linter: ruff
    - 
- Frontend: Next.js
    - Chat UI: assistant-ui
    - Styling: shadcn/ui
    - Querying: TanStack Query
    - State Management: zustand

- Database: SQLite(local)

## Directory Structure

- `/backend`: FastAPI backend code
    - `/tests`: Unit and integration tests for backend
    - `/tools`: Utility scripts
    
- `/frontend`: Next.js frontend code
   - `/app`: Next.js pages and API routes
   - `/components`: UI components
   - `/lib`: Client-side libraries and utilities
   - `/public`: Static assets

## Getting Started

### Prerequisites

- Python 3.12+ (for backend)
- Node.js 20+ (for frontend)
- uv (Python package manager)
- npm (Node package manager)

### Running the Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies with uv:
   ```bash
   uv sync
   ```

3. Set up environment variables (optional):
   - `TAVILY_API_KEY`: For web search functionality
   - `GOOGLE_API_KEY`: For Gemini LLM (if not using ollama)
   - `OLLAMA_API_BASE_URL`: URL for ollama API (default: http://localhost:11434)

4. Start the backend server:
   ```bash
   uv run python app.py
   ```

   The backend will be available at http://127.0.0.1:8000

### Running the Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env` file (or use the default):
   ```bash
   NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```

   The frontend will be available at http://localhost:3000

### Using the Chatbot

1. Open your browser and navigate to http://localhost:3000
2. You'll see a chat interface with a sidebar showing conversation threads
3. Type your message in the input field and press Enter or click Send
4. The chatbot will stream its response in real-time
5. You can:
   - Start a new conversation by clicking "New Thread"
   - Switch between previous conversations by clicking on them in the sidebar
   - Delete conversations by hovering over them and clicking the archive icon

## Features

- **Real-time Streaming**: Responses are streamed in real-time using Server-Sent Events (SSE)
- **Thread Management**: Conversations are organized into threads that can be saved and revisited
- **Web Search**: The chatbot can search the web using Tavily API to provide up-to-date information
- **Markdown Support**: Responses support markdown formatting including code blocks
- **Responsive UI**: The interface works on both desktop and mobile devices
