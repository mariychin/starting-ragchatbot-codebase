"""
Integration tests for RAG system end-to-end functionality
"""
import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock
from rag_system import RAGSystem
from mocks import MockVectorStore, MockAnthropicClient, MockToolManager, create_mock_rag_system
from config import Config


class TestRAGSystemInitialization:
    """Test RAG system initialization and component setup"""

    def test_initialization_with_config(self):
        """Test RAG system initialization with config"""
        config = Config()
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        try:
            rag_system = RAGSystem(config)

            # Check all components are initialized
            assert rag_system.config is not None
            assert rag_system.document_processor is not None
            assert rag_system.vector_store is not None
            assert rag_system.ai_generator is not None
            assert rag_system.session_manager is not None
            assert rag_system.tool_manager is not None
            assert rag_system.search_tool is not None
            assert rag_system.outline_tool is not None

        except Exception as e:
            pytest.fail(f"RAG system initialization failed: {e}")

    def test_tool_registration(self):
        """Test that tools are properly registered"""
        config = Config()
        config.CHROMA_PATH = "./test_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        rag_system = RAGSystem(config)

        # Check tool definitions
        tool_definitions = rag_system.tool_manager.get_tool_definitions()
        assert len(tool_definitions) == 2  # search + outline tools

        tool_names = [tool["name"] for tool in tool_definitions]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names


class TestRAGSystemBasicQuery:
    """Test basic query processing functionality"""

    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_query_without_session(self, mock_vector_store_class, mock_ai_generator_class):
        """Test query processing without session"""
        # Setup mocks
        mock_vector_store = MockVectorStore(populate_with_data=True)
        mock_vector_store_class.return_value = mock_vector_store

        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Test AI response"
        mock_ai_generator_class.return_value = mock_ai_generator

        config = Config()
        config.CHROMA_PATH = "./test_chroma"

        rag_system = RAGSystem(config)

        # Execute query
        response, sources = rag_system.query("What is machine learning?")

        # Check response
        assert isinstance(response, str)
        assert len(response) > 0
        assert isinstance(sources, list)

    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_query_with_session(self, mock_vector_store_class, mock_ai_generator_class):
        """Test query processing with session"""
        # Setup mocks
        mock_vector_store = MockVectorStore(populate_with_data=True)
        mock_vector_store_class.return_value = mock_vector_store

        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Test AI response"
        mock_ai_generator_class.return_value = mock_ai_generator

        config = Config()
        rag_system = RAGSystem(config)

        # Create session
        session_id = rag_system.session_manager.create_session()

        # Execute query
        response, sources = rag_system.query("What is machine learning?", session_id)

        # Check response
        assert isinstance(response, str)
        assert isinstance(sources, list)

        # Check that session was used
        history = rag_system.session_manager.get_conversation_history(session_id)
        assert history is not None

    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_query_ai_generator_called_correctly(self, mock_vector_store_class, mock_ai_generator_class):
        """Test that AI generator is called with correct parameters"""
        # Setup mocks
        mock_vector_store = MockVectorStore(populate_with_data=True)
        mock_vector_store_class.return_value = mock_vector_store

        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Test AI response"
        mock_ai_generator_class.return_value = mock_ai_generator

        config = Config()
        rag_system = RAGSystem(config)

        # Execute query
        response, sources = rag_system.query("What is machine learning?")

        # Check that AI generator was called correctly
        mock_ai_generator.generate_response.assert_called_once()
        call_args = mock_ai_generator.generate_response.call_args

        # Check arguments
        assert 'query' in call_args.kwargs
        assert 'tools' in call_args.kwargs
        assert 'tool_manager' in call_args.kwargs
        assert call_args.kwargs['tool_manager'] is rag_system.tool_manager


class TestRAGSystemErrorHandling:
    """Test error handling in RAG system"""

    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_query_with_ai_error(self, mock_vector_store_class, mock_ai_generator_class):
        """Test query when AI generator fails"""
        mock_vector_store = MockVectorStore(populate_with_data=True)
        mock_vector_store_class.return_value = mock_vector_store

        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.side_effect = Exception("AI generation failed")
        mock_ai_generator_class.return_value = mock_ai_generator

        config = Config()
        rag_system = RAGSystem(config)

        # Should raise the exception
        with pytest.raises(Exception, match="AI generation failed"):
            rag_system.query("What is machine learning?")

    @patch('rag_system.AIGenerator')
    @patch('rag_system.VectorStore')
    def test_query_with_tool_error(self, mock_vector_store_class, mock_ai_generator_class):
        """Test query when tools fail"""
        mock_vector_store = MockVectorStore(simulate_search_error=True)
        mock_vector_store_class.return_value = mock_vector_store

        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Error response"
        mock_ai_generator_class.return_value = mock_ai_generator

        config = Config()
        rag_system = RAGSystem(config)

        # Should still return a response, even with tool errors
        response, sources = rag_system.query("What is machine learning?")
        assert isinstance(response, str)


class TestRAGSystemDocumentProcessing:
    """Test document processing functionality"""

    @patch('rag_system.VectorStore')
    def test_add_course_document(self, mock_vector_store_class):
        """Test adding a single course document"""
        mock_vector_store = Mock()
        mock_vector_store.add_course_metadata = Mock()
        mock_vector_store.add_course_content = Mock()
        mock_vector_store_class.return_value = mock_vector_store

        config = Config()
        rag_system = RAGSystem(config)

        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Course Title: Test Course\n")
            f.write("Course Link: https://example.com\n")
            f.write("Course Instructor: Test Instructor\n")
            f.write("\nLesson 1: Introduction\n")
            f.write("This is lesson content\n")
            temp_file = f.name

        try:
            course, chunk_count = rag_system.add_course_document(temp_file)

            assert course is not None
            assert course.title == "Test Course"
            assert chunk_count > 0

            # Check that vector store methods were called
            mock_vector_store.add_course_metadata.assert_called_once()
            mock_vector_store.add_course_content.assert_called_once()

        finally:
            import os
            os.unlink(temp_file)

    @patch('rag_system.VectorStore')
    def test_add_course_folder(self, mock_vector_store_class):
        """Test adding course folder"""
        mock_vector_store = Mock()
        mock_vector_store.add_course_metadata = Mock()
        mock_vector_store.add_course_content = Mock()
        mock_vector_store.get_existing_course_titles = Mock(return_value=[])
        mock_vector_store_class.return_value = mock_vector_store

        config = Config()
        rag_system = RAGSystem(config)

        # Create temporary directory with test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = f"{temp_dir}/test_course.txt"
            with open(test_file, 'w') as f:
                f.write("Course Title: Test Course\n")
                f.write("Course Link: https://example.com\n")
                f.write("Course Instructor: Test Instructor\n")
                f.write("\nLesson 1: Introduction\n")
                f.write("This is lesson content\n")

            courses_added, chunks_added = rag_system.add_course_folder(temp_dir)

            assert courses_added == 1
            assert chunks_added > 0


class TestRAGSystemAnalytics:
    """Test analytics functionality"""

    @patch('rag_system.VectorStore')
    def test_get_course_analytics(self, mock_vector_store_class):
        """Test getting course analytics"""
        mock_vector_store = Mock()
        mock_vector_store.get_course_count.return_value = 5
        mock_vector_store.get_existing_course_titles.return_value = ["Course A", "Course B"]
        mock_vector_store_class.return_value = mock_vector_store

        config = Config()
        rag_system = RAGSystem(config)

        analytics = rag_system.get_course_analytics()

        assert analytics["total_courses"] == 5
        assert analytics["course_titles"] == ["Course A", "Course B"]


class TestRAGSystemRealWorldScenarios:
    """Test real-world usage scenarios"""

    def test_content_search_query_scenario(self):
        """Test typical content search query scenario"""
        # This is the type of query that's failing according to the user
        mock_rag = create_mock_rag_system(vector_store_populated=True)

        # Simulate a content-related query
        try:
            response, sources = mock_rag.query("Explain machine learning algorithms")

            # Should not fail
            assert isinstance(response, str)
            assert isinstance(sources, list)

        except Exception as e:
            pytest.fail(f"Content search query failed: {e}")

    def test_outline_query_scenario(self):
        """Test outline query scenario"""
        mock_rag = create_mock_rag_system(vector_store_populated=True)

        # Simulate an outline query
        try:
            response, sources = mock_rag.query("What's in the machine learning course?")

            # Should not fail
            assert isinstance(response, str)
            assert isinstance(sources, list)

        except Exception as e:
            pytest.fail(f"Outline query failed: {e}")

    def test_empty_vector_store_scenario(self):
        """Test scenario with empty vector store"""
        mock_rag = create_mock_rag_system(vector_store_populated=False)

        try:
            response, sources = mock_rag.query("What is machine learning?")

            # Should still return a response, not fail
            assert isinstance(response, str)
            assert isinstance(sources, list)

        except Exception as e:
            pytest.fail(f"Empty vector store query failed: {e}")


class TestRAGSystemDiagnostics:
    """Comprehensive diagnostic tests to identify failure points"""

    def test_diagnose_component_initialization(self):
        """Test each component initialization individually"""
        config = Config()
        config.CHROMA_PATH = "./diagnostic_chroma"
        config.ANTHROPIC_API_KEY = "test-key"

        try:
            # Test document processor
            from document_processor import DocumentProcessor
            doc_processor = DocumentProcessor(config.CHUNK_SIZE, config.CHUNK_OVERLAP)
            assert doc_processor is not None

            # Test vector store
            from vector_store import VectorStore
            vector_store = VectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS)
            assert vector_store is not None

            # Test AI generator (without actual API key)
            from ai_generator import AIGenerator
            ai_gen = AIGenerator("test-key", config.ANTHROPIC_MODEL)
            assert ai_gen is not None

            # Test session manager
            from session_manager import SessionManager
            session_mgr = SessionManager(config.MAX_HISTORY)
            assert session_mgr is not None

        except Exception as e:
            pytest.fail(f"Component initialization diagnostic failed: {e}")

    def test_diagnose_tool_system(self):
        """Test tool system functionality"""
        try:
            from search_tools import ToolManager, CourseSearchTool, CourseOutlineTool
            from mocks import MockVectorStore

            # Test tool manager
            manager = ToolManager()
            assert manager is not None

            # Test search tool
            mock_store = MockVectorStore(populate_with_data=True)
            search_tool = CourseSearchTool(mock_store)
            assert search_tool is not None

            # Test outline tool
            outline_tool = CourseOutlineTool(mock_store)
            assert outline_tool is not None

            # Test registration
            manager.register_tool(search_tool)
            manager.register_tool(outline_tool)

            definitions = manager.get_tool_definitions()
            assert len(definitions) == 2

        except Exception as e:
            pytest.fail(f"Tool system diagnostic failed: {e}")

    @pytest.mark.integration
    def test_diagnose_real_rag_system(self):
        """Diagnostic test with real RAG system"""
        try:
            from config import config

            # Try to create real RAG system
            rag_system = RAGSystem(config)

            # Test basic functionality
            analytics = rag_system.get_course_analytics()
            print(f"Real RAG system analytics: {analytics}")

            # Try a simple query (this might fail, which is what we want to identify)
            try:
                response, sources = rag_system.query("test query")
                print(f"Query response: {response[:100]}...")
                print(f"Sources: {sources}")

            except Exception as query_error:
                print(f"Query execution failed: {query_error}")
                # This is the actual error we're trying to diagnose
                raise

        except Exception as e:
            # This will help us identify exactly where the failure occurs
            print(f"Real RAG system diagnostic failed at: {e}")
            raise

    def test_diagnose_tool_execution_pipeline(self):
        """Test the complete tool execution pipeline"""
        try:
            from search_tools import ToolManager, CourseSearchTool
            from mocks import MockVectorStore

            # Create components
            mock_store = MockVectorStore(populate_with_data=True)
            search_tool = CourseSearchTool(mock_store)
            tool_manager = ToolManager()

            # Register tool
            tool_manager.register_tool(search_tool)

            # Test tool definitions
            definitions = tool_manager.get_tool_definitions()
            assert len(definitions) == 1

            # Test tool execution
            result = tool_manager.execute_tool("search_course_content", query="test")
            assert isinstance(result, str)

            # Test source tracking
            sources = tool_manager.get_last_sources()
            assert isinstance(sources, list)

        except Exception as e:
            pytest.fail(f"Tool execution pipeline diagnostic failed: {e}")

    def test_diagnose_api_key_and_model(self):
        """Test API key and model configuration"""
        from config import config

        # Check if API key is configured
        if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "":
            pytest.fail("ANTHROPIC_API_KEY is not configured in environment")

        # Check model name
        assert config.ANTHROPIC_MODEL is not None
        assert len(config.ANTHROPIC_MODEL) > 0

        print(f"Using model: {config.ANTHROPIC_MODEL}")
        print(f"API key configured: {'Yes' if config.ANTHROPIC_API_KEY else 'No'}")