"""
API endpoint tests for the RAG system FastAPI application.

Tests the REST API endpoints for proper request/response handling,
error cases, and integration with the RAG system components.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json


@pytest.mark.api
class TestQueryEndpoint:
    """Test cases for the /api/query endpoint"""

    def test_query_with_session_id(self, client, mock_rag_system, sample_query_response):
        """Test query endpoint with provided session ID"""
        # Configure mock response
        mock_rag_system.query.return_value = (
            sample_query_response["answer"],
            sample_query_response["sources"]
        )

        # Make request
        response = client.post("/api/query", json={
            "query": "What is machine learning?",
            "session_id": "test-session-123"
        })

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == sample_query_response["answer"]
        assert data["sources"] == sample_query_response["sources"]
        assert data["session_id"] == "test-session-123"

        # Verify RAG system was called correctly
        mock_rag_system.query.assert_called_once_with(
            "What is machine learning?", "test-session-123"
        )

    def test_query_without_session_id(self, client, mock_rag_system, sample_query_response):
        """Test query endpoint without session ID - should create new session"""
        # Configure mock response
        mock_rag_system.query.return_value = (
            sample_query_response["answer"],
            sample_query_response["sources"]
        )

        # Make request without session_id
        response = client.post("/api/query", json={
            "query": "Explain neural networks"
        })

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == sample_query_response["answer"]
        assert data["session_id"] == "test-session-123"  # From mock

        # Verify session was created
        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with(
            "Explain neural networks", "test-session-123"
        )

    def test_query_with_string_sources(self, client, mock_rag_system):
        """Test query endpoint with string sources (backward compatibility)"""
        # Configure mock response with string sources
        mock_rag_system.query.return_value = (
            "Test answer",
            ["String source 1", "String source 2"]
        )

        response = client.post("/api/query", json={
            "query": "Test query",
            "session_id": "test-session"
        })

        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 2
        assert data["sources"][0] == {"text": "String source 1", "link": None}
        assert data["sources"][1] == {"text": "String source 2", "link": None}

    def test_query_missing_query_field(self, client):
        """Test query endpoint with missing query field"""
        response = client.post("/api/query", json={
            "session_id": "test-session"
        })

        assert response.status_code == 422  # Validation error

    def test_query_empty_query(self, client, mock_rag_system):
        """Test query endpoint with empty query string"""
        mock_rag_system.query.return_value = ("No results found", [])

        response = client.post("/api/query", json={
            "query": "",
            "session_id": "test-session"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "No results found"
        assert data["sources"] == []

    def test_query_rag_system_exception(self, client, mock_rag_system):
        """Test query endpoint when RAG system raises exception"""
        mock_rag_system.query.side_effect = Exception("RAG system error")

        response = client.post("/api/query", json={
            "query": "Test query",
            "session_id": "test-session"
        })

        assert response.status_code == 500
        assert "RAG system error" in response.json()["detail"]

    def test_query_invalid_json(self, client):
        """Test query endpoint with invalid JSON"""
        response = client.post("/api/query",
                             data="invalid json",
                             headers={"Content-Type": "application/json"})

        assert response.status_code == 422


@pytest.mark.api
class TestCoursesEndpoint:
    """Test cases for the /api/courses endpoint"""

    def test_get_courses_success(self, client, mock_rag_system, sample_course_analytics):
        """Test successful retrieval of course statistics"""
        mock_rag_system.get_course_analytics.return_value = sample_course_analytics

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 3
        assert data["course_titles"] == ["Test Course", "Machine Learning", "AI Fundamentals"]

        mock_rag_system.get_course_analytics.assert_called_once()

    def test_get_courses_empty(self, client, mock_rag_system):
        """Test course endpoint with no courses"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_courses_exception(self, client, mock_rag_system):
        """Test course endpoint when analytics raises exception"""
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert "Analytics error" in response.json()["detail"]


@pytest.mark.api
class TestRootEndpoint:
    """Test cases for the root endpoint"""

    def test_root_endpoint(self, client):
        """Test root endpoint returns basic message"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "RAG System API"


@pytest.mark.api
class TestCORSHeaders:
    """Test CORS middleware functionality"""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly set"""
        response = client.options("/api/query")

        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

    def test_preflight_request(self, client):
        """Test CORS preflight request handling"""
        response = client.options("/api/query", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        })

        assert response.status_code == 200


@pytest.mark.api
class TestErrorHandling:
    """Test error handling across endpoints"""

    def test_404_endpoint(self, client):
        """Test non-existent endpoint returns 404"""
        response = client.get("/api/nonexistent")

        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test wrong HTTP method returns 405"""
        response = client.get("/api/query")  # Should be POST

        assert response.status_code == 405

    def test_large_payload(self, client, mock_rag_system):
        """Test handling of large query payloads"""
        large_query = "A" * 10000  # 10KB query
        mock_rag_system.query.return_value = ("Large query processed", [])

        response = client.post("/api/query", json={
            "query": large_query,
            "session_id": "test-session"
        })

        assert response.status_code == 200
        mock_rag_system.query.assert_called_once_with(large_query, "test-session")


@pytest.mark.api
@pytest.mark.integration
class TestEndToEndWorkflow:
    """Integration tests for typical API workflows"""

    def test_complete_query_workflow(self, client, mock_rag_system):
        """Test complete workflow: get courses -> query -> get results"""
        # Setup mocks
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Course A", "Course B"]
        }
        mock_rag_system.query.return_value = (
            "Answer about Course A",
            [{"text": "Source from Course A", "link": "http://example.com"}]
        )

        # Step 1: Get available courses
        courses_response = client.get("/api/courses")
        assert courses_response.status_code == 200
        courses_data = courses_response.json()
        assert "Course A" in courses_data["course_titles"]

        # Step 2: Query about a specific course
        query_response = client.post("/api/query", json={
            "query": "Tell me about Course A"
        })
        assert query_response.status_code == 200
        query_data = query_response.json()
        assert "Course A" in query_data["answer"]
        assert len(query_data["sources"]) == 1

        # Verify session was created and used
        session_id = query_data["session_id"]
        assert session_id == "test-session-123"

    def test_session_continuity(self, client, mock_rag_system):
        """Test that session ID is maintained across requests"""
        mock_rag_system.query.return_value = ("Response", [])

        # First query - get session ID
        response1 = client.post("/api/query", json={
            "query": "First question"
        })
        session_id = response1.json()["session_id"]

        # Second query - use same session ID
        response2 = client.post("/api/query", json={
            "query": "Follow-up question",
            "session_id": session_id
        })

        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

        # Verify RAG system was called with correct session
        assert mock_rag_system.query.call_count == 2
        calls = mock_rag_system.query.call_args_list
        assert calls[0][0][1] == session_id  # First call
        assert calls[1][0][1] == session_id  # Second call