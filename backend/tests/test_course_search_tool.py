"""
Comprehensive tests for CourseSearchTool to diagnose content query failures
"""
import pytest
from unittest.mock import Mock, patch
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults
from mocks import MockVectorStore


class TestCourseSearchToolBasic:
    """Test basic CourseSearchTool functionality"""

    def test_tool_definition_format(self):
        """Test that tool definition has correct format for Anthropic API"""
        mock_store = MockVectorStore()
        tool = CourseSearchTool(mock_store)

        definition = tool.get_tool_definition()

        # Check required fields
        assert "name" in definition
        assert "description" in definition
        assert "input_schema" in definition

        # Check name and description
        assert definition["name"] == "search_course_content"
        assert isinstance(definition["description"], str)
        assert len(definition["description"]) > 0

        # Check input schema structure
        schema = definition["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Check required parameters
        assert "query" in schema["required"]
        assert "query" in schema["properties"]

    def test_execute_with_simple_query_success(self):
        """Test successful execution with simple query"""
        mock_store = MockVectorStore(populate_with_data=True)
        tool = CourseSearchTool(mock_store)

        result = tool.execute(query="machine learning")

        # Should return formatted result, not error
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        assert "error" not in result.lower() or "failed" not in result.lower()

        # Check that vector store was called
        assert mock_store.last_search_query == "machine learning"

    def test_execute_with_empty_vector_store(self):
        """Test execution when vector store is empty"""
        mock_store = MockVectorStore(populate_with_data=False)
        tool = CourseSearchTool(mock_store)

        result = tool.execute(query="machine learning")

        # Should return "no content found" message
        assert "No relevant content found" in result

    def test_execute_with_vector_store_error(self):
        """Test execution when vector store returns error"""
        mock_store = MockVectorStore(simulate_search_error=True)
        tool = CourseSearchTool(mock_store)

        result = tool.execute(query="machine learning")

        # Should return the error message
        assert "Simulated search error" in result


class TestCourseSearchToolWithFilters:
    """Test CourseSearchTool with course and lesson filters"""

    def test_execute_with_course_filter(self):
        """Test execution with course name filter"""
        mock_store = MockVectorStore(populate_with_data=True)
        tool = CourseSearchTool(mock_store)

        result = tool.execute(query="machine learning", course_name="Test Course")

        # Check that parameters were passed correctly
        assert mock_store.last_search_params["course_name"] == "Test Course"
        assert isinstance(result, str)

    def test_execute_with_lesson_filter(self):
        """Test execution with lesson number filter"""
        mock_store = MockVectorStore(populate_with_data=True)
        tool = CourseSearchTool(mock_store)

        result = tool.execute(query="machine learning", lesson_number=1)

        # Check that parameters were passed correctly
        assert mock_store.last_search_params["lesson_number"] == 1
        assert isinstance(result, str)

    def test_execute_with_both_filters(self):
        """Test execution with both course and lesson filters"""
        mock_store = MockVectorStore(populate_with_data=True)
        tool = CourseSearchTool(mock_store)

        result = tool.execute(query="machine learning", course_name="Test Course", lesson_number=1)

        # Check that both parameters were passed
        assert mock_store.last_search_params["course_name"] == "Test Course"
        assert mock_store.last_search_params["lesson_number"] == 1
        assert isinstance(result, str)

    def test_execute_with_invalid_course_name(self):
        """Test execution with non-existent course name"""
        mock_store = MockVectorStore(populate_with_data=True)
        # Override course resolution to return None
        mock_store._resolve_course_name = Mock(return_value=None)
        tool = CourseSearchTool(mock_store)

        result = tool.execute(query="machine learning", course_name="NonexistentCourse")

        # Should indicate course not found
        assert "No relevant content found in course 'NonexistentCourse'" in result


class TestCourseSearchToolResultFormatting:
    """Test result formatting and source tracking"""

    def test_result_formatting_with_sources(self):
        """Test that results are properly formatted with source information"""
        # Create mock with specific search results
        mock_store = Mock()
        search_results = SearchResults(
            documents=["Test document content"],
            metadata=[{"course_title": "Test Course", "lesson_number": 1}],
            distances=[0.1]
        )
        mock_store.search.return_value = search_results
        mock_store.get_lesson_link.return_value = "https://example.com/lesson1"

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test query")

        # Check formatting
        assert "[Test Course - Lesson 1]" in result
        assert "Test document content" in result

        # Check source tracking
        assert len(tool.last_sources) == 1
        source = tool.last_sources[0]
        assert source["text"] == "Test Course - Lesson 1"
        assert source["link"] == "https://example.com/lesson1"

    def test_result_formatting_without_lesson(self):
        """Test formatting when no lesson number is available"""
        mock_store = Mock()
        search_results = SearchResults(
            documents=["Test document content"],
            metadata=[{"course_title": "Test Course", "lesson_number": None}],
            distances=[0.1]
        )
        mock_store.search.return_value = search_results

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test query")

        # Should format without lesson number
        assert "[Test Course]" in result
        assert "Test document content" in result

    def test_multiple_results_formatting(self):
        """Test formatting with multiple search results"""
        mock_store = Mock()
        search_results = SearchResults(
            documents=["Document 1", "Document 2"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2}
            ],
            distances=[0.1, 0.2]
        )
        mock_store.search.return_value = search_results
        mock_store.get_lesson_link.return_value = None

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test query")

        # Should contain both results
        assert "[Course A - Lesson 1]" in result
        assert "[Course B - Lesson 2]" in result
        assert "Document 1" in result
        assert "Document 2" in result

        # Should track multiple sources
        assert len(tool.last_sources) == 2


class TestCourseSearchToolIntegration:
    """Integration tests with real components"""

    def test_with_real_vector_store_empty(self):
        """Test with real VectorStore that has no data"""
        from vector_store import VectorStore
        from config import config

        # Create a temporary vector store
        test_store = VectorStore("./test_empty_chroma", config.EMBEDDING_MODEL, 3)
        try:
            # Clear any existing data
            test_store.clear_all_data()

            tool = CourseSearchTool(test_store)
            result = tool.execute(query="machine learning")

            # Should indicate no content found
            assert "No relevant content found" in result

        finally:
            # Clean up
            try:
                test_store.clear_all_data()
            except:
                pass

    @pytest.mark.integration
    def test_with_real_vector_store_with_data(self):
        """Integration test with real vector store and sample data"""
        from vector_store import VectorStore
        from config import config
        from models import Course, Lesson, CourseChunk

        # Create a temporary vector store
        test_store = VectorStore("./test_populated_chroma", config.EMBEDDING_MODEL, 3)
        try:
            # Clear and add test data
            test_store.clear_all_data()

            # Add sample course metadata
            test_course = Course(
                title="Integration Test Course",
                course_link="https://example.com/course",
                instructor="Test Instructor",
                lessons=[
                    Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/lesson1")
                ]
            )
            test_store.add_course_metadata(test_course)

            # Add sample content
            test_chunks = [
                CourseChunk(
                    content="This is a test lesson about machine learning fundamentals",
                    course_title="Integration Test Course",
                    lesson_number=1,
                    chunk_index=0
                )
            ]
            test_store.add_course_content(test_chunks)

            # Test the search tool
            tool = CourseSearchTool(test_store)
            result = tool.execute(query="machine learning")

            # Should find the content
            assert isinstance(result, str)
            assert len(result) > 0
            # The exact content depends on the search algorithm, but it should not be an error
            assert not any(error_word in result.lower() for error_word in ["error", "failed", "no relevant content"])

        finally:
            # Clean up
            try:
                test_store.clear_all_data()
            except:
                pass


class TestToolManagerIntegration:
    """Test CourseSearchTool integration with ToolManager"""

    def test_tool_registration(self):
        """Test that CourseSearchTool can be registered with ToolManager"""
        mock_store = MockVectorStore()
        tool = CourseSearchTool(mock_store)
        manager = ToolManager()

        # Register the tool
        manager.register_tool(tool)

        # Check that it's registered
        definitions = manager.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["name"] == "search_course_content"

    def test_tool_execution_through_manager(self):
        """Test executing the tool through ToolManager"""
        mock_store = MockVectorStore(populate_with_data=True)
        tool = CourseSearchTool(mock_store)
        manager = ToolManager()

        manager.register_tool(tool)

        # Execute through manager
        result = manager.execute_tool("search_course_content", query="machine learning")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_source_tracking_through_manager(self):
        """Test that sources are tracked correctly through ToolManager"""
        mock_store = MockVectorStore(populate_with_data=True)
        tool = CourseSearchTool(mock_store)
        manager = ToolManager()

        manager.register_tool(tool)

        # Execute search
        result = manager.execute_tool("search_course_content", query="machine learning")

        # Check sources
        sources = manager.get_last_sources()
        assert len(sources) > 0
        assert all(isinstance(source, dict) for source in sources)
        assert all("text" in source for source in sources)


# Diagnostic test to identify common failure points
class TestCourseSearchToolDiagnostics:
    """Diagnostic tests to identify common failure patterns"""

    def test_diagnose_vector_store_connection(self):
        """Test if vector store can be accessed"""
        try:
            from vector_store import VectorStore
            from config import config

            # Try to create a vector store
            store = VectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS)
            tool = CourseSearchTool(store)

            # This should not raise an exception
            definition = tool.get_tool_definition()
            assert definition is not None

        except Exception as e:
            pytest.fail(f"Vector store connection failed: {e}")

    def test_diagnose_search_functionality(self):
        """Test basic search functionality with real vector store"""
        try:
            from vector_store import VectorStore
            from config import config

            store = VectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS)
            tool = CourseSearchTool(store)

            # Try a simple search
            result = tool.execute(query="test")

            # Should return a string result, not raise an exception
            assert isinstance(result, str)

        except Exception as e:
            pytest.fail(f"Search functionality failed: {e}")

    def test_diagnose_course_resolution(self):
        """Test course name resolution functionality"""
        try:
            from vector_store import VectorStore
            from config import config

            store = VectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS)

            # Try to resolve a course name
            resolved = store._resolve_course_name("test")

            # Should return either a string or None, not raise an exception
            assert resolved is None or isinstance(resolved, str)

        except Exception as e:
            pytest.fail(f"Course resolution failed: {e}")