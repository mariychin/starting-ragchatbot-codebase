"""
Tests for AIGenerator tool calling and response generation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from ai_generator import AIGenerator
from mocks import MockAnthropicClient, MockToolManager, EnhancedMockAnthropicClient


class TestAIGeneratorBasic:
    """Test basic AIGenerator functionality"""

    def test_initialization(self):
        """Test AIGenerator initialization"""
        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")

        assert generator.model == "claude-3-sonnet-20240229"
        assert generator.base_params["model"] == "claude-3-sonnet-20240229"
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800

    def test_system_prompt_content(self):
        """Test that system prompt contains required tool guidance"""
        system_prompt = AIGenerator.SYSTEM_PROMPT

        # Check for tool usage guidelines
        assert "search_course_content" in system_prompt
        assert "get_course_outline" in system_prompt
        assert "Tool Usage Guidelines" in system_prompt

        # Check for response protocol
        assert "Response Protocol" in system_prompt
        assert "General knowledge questions" in system_prompt
        assert "Course content questions" in system_prompt
        assert "Course outline/structure questions" in system_prompt


class TestAIGeneratorWithoutTools:
    """Test AIGenerator without tool calling"""

    @patch('anthropic.Anthropic')
    def test_generate_response_without_tools(self, mock_anthropic_class):
        """Test generating response without tools"""
        # Setup mock client
        mock_client = MockAnthropicClient(simulate_tool_use=False, custom_response="Test response")
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        result = generator.generate_response(query="What is 2+2?")

        assert result == "Test response"
        assert mock_client.call_count == 1

    @patch('anthropic.Anthropic')
    def test_generate_response_with_conversation_history(self, mock_anthropic_class):
        """Test generating response with conversation history"""
        mock_client = MockAnthropicClient(custom_response="Response with history")
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        history = "User: Previous question\nAssistant: Previous answer"
        result = generator.generate_response(
            query="Follow-up question",
            conversation_history=history
        )

        assert result == "Response with history"
        # Check that history was included in system prompt
        assert history in mock_client.last_request_params["system"]

    @patch('anthropic.Anthropic')
    def test_api_error_handling(self, mock_anthropic_class):
        """Test handling of API errors"""
        mock_client = MockAnthropicClient(simulate_api_error=True)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        with pytest.raises(Exception, match="Simulated API error"):
            generator.generate_response(query="Test query")


class TestAIGeneratorWithTools:
    """Test AIGenerator with tool calling functionality"""

    @patch('anthropic.Anthropic')
    def test_generate_response_with_tools_no_tool_use(self, mock_anthropic_class):
        """Test response generation with tools available but not used"""
        mock_client = MockAnthropicClient(simulate_tool_use=False, custom_response="Direct response")
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager()
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="What is machine learning?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        assert result == "Direct response"
        # Should have tools in the request
        assert "tools" in mock_client.last_request_params
        # But no tool execution should occur
        assert mock_tool_manager.last_tool_name is None

    @patch('anthropic.Anthropic')
    def test_generate_response_with_tool_use(self, mock_anthropic_class):
        """Test response generation with tool use"""
        # First call returns tool use, second call returns final response
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock the first response (tool use)
        first_response = Mock()
        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.name = "search_course_content"
        tool_block.id = "tool_123"
        tool_block.input = {"query": "machine learning"}

        first_response.content = [tool_block]
        first_response.stop_reason = "tool_use"

        # Mock the second response (final answer)
        second_response = Mock()
        text_block = Mock()
        text_block.text = "Final AI response based on tool results"
        second_response.content = [text_block]
        second_response.stop_reason = "end_turn"

        # Configure the mock to return different responses on consecutive calls
        mock_client.messages.create.side_effect = [first_response, second_response]

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager(mock_search_result="Tool search result")
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="Tell me about machine learning",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        assert result == "Final AI response based on tool results"
        # Tool should have been executed
        assert mock_tool_manager.last_tool_name == "search_course_content"
        assert mock_tool_manager.last_tool_params == {"query": "machine learning"}
        # Should have made two API calls
        assert mock_client.messages.create.call_count == 2

    @patch('anthropic.Anthropic')
    def test_tool_execution_error_handling(self, mock_anthropic_class):
        """Test handling of tool execution errors"""
        # Mock tool use response
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_response = Mock()
        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.name = "search_course_content"
        tool_block.id = "tool_123"
        tool_block.input = {"query": "test"}

        tool_response.content = [tool_block]
        tool_response.stop_reason = "tool_use"

        final_response = Mock()
        text_block = Mock()
        text_block.text = "Response despite tool error"
        final_response.content = [text_block]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        # Tool manager that simulates error
        mock_tool_manager = MockToolManager(simulate_tool_error=True)
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="Test query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should still return a response even if tool fails
        assert result == "Response despite tool error"


class TestAIGeneratorToolIntegration:
    """Test AIGenerator integration with real tool components"""

    def test_with_real_tool_definitions(self):
        """Test with real tool definitions from CourseSearchTool"""
        from search_tools import CourseSearchTool
        from mocks import MockVectorStore

        mock_store = MockVectorStore()
        search_tool = CourseSearchTool(mock_store)
        tool_definition = search_tool.get_tool_definition()

        # Mock the client to avoid actual API calls
        with patch('anthropic.Anthropic') as mock_anthropic_class:
            mock_client = MockAnthropicClient(custom_response="Test response")
            mock_anthropic_class.return_value = mock_client

            generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
            generator.client = mock_client

            result = generator.generate_response(
                query="Test query",
                tools=[tool_definition]
            )

            assert result == "Test response"
            # Should have valid tool definition in request
            tools_in_request = mock_client.last_request_params.get("tools", [])
            assert len(tools_in_request) == 1
            assert tools_in_request[0]["name"] == "search_course_content"

    def test_with_multiple_tools(self):
        """Test with multiple tool definitions"""
        from search_tools import CourseSearchTool, CourseOutlineTool
        from mocks import MockVectorStore

        mock_store = MockVectorStore()
        search_tool = CourseSearchTool(mock_store)
        outline_tool = CourseOutlineTool(mock_store)

        tools = [search_tool.get_tool_definition(), outline_tool.get_tool_definition()]

        with patch('anthropic.Anthropic') as mock_anthropic_class:
            mock_client = MockAnthropicClient(custom_response="Multi-tool response")
            mock_anthropic_class.return_value = mock_client

            generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
            generator.client = mock_client

            result = generator.generate_response(
                query="Test query",
                tools=tools
            )

            assert result == "Multi-tool response"
            # Should have both tools available
            tools_in_request = mock_client.last_request_params.get("tools", [])
            assert len(tools_in_request) == 2
            tool_names = [tool["name"] for tool in tools_in_request]
            assert "search_course_content" in tool_names
            assert "get_course_outline" in tool_names


class TestAIGeneratorDiagnostics:
    """Diagnostic tests to identify common AI generator issues"""

    def test_diagnose_anthropic_client_creation(self):
        """Test if Anthropic client can be created"""
        try:
            generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
            assert generator.client is not None
        except Exception as e:
            pytest.fail(f"Anthropic client creation failed: {e}")

    def test_diagnose_system_prompt_validity(self):
        """Test if system prompt is valid and contains required elements"""
        system_prompt = AIGenerator.SYSTEM_PROMPT

        # Check basic structure
        assert isinstance(system_prompt, str)
        assert len(system_prompt) > 0

        # Check for required elements
        required_elements = [
            "search_course_content",
            "get_course_outline",
            "Tool Usage Guidelines",
            "Response Protocol"
        ]

        for element in required_elements:
            assert element in system_prompt, f"Missing required element: {element}"

    @patch('anthropic.Anthropic')
    def test_diagnose_basic_request_format(self, mock_anthropic_class):
        """Test if basic API request format is correct"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Test response"
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        try:
            result = generator.generate_response(query="Test query")

            # Check that request was made with correct format
            call_args = mock_client.messages.create.call_args[1]
            assert "model" in call_args
            assert "messages" in call_args
            assert "system" in call_args
            assert len(call_args["messages"]) == 1
            assert call_args["messages"][0]["role"] == "user"

        except Exception as e:
            pytest.fail(f"Basic request formatting failed: {e}")

    @patch('anthropic.Anthropic')
    def test_diagnose_tool_request_format(self, mock_anthropic_class):
        """Test if tool request format is correct"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Test response"
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        sample_tools = [{
            "name": "test_tool",
            "description": "Test tool",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }]

        try:
            result = generator.generate_response(
                query="Test query",
                tools=sample_tools
            )

            # Check that request includes tools
            call_args = mock_client.messages.create.call_args[1]
            assert "tools" in call_args
            assert "tool_choice" in call_args
            assert len(call_args["tools"]) == 1
            assert call_args["tools"][0]["name"] == "test_tool"

        except Exception as e:
            pytest.fail(f"Tool request formatting failed: {e}")


class TestSequentialToolCalling:
    """Test sequential tool calling functionality"""

    @patch('anthropic.Anthropic')
    def test_single_tool_call_termination(self, mock_anthropic_class):
        """Verify that when Claude makes one tool call and returns a text response, it terminates correctly"""
        response_sequence = [
            {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test"}},
            {"type": "text", "content": "Final response after tool use"}
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager(mock_search_result="Tool result")
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="Test query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify external behavior
        assert result == "Final response after tool use"
        assert mock_client.call_count == 2  # Tool call + final response
        assert mock_tool_manager.execution_count == 1
        assert mock_tool_manager.execution_history[0]["tool_name"] == "search_course_content"

    @patch('anthropic.Anthropic')
    def test_two_round_sequential_calls(self, mock_anthropic_class):
        """Test full 2-round scenario (outline → search → final response)"""
        response_sequence = [
            {"type": "tool_use", "tool": "get_course_outline", "params": {"course_name": "Course A"}},
            {"type": "tool_use", "tool": "search_course_content", "params": {"query": "introduction"}},
            {"type": "text", "content": "Comprehensive response based on both tools"}
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager(mock_search_result="Tool result")
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="Compare courses",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify external behavior
        assert result == "Comprehensive response based on both tools"
        assert mock_client.call_count == 3  # Two tool calls + final response
        assert mock_tool_manager.execution_count == 2

        # Verify tool execution order
        assert mock_tool_manager.execution_history[0]["tool_name"] == "get_course_outline"
        assert mock_tool_manager.execution_history[1]["tool_name"] == "search_course_content"

        # Verify conversation context grows correctly
        mock_client.verify_message_context(0, 1)  # Initial: just user query
        mock_client.verify_message_context(1, 3)  # After round 1: user + assistant + tool result
        mock_client.verify_message_context(2, 5)  # After round 2: + assistant + tool result

    @patch('anthropic.Anthropic')
    def test_max_rounds_termination(self, mock_anthropic_class):
        """Verify termination after exactly 2 tool rounds"""
        response_sequence = [
            {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test1"}},
            {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test2"}},
            {"type": "text", "content": "Final summary after max rounds"}
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager(mock_search_result="Tool result")
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="Complex query requiring multiple searches",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should stop after 2 rounds regardless of more tool requests
        assert mock_client.call_count == 3  # 2 tool rounds + final summary call
        assert mock_tool_manager.execution_count == 2  # Only 2 tools executed
        assert result == "Final summary after max rounds"

    @patch('anthropic.Anthropic')
    def test_no_tools_termination(self, mock_anthropic_class):
        """Test termination when Claude responds without tools"""
        response_sequence = [
            {"type": "text", "content": "Direct answer without tools"}
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager()
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="Simple question",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should terminate immediately
        assert mock_client.call_count == 1
        assert mock_tool_manager.execution_count == 0
        assert result == "Direct answer without tools"

    @patch('anthropic.Anthropic')
    def test_conversation_context_preservation(self, mock_anthropic_class):
        """Verify that conversation history is maintained across rounds"""
        response_sequence = [
            {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test"}},
            {"type": "text", "content": "Response with context"}
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager()
        tools = mock_tool_manager.get_tool_definitions()

        history = "User: Previous question\nAssistant: Previous answer"
        result = generator.generate_response(
            query="Follow-up question",
            conversation_history=history,
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Check that history was included in system prompt for all calls
        for call_params in mock_client.call_history:
            assert history in call_params["system"]

        assert result == "Response with context"


class TestSequentialToolErrorHandling:
    """Test error scenarios and graceful degradation"""

    @patch('anthropic.Anthropic')
    def test_first_round_tool_error_recovery(self, mock_anthropic_class):
        """Tool fails in first round, should handle gracefully"""
        response_sequence = [
            {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test"}},
            {"type": "text", "content": "Response despite tool error"}
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        # Tool manager that simulates error
        mock_tool_manager = MockToolManager(simulate_tool_error=True)
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="Test query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should handle error gracefully and return appropriate response
        assert "course materials" in result or "Response despite tool error" in result
        assert mock_client.call_count == 1  # Should terminate after tool error

    @patch('anthropic.Anthropic')
    def test_tool_execution_exception_handling(self, mock_anthropic_class):
        """Test handling of tool execution exceptions"""
        response_sequence = [
            {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test"}},
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        # Mock tool manager that raises exception
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = Exception("Tool execution failed")
        tools = [{"name": "search_course_content", "description": "test"}]

        result = generator.generate_response(
            query="Test query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should handle exception gracefully
        assert "course materials" in result
        assert mock_client.call_count == 1


class TestSequentialToolIntegration:
    """Test integration with real tool definitions and complex scenarios"""

    @patch('anthropic.Anthropic')
    def test_with_real_tool_definitions(self, mock_anthropic_class):
        """Test with real tool definitions from search tools"""
        from search_tools import CourseSearchTool, CourseOutlineTool
        from mocks import MockVectorStore

        response_sequence = [
            {"type": "tool_use", "tool": "get_course_outline", "params": {"course_name": "Test Course"}},
            {"type": "tool_use", "tool": "search_course_content", "params": {"query": "introduction"}},
            {"type": "text", "content": "Integrated response"}
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        # Use real tool definitions
        mock_store = MockVectorStore()
        search_tool = CourseSearchTool(mock_store)
        outline_tool = CourseOutlineTool(mock_store)

        # Mock tool manager that can handle real tool calls
        mock_tool_manager = MockToolManager(mock_search_result="Real tool result")
        tools = [search_tool.get_tool_definition(), outline_tool.get_tool_definition()]

        result = generator.generate_response(
            query="Complex query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        assert result == "Integrated response"
        assert mock_client.call_count == 3
        assert mock_tool_manager.execution_count == 2

        # Verify tools were called with correct names
        assert mock_tool_manager.execution_history[0]["tool_name"] == "get_course_outline"
        assert mock_tool_manager.execution_history[1]["tool_name"] == "search_course_content"

    @patch('anthropic.Anthropic')
    def test_course_comparison_scenario(self, mock_anthropic_class):
        """Test realistic course comparison scenario"""
        response_sequence = [
            {"type": "tool_use", "tool": "search_course_content",
             "params": {"query": "introduction", "course_name": "Course A"}},
            {"type": "tool_use", "tool": "search_course_content",
             "params": {"query": "introduction", "course_name": "Course B"}},
            {"type": "text", "content": "Comparison of introductions between courses"}
        ]

        mock_client = EnhancedMockAnthropicClient(response_sequence)
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager(mock_search_result="Course content")
        tools = mock_tool_manager.get_tool_definitions()

        result = generator.generate_response(
            query="Compare the introduction content between Course A and Course B",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        assert result == "Comparison of introductions between courses"
        assert mock_client.call_count == 3
        assert mock_tool_manager.execution_count == 2

        # Verify tool parameters evolved correctly
        first_call = mock_tool_manager.execution_history[0]
        second_call = mock_tool_manager.execution_history[1]

        assert first_call["params"]["query"] == "introduction"
        assert second_call["params"]["query"] == "introduction"


class TestBackwardCompatibility:
    """Ensure existing single-call behavior still works"""

    @patch('anthropic.Anthropic')
    def test_single_call_behavior_unchanged(self, mock_anthropic_class):
        """Verify single tool calls work exactly as before"""
        mock_client = MockAnthropicClient(simulate_tool_use=True, custom_response="Single tool response")
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        mock_tool_manager = MockToolManager(mock_search_result="Tool result")
        tools = mock_tool_manager.get_tool_definitions()

        # Use old interface without max_rounds parameter
        result = generator.generate_response(
            query="Simple query",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should still work as before
        assert mock_client.call_count == 2  # Tool use + final response
        assert mock_tool_manager.execution_count == 1

    @patch('anthropic.Anthropic')
    def test_no_tools_behavior_unchanged(self, mock_anthropic_class):
        """Verify no-tool responses work exactly as before"""
        mock_client = MockAnthropicClient(simulate_tool_use=False, custom_response="Direct response")
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        result = generator.generate_response(query="Simple question")

        assert result == "Direct response"
        assert mock_client.call_count == 1

    @patch('anthropic.Anthropic')
    def test_original_api_compatibility(self, mock_anthropic_class):
        """Test that all original API parameters still work"""
        mock_client = MockAnthropicClient(custom_response="Compatible response")
        mock_anthropic_class.return_value = mock_client

        generator = AIGenerator("test-api-key", "claude-3-sonnet-20240229")
        generator.client = mock_client

        # Test all original parameters still work
        result = generator.generate_response(
            query="Test query",
            conversation_history="Previous: conversation",
            tools=[{"name": "test_tool"}],
            tool_manager=None
        )

        assert result == "Compatible response"
        assert mock_client.call_count == 1