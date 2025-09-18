"""
Mock objects for RAG system testing
"""
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any, Optional
from vector_store import SearchResults
from models import Course, Lesson, CourseChunk


class MockVectorStore:
    """Mock VectorStore with configurable behavior"""

    def __init__(self,
                 populate_with_data: bool = True,
                 simulate_search_error: bool = False,
                 simulate_empty_results: bool = False):
        self.populate_with_data = populate_with_data
        self.simulate_search_error = simulate_search_error
        self.simulate_empty_results = simulate_empty_results
        self.last_search_query = None
        self.last_search_params = None

        # Mock course metadata
        self.mock_courses_metadata = [
            {
                "title": "Test Course",
                "instructor": "Test Instructor",
                "course_link": "https://example.com/course",
                "lessons": [
                    {"lesson_number": 1, "lesson_title": "Introduction", "lesson_link": "https://example.com/lesson1"},
                    {"lesson_number": 2, "lesson_title": "Advanced Topics", "lesson_link": "https://example.com/lesson2"}
                ]
            }
        ] if populate_with_data else []

    def search(self, query: str, course_name: Optional[str] = None,
              lesson_number: Optional[int] = None, limit: Optional[int] = None) -> SearchResults:
        """Mock search implementation"""
        self.last_search_query = query
        self.last_search_params = {
            "course_name": course_name,
            "lesson_number": lesson_number,
            "limit": limit
        }

        if self.simulate_search_error:
            return SearchResults.empty("Simulated search error")

        if self.simulate_empty_results or not self.populate_with_data:
            return SearchResults(documents=[], metadata=[], distances=[])

        # Return mock search results
        return SearchResults(
            documents=["Mock document content about " + query],
            metadata=[{"course_title": "Test Course", "lesson_number": 1}],
            distances=[0.1]
        )

    def _resolve_course_name(self, course_name: str) -> Optional[str]:
        """Mock course name resolution"""
        if not self.populate_with_data:
            return None

        # Simple matching logic for testing
        if "test" in course_name.lower() or "course" in course_name.lower():
            return "Test Course"
        return None

    def get_all_courses_metadata(self) -> List[Dict[str, Any]]:
        """Mock get all courses metadata"""
        return self.mock_courses_metadata

    def get_lesson_link(self, course_title: str, lesson_number: int) -> Optional[str]:
        """Mock get lesson link"""
        if course_title == "Test Course" and lesson_number in [1, 2]:
            return f"https://example.com/lesson{lesson_number}"
        return None


class MockAnthropicClient:
    """Mock Anthropic client for testing AI responses"""

    def __init__(self,
                 simulate_tool_use: bool = False,
                 simulate_api_error: bool = False,
                 custom_response: str = "Mock AI response"):
        self.simulate_tool_use = simulate_tool_use
        self.simulate_api_error = simulate_api_error
        self.custom_response = custom_response
        self.last_request_params = None
        self.call_count = 0

        # Set up messages mock
        self.messages = Mock()
        self.messages.create = self._create_message

    def _create_message(self, **kwargs):
        """Mock message creation"""
        self.call_count += 1
        self.last_request_params = kwargs

        if self.simulate_api_error:
            raise Exception("Simulated API error")

        response = Mock()

        if self.simulate_tool_use:
            # Simulate tool use response
            tool_block = Mock()
            tool_block.type = "tool_use"
            tool_block.name = "search_course_content"
            tool_block.id = "mock_tool_id"
            tool_block.input = {"query": "mock query"}

            response.content = [tool_block]
            response.stop_reason = "tool_use"
        else:
            # Simulate regular text response
            text_block = Mock()
            text_block.text = self.custom_response

            response.content = [text_block]
            response.stop_reason = "end_turn"

        return response


class EnhancedMockAnthropicClient:
    """Enhanced mock Anthropic client for testing sequential tool calling"""

    def __init__(self, response_sequence: List[Dict[str, Any]]):
        """
        Initialize with a sequence of responses to return in order.

        Args:
            response_sequence: List of response definitions
            Example: [
                {"type": "tool_use", "tool": "get_course_outline", "params": {"course_name": "test"}},
                {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test"}},
                {"type": "text", "content": "Final response"}
            ]
        """
        self.response_sequence = response_sequence
        self.call_index = 0
        self.call_history = []

        # Set up messages mock
        self.messages = Mock()
        self.messages.create = self._create_message

    @property
    def call_count(self) -> int:
        """Number of API calls made"""
        return len(self.call_history)

    def _create_message(self, **kwargs):
        """Mock message creation with sequential responses"""
        self.call_history.append(kwargs)

        # Return next response in sequence
        if self.call_index < len(self.response_sequence):
            response_def = self.response_sequence[self.call_index]
            self.call_index += 1
            return self._build_response(response_def)

        # Return empty response if sequence exhausted
        return self._build_text_response("Sequence exhausted")

    def _build_response(self, response_def: Dict[str, Any]):
        """Build a mock response from definition"""
        response = Mock()

        if response_def["type"] == "tool_use":
            # Create tool use response
            tool_block = Mock()
            tool_block.type = "tool_use"
            tool_block.name = response_def["tool"]
            tool_block.id = f"tool_{self.call_index}"
            tool_block.input = response_def.get("params", {})

            response.content = [tool_block]
            response.stop_reason = "tool_use"

        elif response_def["type"] == "text":
            # Create text response
            text_block = Mock()
            text_block.text = response_def["content"]

            response.content = [text_block]
            response.stop_reason = "end_turn"

        return response

    def _build_text_response(self, text: str):
        """Helper to build a text response"""
        response = Mock()
        text_block = Mock()
        text_block.text = text
        response.content = [text_block]
        response.stop_reason = "end_turn"
        return response

    def verify_message_context(self, call_index: int, expected_message_count: int):
        """Verify that the Nth API call has the expected message count"""
        if call_index >= len(self.call_history):
            raise AssertionError(f"Call index {call_index} not found in call history")

        call_params = self.call_history[call_index]
        actual_count = len(call_params.get("messages", []))

        if actual_count != expected_message_count:
            raise AssertionError(
                f"Call {call_index}: expected {expected_message_count} messages, got {actual_count}"
            )


class MockToolManager:
    """Mock ToolManager for testing tool execution"""

    def __init__(self,
                 simulate_tool_error: bool = False,
                 mock_search_result: str = "Mock search result"):
        self.simulate_tool_error = simulate_tool_error
        self.mock_search_result = mock_search_result
        self.last_tool_name = None
        self.last_tool_params = None
        self.mock_sources = [{"text": "Mock source", "link": "https://example.com"}]

        # For sequential tool calling tests
        self.execution_history = []
        self.execution_count = 0

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Mock tool definitions"""
        return [
            {
                "name": "search_course_content",
                "description": "Search course materials",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            }
        ]

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Mock tool execution"""
        self.last_tool_name = tool_name
        self.last_tool_params = kwargs

        # Track execution history
        execution_record = {
            "tool_name": tool_name,
            "params": kwargs.copy(),
            "execution_index": self.execution_count
        }
        self.execution_history.append(execution_record)
        self.execution_count += 1

        if self.simulate_tool_error:
            return "Tool execution failed"

        return self.mock_search_result

    def get_last_sources(self) -> List[Dict[str, Any]]:
        """Mock get last sources"""
        return self.mock_sources

    def reset_sources(self):
        """Mock reset sources"""
        self.mock_sources = []


class MockSessionManager:
    """Mock SessionManager for testing session handling"""

    def __init__(self):
        self.sessions = {}
        self.session_counter = 0

    def create_session(self) -> str:
        """Mock session creation"""
        self.session_counter += 1
        session_id = f"mock_session_{self.session_counter}"
        self.sessions[session_id] = []
        return session_id

    def add_exchange(self, session_id: str, user_message: str, assistant_message: str):
        """Mock add exchange"""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message}
        ])

    def get_conversation_history(self, session_id: Optional[str]) -> Optional[str]:
        """Mock get conversation history"""
        if not session_id or session_id not in self.sessions:
            return None

        messages = self.sessions[session_id]
        if not messages:
            return None

        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])


def create_mock_rag_system(
    vector_store_populated: bool = True,
    simulate_search_error: bool = False,
    simulate_ai_error: bool = False,
    simulate_tool_error: bool = False
):
    """Factory function to create a mock RAG system with various configurations"""
    from rag_system import RAGSystem
    from unittest.mock import patch

    mock_system = Mock(spec=RAGSystem)

    # Configure mock vector store
    mock_vector_store = MockVectorStore(
        populate_with_data=vector_store_populated,
        simulate_search_error=simulate_search_error
    )

    # Configure mock AI generator
    mock_ai_generator = Mock()
    mock_ai_generator.generate_response = Mock()

    if simulate_ai_error:
        mock_ai_generator.generate_response.side_effect = Exception("Simulated AI error")
    else:
        mock_ai_generator.generate_response.return_value = "Mock AI response"

    # Configure mock tool manager
    mock_tool_manager = MockToolManager(simulate_tool_error=simulate_tool_error)

    # Configure mock session manager
    mock_session_manager = MockSessionManager()

    # Set up the mock system
    mock_system.vector_store = mock_vector_store
    mock_system.ai_generator = mock_ai_generator
    mock_system.tool_manager = mock_tool_manager
    mock_system.session_manager = mock_session_manager

    return mock_system