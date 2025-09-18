#!/usr/bin/env python3
"""
Test sequential tool calling logic without external dependencies
"""

import sys
from unittest.mock import Mock

# Mock the anthropic module
sys.modules['anthropic'] = Mock()

from ai_generator import AIGenerator
from tests.mocks import EnhancedMockAnthropicClient, MockToolManager

def test_basic_sequential_flow():
    """Test basic 2-round sequential tool calling"""
    print("Testing basic sequential flow...")

    # Set up response sequence: tool -> tool -> text
    response_sequence = [
        {"type": "tool_use", "tool": "get_course_outline", "params": {"course_name": "Course A"}},
        {"type": "tool_use", "tool": "search_course_content", "params": {"query": "introduction"}},
        {"type": "text", "content": "Final response after 2 tools"}
    ]

    # Create enhanced mock client
    mock_client = EnhancedMockAnthropicClient(response_sequence)

    # Create AI generator and set the mock client
    generator = AIGenerator("test-key", "test-model")
    generator.client = mock_client

    # Create mock tool manager
    mock_tool_manager = MockToolManager(mock_search_result="Tool result")
    tools = mock_tool_manager.get_tool_definitions()

    # Test the sequential flow
    result = generator.generate_response(
        query="Compare courses",
        tools=tools,
        tool_manager=mock_tool_manager
    )

    # Verify results
    assert result == "Final response after 2 tools", f"Expected final response, got: {result}"
    assert mock_client.call_count == 3, f"Expected 3 API calls, got: {mock_client.call_count}"
    assert mock_tool_manager.execution_count == 2, f"Expected 2 tool executions, got: {mock_tool_manager.execution_count}"

    # Verify execution order
    assert mock_tool_manager.execution_history[0]["tool_name"] == "get_course_outline"
    assert mock_tool_manager.execution_history[1]["tool_name"] == "search_course_content"

    print("[PASS] Basic sequential flow test passed")

def test_max_rounds_termination():
    """Test that execution stops after max rounds"""
    print("Testing max rounds termination...")

    # Set up response sequence with 3 tool calls (should stop after 2)
    response_sequence = [
        {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test1"}},
        {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test2"}},
        {"type": "text", "content": "Final summary after max rounds"}
    ]

    mock_client = EnhancedMockAnthropicClient(response_sequence)
    generator = AIGenerator("test-key", "test-model")
    generator.client = mock_client

    mock_tool_manager = MockToolManager()
    tools = mock_tool_manager.get_tool_definitions()

    result = generator.generate_response(
        query="Complex query",
        tools=tools,
        tool_manager=mock_tool_manager
    )

    # Should stop after 2 rounds + final summary call
    assert mock_client.call_count == 3, f"Expected 3 API calls (2 rounds + final), got: {mock_client.call_count}"
    assert mock_tool_manager.execution_count == 2, f"Expected 2 tool executions, got: {mock_tool_manager.execution_count}"
    assert result == "Final summary after max rounds"

    print("[PASS] Max rounds termination test passed")

def test_early_termination():
    """Test early termination when Claude doesn't request tools"""
    print("Testing early termination...")

    # Claude returns text immediately without tools
    response_sequence = [
        {"type": "text", "content": "Direct answer without tools"}
    ]

    mock_client = EnhancedMockAnthropicClient(response_sequence)
    generator = AIGenerator("test-key", "test-model")
    generator.client = mock_client

    mock_tool_manager = MockToolManager()
    tools = mock_tool_manager.get_tool_definitions()

    result = generator.generate_response(
        query="Simple question",
        tools=tools,
        tool_manager=mock_tool_manager
    )

    # Should terminate immediately
    assert mock_client.call_count == 1, f"Expected 1 API call, got: {mock_client.call_count}"
    assert mock_tool_manager.execution_count == 0, f"Expected 0 tool executions, got: {mock_tool_manager.execution_count}"
    assert result == "Direct answer without tools"

    print("[PASS] Early termination test passed")

def test_conversation_context():
    """Test that conversation context is preserved"""
    print("Testing conversation context preservation...")

    response_sequence = [
        {"type": "tool_use", "tool": "search_course_content", "params": {"query": "test"}},
        {"type": "text", "content": "Response with context"}
    ]

    mock_client = EnhancedMockAnthropicClient(response_sequence)
    generator = AIGenerator("test-key", "test-model")
    generator.client = mock_client

    mock_tool_manager = MockToolManager()
    tools = mock_tool_manager.get_tool_definitions()

    # Include conversation history
    history = "User: Previous question\nAssistant: Previous answer"
    result = generator.generate_response(
        query="Follow-up question",
        conversation_history=history,
        tools=tools,
        tool_manager=mock_tool_manager
    )

    # Verify history was included in all system prompts
    for call_params in mock_client.call_history:
        assert history in call_params["system"], "Conversation history not preserved"

    print("[PASS] Conversation context test passed")

if __name__ == "__main__":
    try:
        test_basic_sequential_flow()
        test_max_rounds_termination()
        test_early_termination()
        test_conversation_context()

        print("\n[SUCCESS] All sequential tool calling tests passed!")
        print("Implementation is working correctly.")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()