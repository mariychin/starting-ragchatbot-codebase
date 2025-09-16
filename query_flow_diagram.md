# RAG System Query Flow Diagram

```mermaid
sequenceDiagram
    participant User
    participant Frontend as Frontend<br/>(script.js)
    participant API as FastAPI<br/>(app.py)
    participant RAG as RAGSystem<br/>(rag_system.py)
    participant AI as AIGenerator<br/>(ai_generator.py)
    participant Claude as Anthropic<br/>Claude API
    participant Tools as ToolManager<br/>(search_tools.py)
    participant Vector as VectorStore<br/>(vector_store.py)
    participant Chroma as ChromaDB
    participant Session as SessionManager<br/>(session_manager.py)

    Note over User,Session: User Query Processing Flow

    %% User Input
    User->>Frontend: Types query & clicks send
    Frontend->>Frontend: Validate input, show loading

    %% HTTP Request
    Frontend->>+API: POST /api/query<br/>{query, session_id}

    %% Session Management
    API->>RAG: query(text, session_id)
    RAG->>Session: get_conversation_history(session_id)
    Session-->>RAG: Previous messages (formatted)

    %% AI Generation Setup
    RAG->>+AI: generate_response(query, history, tools, tool_manager)
    AI->>AI: Build system prompt + context

    %% Claude API Call
    AI->>+Claude: messages.create(prompt, tools, tool_choice="auto")

    %% Tool Decision Point
    alt Claude decides to search
        Claude-->>-AI: tool_use response<br/>(search_course_content)

        %% Tool Execution
        AI->>Tools: execute_tool("search_course_content", params)
        Tools->>+Vector: search(query, course_name, lesson_number)

        %% Vector Search
        Vector->>Vector: Embed query with sentence-transformers
        Vector->>+Chroma: query(embeddings, filters, n_results)
        Chroma-->>-Vector: Similar chunks + metadata
        Vector->>Vector: Format results with course/lesson context
        Vector-->>-Tools: SearchResults with sources

        Tools->>Tools: _format_results() & store sources
        Tools-->>AI: Formatted search results

        %% Final Response Generation
        AI->>+Claude: messages.create(conversation + tool_results)
        Claude-->>-AI: Final answer based on search results

    else Claude answers from knowledge
        Claude-->>-AI: Direct response (no search needed)
    end

    %% Response Assembly
    AI-->>-RAG: Generated response text
    RAG->>Tools: get_last_sources()
    Tools-->>RAG: Source list for UI
    RAG->>Tools: reset_sources()

    %% Update Session
    RAG->>Session: add_exchange(session_id, query, response)
    Session->>Session: Store in conversation history

    %% API Response
    RAG-->>API: (response_text, sources)
    API-->>-Frontend: QueryResponse{answer, sources, session_id}

    %% Frontend Display
    Frontend->>Frontend: Remove loading indicator
    Frontend->>Frontend: addMessage(answer, 'assistant', sources)
    Frontend->>Frontend: Render markdown + collapsible sources
    Frontend-->>User: Display response with sources

    Note over User,Session: Conversation state maintained for follow-up queries
```

## Architecture Components

### Frontend Layer
- **HTML/CSS**: Static UI with chat interface and sidebar
- **JavaScript**: Handles user interactions, API calls, message rendering
- **Session**: Maintains `currentSessionId` for conversation continuity

### API Layer
- **FastAPI**: RESTful endpoints with Pydantic models
- **CORS**: Configured for development with proxy support
- **Error Handling**: HTTP status codes and exception management

### RAG Orchestration
- **RAGSystem**: Main coordinator between all components
- **Tool Integration**: Manages available tools for Claude
- **Session Coordination**: Links conversation state with processing

### AI Generation
- **Claude Integration**: Anthropic API with tool calling support
- **System Prompts**: Specialized instructions for course material queries
- **Tool Execution**: Handles multi-step tool use workflows

### Search & Retrieval
- **Tool Manager**: Plugin architecture for extensible tools
- **Vector Store**: ChromaDB with sentence-transformers embeddings
- **Semantic Search**: Similarity matching with metadata filtering

### Data Processing
- **Document Processor**: Converts course files to structured chunks
- **Session Manager**: Conversation history with configurable limits
- **Models**: Pydantic schemas for type safety

## Key Features

1. **Stateful Conversations**: Sessions maintain context across queries
2. **Intelligent Tool Use**: Claude decides when to search vs. use knowledge
3. **Semantic Search**: Vector embeddings enable contextual retrieval
4. **Source Tracking**: UI shows which courses/lessons informed the response
5. **Structured Data**: Course → Lesson → Chunk hierarchy preserved
6. **Real-time Processing**: Streaming-style UI with loading indicators