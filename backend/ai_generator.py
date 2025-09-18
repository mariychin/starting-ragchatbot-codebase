import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive search and outline tools for course information.

Tool Usage Guidelines:
- **Course Content Search (search_course_content)**: Use for questions about specific course content, concepts, or detailed educational materials
- **Course Outline (get_course_outline)**: Use for questions about course structure, lesson lists, or course overviews
- **Sequential tool calling**: You may use up to 2 tools in separate reasoning steps to gather comprehensive information
- **Tool strategy**: Consider using multiple searches with different parameters or combining content search with outline queries
- After each tool use, you will have opportunity to make additional tool calls if needed
- Synthesize all tool results into accurate, fact-based responses
- If tools yield no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Use search_course_content tool, then optionally refine with additional searches
- **Course outline/structure questions**: Use get_course_outline tool first, then optionally search for specific content
- **Complex queries**: Consider multiple tool calls to gather comprehensive information
- **No meta-commentary**: Provide direct answers only — no reasoning process, tool explanations, or question-type analysis

When you have sufficient information from tool results, provide your final answer without requesting additional tools.

When responding to outline queries, ensure your response includes:
- Course title
- Course link (if available)
- Complete lesson breakdown with lesson numbers and titles

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None,
                         max_rounds: int = 2) -> str:
        """
        Generate AI response with sequential tool calling support.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            max_rounds: Maximum number of tool calling rounds (default: 2)

        Returns:
            Generated response as string
        """

        # Initialize conversation state
        messages = self._initialize_conversation(query, conversation_history)
        system_content = self._build_system_content(conversation_history, max_rounds)

        # Execute sequential rounds
        return self._execute_sequential_rounds(
            messages=messages,
            system_content=system_content,
            tools=tools,
            tool_manager=tool_manager,
            max_rounds=max_rounds
        )
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls and get follow-up response.
        
        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            
        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()
        
        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})
        
        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, 
                    **content_block.input
                )
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content_block.id,
                    "content": tool_result
                })
        
        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        
        # Prepare final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"]
        }
        
        # Get final response
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text

    def _initialize_conversation(self, query: str, conversation_history: Optional[str]) -> List[Dict[str, Any]]:
        """
        Initialize the conversation messages array.

        Args:
            query: The user's current question
            conversation_history: Previous conversation context

        Returns:
            List of message dictionaries
        """
        messages = []

        # For now, just add the current user query
        # Conversation history is handled in system content
        messages.append({"role": "user", "content": query})

        return messages

    def _build_system_content(self, conversation_history: Optional[str], max_rounds: int) -> str:
        """
        Build system content with round-specific guidance.

        Args:
            conversation_history: Previous conversation context
            max_rounds: Maximum tool calling rounds

        Returns:
            Complete system content string
        """
        base_content = self.SYSTEM_PROMPT

        # Add round-specific guidance
        round_guidance = f"\nTool Round Limits: You have up to {max_rounds} opportunities to use tools in this conversation. Use them strategically to gather the most relevant information."

        # Add conversation history
        if conversation_history:
            return f"{base_content}{round_guidance}\n\nPrevious conversation:\n{conversation_history}"
        else:
            return f"{base_content}{round_guidance}"

    def _execute_sequential_rounds(self, messages: List[Dict[str, Any]], system_content: str,
                                  tools: Optional[List], tool_manager,
                                  max_rounds: int) -> str:
        """
        Execute up to max_rounds of tool calling with Claude.

        Termination conditions:
        1. Maximum rounds reached
        2. Claude doesn't request tool usage
        3. Tool execution fails

        Args:
            messages: Current conversation messages
            system_content: System prompt content
            tools: Available tools
            tool_manager: Manager to execute tools
            max_rounds: Maximum number of rounds

        Returns:
            Final response text
        """
        current_round = 0

        while current_round < max_rounds:
            # Make API call to Claude
            response = self._make_claude_api_call(messages, system_content, tools)

            # Check termination conditions
            if response.stop_reason != "tool_use":
                # Claude didn't request tools - conversation complete
                return response.content[0].text

            if not tool_manager:
                # No tool manager available - return response
                return response.content[0].text

            # Execute tools and update conversation
            tool_execution_success = self._execute_tools_and_update_messages(
                response, messages, tool_manager
            )

            if not tool_execution_success:
                # Tool execution failed - terminate with error handling
                return self._handle_tool_failure(response)

            current_round += 1

        # Max rounds reached - make final call without tools for summary
        final_response = self._make_claude_api_call(messages, system_content, tools=None)
        return final_response.content[0].text

    def _make_claude_api_call(self, messages: List[Dict[str, Any]], system_content: str,
                             tools: Optional[List] = None):
        """
        Make a single API call to Claude.

        Args:
            messages: Conversation messages
            system_content: System prompt
            tools: Available tools (optional)

        Returns:
            Claude API response
        """
        api_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }

        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        return self.client.messages.create(**api_params)

    def _execute_tools_and_update_messages(self, response, messages: List[Dict[str, Any]],
                                          tool_manager) -> bool:
        """
        Execute tools from Claude's response and update messages array.

        Args:
            response: Claude API response containing tool use
            messages: Conversation messages to update
            tool_manager: Manager to execute tools

        Returns:
            bool: True if tool execution succeeded, False otherwise
        """
        try:
            # Add Claude's tool use response to messages
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tool calls
            tool_results = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_result = tool_manager.execute_tool(
                        content_block.name,
                        **content_block.input
                    )

                    # Check for tool execution errors
                    if isinstance(tool_result, str) and "not found" in tool_result.lower():
                        return False

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })

            # Add tool results as single message
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            return True

        except Exception as e:
            print(f"Tool execution error: {e}")
            return False

    def _handle_tool_failure(self, response) -> str:
        """
        Handle tool execution failures gracefully.

        Args:
            response: Claude API response that had tool failures

        Returns:
            Fallback response text
        """
        # Extract any text content from the response
        text_content = []
        for content_block in response.content:
            if content_block.type == "text":
                text_content.append(content_block.text)

        if text_content:
            return " ".join(text_content)
        else:
            return "I encountered an issue accessing the course materials. Please try rephrasing your question."