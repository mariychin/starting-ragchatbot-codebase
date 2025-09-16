# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend && uv run uvicorn app:app --reload --port 8000
```

### Environment Setup
```bash
# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env to add ANTHROPIC_API_KEY
```

### Development Server
- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Architecture Overview

This is a **RAG (Retrieval-Augmented Generation) system** for querying course materials with AI-powered responses. The architecture follows a clear separation of concerns:

### Core Flow
1. **Frontend** (`frontend/`) - Static HTML/CSS/JS chat interface
2. **FastAPI Backend** (`backend/app.py`) - RESTful API with `/api/query` and `/api/courses` endpoints
3. **RAG Orchestrator** (`backend/rag_system.py`) - Coordinates all components
4. **AI Generator** (`backend/ai_generator.py`) - Manages Claude API with tool calling
5. **Search Tools** (`backend/search_tools.py`) - Semantic search capabilities
6. **Vector Store** (`backend/vector_store.py`) - ChromaDB interface with embeddings

### Key Components

**Document Processing Pipeline** (`backend/document_processor.py`):
- Parses structured course documents with format: Course Title/Link/Instructor → Lessons
- Implements intelligent sentence-based chunking with overlap
- Enriches chunks with course/lesson context for better retrieval

**Tool-Based Search** (`backend/search_tools.py`):
- Claude autonomously decides when to search vs. answer from knowledge
- Supports course name filtering and lesson number filtering
- Tracks sources for UI transparency

**Session Management** (`backend/session_manager.py`):
- Maintains conversation context across queries
- Configurable history limits to prevent context bloat

**Configuration** (`backend/config.py`):
- Centralized settings: chunk sizes, models, API keys, database paths
- Uses environment variables for sensitive data

### Data Flow Pattern
```
User Query → Frontend → FastAPI → RAGSystem → AIGenerator → Claude API
                                      ↓
                              SessionManager (context)
                                      ↓
                              ToolManager → SearchTool → VectorStore → ChromaDB
```

### Document Structure
Course documents in `docs/` follow this format:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [instructor]

Lesson 0: Introduction
Lesson Link: [lesson_url]
[lesson content...]
```

### Important Implementation Details

**Tool Calling Architecture**: Claude decides when to search using the `search_course_content` tool. The AI Generator handles tool execution and follows up with Claude to synthesize results.

**Vector Search**: Uses sentence-transformers embeddings stored in ChromaDB. Supports semantic matching with metadata filtering by course title and lesson number.

**Stateful Conversations**: Frontend maintains `currentSessionId` which links to server-side conversation history for context continuity.

**Source Attribution**: Search results track which course/lesson chunks informed the response, displayed in collapsible UI sections.

## Configuration

Key settings in `backend/config.py`:
- `CHUNK_SIZE`: 800 chars (balance between context and specificity)
- `CHUNK_OVERLAP`: 100 chars (maintains context across chunks)
- `MAX_RESULTS`: 5 search results per query
- `MAX_HISTORY`: 2 conversation turns remembered
- `ANTHROPIC_MODEL`: claude-sonnet-4-20250514

## Adding New Course Materials

1. Place files in `docs/` directory (supports .txt, .pdf, .docx)
2. Use the structured format above
3. Server automatically processes new files on startup
4. Existing courses are skipped to avoid duplicates
- always use uv to run the server do not use pip directly
- make sure to use uv to manage all dependencies