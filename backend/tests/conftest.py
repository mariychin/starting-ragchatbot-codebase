import pytest
import sys
import os
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Course, Lesson, CourseChunk
from vector_store import SearchResults
from config import Config

@pytest.fixture
def test_config():
    """Test configuration with safe defaults"""
    config = Config()
    config.CHROMA_PATH = "./test_chroma_db"
    config.ANTHROPIC_API_KEY = "test-key"
    config.CHUNK_SIZE = 100
    config.CHUNK_OVERLAP = 20
    config.MAX_RESULTS = 3
    return config

@pytest.fixture
def sample_course():
    """Sample course for testing"""
    return Course(
        title="Test Course",
        course_link="https://example.com/course",
        instructor="Test Instructor",
        lessons=[
            Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/lesson1"),
            Lesson(lesson_number=2, title="Advanced Topics", lesson_link="https://example.com/lesson2")
        ]
    )

@pytest.fixture
def sample_course_chunks():
    """Sample course chunks for testing"""
    return [
        CourseChunk(
            content="This is lesson 1 content about introduction",
            course_title="Test Course",
            lesson_number=1,
            chunk_index=0
        ),
        CourseChunk(
            content="This is lesson 2 content about advanced topics",
            course_title="Test Course",
            lesson_number=2,
            chunk_index=1
        )
    ]

@pytest.fixture
def empty_search_results():
    """Empty search results for testing"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )

@pytest.fixture
def populated_search_results():
    """Populated search results for testing"""
    return SearchResults(
        documents=["Test document 1", "Test document 2"],
        metadata=[
            {"course_title": "Test Course", "lesson_number": 1},
            {"course_title": "Test Course", "lesson_number": 2}
        ],
        distances=[0.1, 0.2]
    )

@pytest.fixture
def error_search_results():
    """Search results with error for testing"""
    return SearchResults.empty("Test error message")

@pytest.fixture
def mock_vector_store():
    """Mock vector store for isolated testing"""
    mock = Mock()
    mock.search = Mock()
    mock._resolve_course_name = Mock()
    mock.get_all_courses_metadata = Mock()
    mock.get_lesson_link = Mock()
    return mock

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for AI testing"""
    mock = Mock()
    mock.messages = Mock()
    mock.messages.create = Mock()
    return mock

@pytest.fixture
def mock_ai_response():
    """Mock AI response structure"""
    response = Mock()
    response.content = [Mock()]
    response.content[0].text = "Test AI response"
    response.stop_reason = "end_turn"
    return response

@pytest.fixture
def mock_tool_use_response():
    """Mock AI response with tool use"""
    response = Mock()

    # Create tool use content block
    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "test_tool_id"
    tool_block.input = {"query": "test query"}

    response.content = [tool_block]
    response.stop_reason = "tool_use"
    return response

@pytest.fixture
def sample_tool_definitions():
    """Sample tool definitions for testing"""
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
        },
        {
            "name": "get_course_outline",
            "description": "Get course outline",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_title": {"type": "string", "description": "Course title"}
                },
                "required": ["course_title"]
            }
        }
    ]

# Test data for various scenarios
TEST_QUERIES = [
    "What is machine learning?",
    "Explain the concept in lesson 1",
    "Show me the course outline",
    "What's in the Test Course?"
]

TEST_COURSE_NAMES = [
    "Test Course",
    "Machine Learning",
    "AI Fundamentals",
    "NonexistentCourse"
]