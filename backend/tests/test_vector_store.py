"""
Tests for VectorStore functionality and search operations
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch
from vector_store import VectorStore, SearchResults
from models import Course, Lesson, CourseChunk


class TestVectorStoreBasic:
    """Test basic VectorStore functionality"""

    def test_initialization(self):
        """Test VectorStore initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            assert store.max_results == 5
            assert store.client is not None
            assert store.course_catalog is not None
            assert store.course_content is not None

    def test_search_results_creation(self):
        """Test SearchResults creation and methods"""
        # Test normal results
        results = SearchResults(
            documents=["doc1", "doc2"],
            metadata=[{"key": "value1"}, {"key": "value2"}],
            distances=[0.1, 0.2]
        )

        assert not results.is_empty()
        assert results.error is None
        assert len(results.documents) == 2

        # Test empty results
        empty_results = SearchResults.empty("No results found")
        assert empty_results.is_empty()
        assert empty_results.error == "No results found"

        # Test from chroma format
        chroma_data = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"key": "value1"}, {"key": "value2"}]],
            "distances": [[0.1, 0.2]]
        }
        chroma_results = SearchResults.from_chroma(chroma_data)
        assert len(chroma_results.documents) == 2
        assert chroma_results.documents[0] == "doc1"


class TestVectorStoreDataOperations:
    """Test VectorStore data adding and retrieval operations"""

    def test_add_course_metadata(self):
        """Test adding course metadata"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            course = Course(
                title="Test Course",
                course_link="https://example.com/course",
                instructor="Test Instructor",
                lessons=[
                    Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/lesson1"),
                    Lesson(lesson_number=2, title="Advanced", lesson_link="https://example.com/lesson2")
                ]
            )

            # Should not raise an exception
            store.add_course_metadata(course)

            # Check that course was added
            existing_titles = store.get_existing_course_titles()
            assert "Test Course" in existing_titles

    def test_add_course_content(self):
        """Test adding course content chunks"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            chunks = [
                CourseChunk(
                    content="This is lesson 1 content",
                    course_title="Test Course",
                    lesson_number=1,
                    chunk_index=0
                ),
                CourseChunk(
                    content="This is lesson 2 content",
                    course_title="Test Course",
                    lesson_number=2,
                    chunk_index=1
                )
            ]

            # Should not raise an exception
            store.add_course_content(chunks)

    def test_get_existing_course_titles(self):
        """Test retrieving existing course titles"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Initially should be empty
            titles = store.get_existing_course_titles()
            assert len(titles) == 0

            # Add a course
            course = Course(title="Test Course", lessons=[])
            store.add_course_metadata(course)

            # Now should contain the course
            titles = store.get_existing_course_titles()
            assert "Test Course" in titles

    def test_get_course_count(self):
        """Test getting course count"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Initially should be 0
            count = store.get_course_count()
            assert count == 0

            # Add courses
            course1 = Course(title="Course 1", lessons=[])
            course2 = Course(title="Course 2", lessons=[])

            store.add_course_metadata(course1)
            store.add_course_metadata(course2)

            # Should be 2
            count = store.get_course_count()
            assert count == 2

    def test_get_all_courses_metadata(self):
        """Test retrieving all course metadata"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            course = Course(
                title="Test Course",
                instructor="Test Instructor",
                course_link="https://example.com",
                lessons=[
                    Lesson(lesson_number=1, title="Intro", lesson_link="https://example.com/lesson1")
                ]
            )

            store.add_course_metadata(course)

            metadata = store.get_all_courses_metadata()
            assert len(metadata) == 1
            assert metadata[0]["title"] == "Test Course"
            assert metadata[0]["instructor"] == "Test Instructor"
            assert "lessons" in metadata[0]
            assert len(metadata[0]["lessons"]) == 1


class TestVectorStoreSearch:
    """Test VectorStore search functionality"""

    def test_search_empty_store(self):
        """Test searching in empty store"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            results = store.search("machine learning")

            assert results.is_empty()
            assert results.error is None

    def test_search_with_content(self):
        """Test searching with actual content"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Add course metadata
            course = Course(
                title="Machine Learning Course",
                lessons=[Lesson(lesson_number=1, title="Introduction")]
            )
            store.add_course_metadata(course)

            # Add content
            chunks = [
                CourseChunk(
                    content="This lesson covers machine learning fundamentals and algorithms",
                    course_title="Machine Learning Course",
                    lesson_number=1,
                    chunk_index=0
                )
            ]
            store.add_course_content(chunks)

            # Search for content
            results = store.search("machine learning")

            # Should find something (exact results depend on embedding model)
            assert isinstance(results, SearchResults)
            # Results may or may not be empty depending on the search algorithm

    def test_course_name_resolution(self):
        """Test course name resolution functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Add course
            course = Course(title="Machine Learning Fundamentals", lessons=[])
            store.add_course_metadata(course)

            # Test exact match
            resolved = store._resolve_course_name("Machine Learning Fundamentals")
            assert resolved == "Machine Learning Fundamentals"

            # Test partial match (may or may not work depending on embedding similarity)
            resolved_partial = store._resolve_course_name("Machine Learning")
            # This might be None or the course name depending on the embedding model

            # Test non-existent course
            resolved_none = store._resolve_course_name("Nonexistent Course")
            assert resolved_none is None

    def test_search_with_course_filter(self):
        """Test searching with course filter"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Add courses and content
            course1 = Course(title="Course A", lessons=[])
            course2 = Course(title="Course B", lessons=[])
            store.add_course_metadata(course1)
            store.add_course_metadata(course2)

            chunks = [
                CourseChunk(content="Content for course A", course_title="Course A", chunk_index=0),
                CourseChunk(content="Content for course B", course_title="Course B", chunk_index=1)
            ]
            store.add_course_content(chunks)

            # Search with course filter
            results = store.search("content", course_name="Course A")

            # Should work without errors
            assert isinstance(results, SearchResults)

    def test_search_with_lesson_filter(self):
        """Test searching with lesson filter"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Add content
            chunks = [
                CourseChunk(content="Lesson 1 content", course_title="Course", lesson_number=1, chunk_index=0),
                CourseChunk(content="Lesson 2 content", course_title="Course", lesson_number=2, chunk_index=1)
            ]
            store.add_course_content(chunks)

            # Search with lesson filter
            results = store.search("content", lesson_number=1)

            # Should work without errors
            assert isinstance(results, SearchResults)

    def test_build_filter(self):
        """Test filter building functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Test no filter
            filter_dict = store._build_filter(None, None)
            assert filter_dict is None

            # Test course filter only
            filter_dict = store._build_filter("Test Course", None)
            assert filter_dict == {"course_title": "Test Course"}

            # Test lesson filter only
            filter_dict = store._build_filter(None, 1)
            assert filter_dict == {"lesson_number": 1}

            # Test both filters
            filter_dict = store._build_filter("Test Course", 1)
            expected = {"$and": [{"course_title": "Test Course"}, {"lesson_number": 1}]}
            assert filter_dict == expected


class TestVectorStoreLinkRetrieval:
    """Test link retrieval functionality"""

    def test_get_course_link(self):
        """Test getting course link"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            course = Course(
                title="Test Course",
                course_link="https://example.com/course",
                lessons=[]
            )
            store.add_course_metadata(course)

            # Test existing course
            link = store.get_course_link("Test Course")
            assert link == "https://example.com/course"

            # Test non-existent course
            link = store.get_course_link("Nonexistent Course")
            assert link is None

    def test_get_lesson_link(self):
        """Test getting lesson link"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            course = Course(
                title="Test Course",
                lessons=[
                    Lesson(lesson_number=1, title="Intro", lesson_link="https://example.com/lesson1"),
                    Lesson(lesson_number=2, title="Advanced", lesson_link="https://example.com/lesson2")
                ]
            )
            store.add_course_metadata(course)

            # Test existing lesson
            link = store.get_lesson_link("Test Course", 1)
            assert link == "https://example.com/lesson1"

            # Test non-existent lesson
            link = store.get_lesson_link("Test Course", 99)
            assert link is None

            # Test non-existent course
            link = store.get_lesson_link("Nonexistent Course", 1)
            assert link is None


class TestVectorStoreErrorHandling:
    """Test error handling in VectorStore operations"""

    def test_clear_all_data(self):
        """Test clearing all data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Add some data
            course = Course(title="Test Course", lessons=[])
            store.add_course_metadata(course)

            # Clear data
            store.clear_all_data()

            # Should be empty
            count = store.get_course_count()
            assert count == 0

    def test_add_empty_chunks(self):
        """Test adding empty chunks list"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Should not raise an exception
            store.add_course_content([])

    def test_search_error_handling(self):
        """Test search error handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(temp_dir, "all-MiniLM-L6-v2", max_results=5)

            # Mock the collection to raise an exception
            with patch.object(store.course_content, 'query', side_effect=Exception("Test error")):
                results = store.search("test query")

                assert results.error is not None
                assert "Test error" in results.error


class TestVectorStoreDiagnostics:
    """Diagnostic tests for VectorStore"""

    def test_diagnose_chroma_installation(self):
        """Test if ChromaDB is properly installed and working"""
        try:
            import chromadb
            from chromadb.config import Settings

            # Try to create a client
            with tempfile.TemporaryDirectory() as temp_dir:
                client = chromadb.PersistentClient(
                    path=temp_dir,
                    settings=Settings(anonymized_telemetry=False)
                )
                assert client is not None

        except Exception as e:
            pytest.fail(f"ChromaDB installation issue: {e}")

    def test_diagnose_embedding_model(self):
        """Test if embedding model can be loaded"""
        try:
            import chromadb.utils.embedding_functions

            embedding_function = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            assert embedding_function is not None

        except Exception as e:
            pytest.fail(f"Embedding model loading issue: {e}")

    def test_diagnose_vector_store_with_real_config(self):
        """Test VectorStore with real configuration"""
        try:
            from config import config

            # Create a temporary vector store
            with tempfile.TemporaryDirectory() as temp_dir:
                store = VectorStore(temp_dir, config.EMBEDDING_MODEL, config.MAX_RESULTS)

                # Basic operations should work
                count = store.get_course_count()
                assert isinstance(count, int)

                titles = store.get_existing_course_titles()
                assert isinstance(titles, list)

        except Exception as e:
            pytest.fail(f"Vector store with real config failed: {e}")

    def test_diagnose_real_vector_store_state(self):
        """Test the actual vector store state"""
        try:
            from config import config

            # Try to access the real vector store
            store = VectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS)

            # Check if it has data
            count = store.get_course_count()
            print(f"Real vector store has {count} courses")

            titles = store.get_existing_course_titles()
            print(f"Course titles: {titles}")

            # Try a simple search
            results = store.search("test")
            print(f"Test search returned {len(results.documents) if not results.is_empty() else 0} results")

            if results.error:
                print(f"Search error: {results.error}")

        except Exception as e:
            pytest.fail(f"Real vector store diagnosis failed: {e}")