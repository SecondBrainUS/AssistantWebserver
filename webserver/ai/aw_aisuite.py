import json
import uuid
import logging
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import aisuite

logger = logging.getLogger(__name__)

@dataclass
class ToolCall:
    """Represents a single tool call"""
    id: str
    name: str
    arguments: dict

@dataclass
class ToolResult:
    """Represents the result of a tool call"""
    id: str  # Unique ID for the result message
    call_id: str  # ID of the original tool call
    name: str  # Name of the tool that was called
    arguments: dict  # Original arguments for context
    result: Any  # Result from the tool execution

@dataclass
class AIResponse:
    """Standardized response format for both regular messages and tool-using conversations"""
    id: str
    content: str
    tool_calls: List[ToolCall]  # Tool calls made
    tool_results: List[ToolResult]  # Results of tool calls
    token_usage: Optional[Dict[str, int]]
    stop_reason: Optional[str]
    conversation_messages: List[Dict]  # Full conversation including tool interactions

class AISuiteWrapper:
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the AI Suite wrapper with optional configuration.
        
        Args:
            config: Configuration dictionary for providers (e.g., Azure credentials)
        """
        self.client = aisuite.Client()
        if config:
            self.client.configure(config)
            
        self._tool_function_map = {}
        self._max_tool_chain_turns = 5
        self._allow_tool_chaining = True
        self._tool_chain_counter = 0
        
    def set_tool_function_map(self, tool_map: Dict[str, Dict]):
        """
        Set the available tools and their implementations.
        
        Args:
            tool_map: Dictionary mapping tool names to their metadata and implementations
        """
        self._tool_function_map = tool_map
        
    def set_tool_chain_config(self, allow_chaining: bool = True, max_turns: int = 5):
        """Configure tool chaining behavior"""
        self._allow_tool_chaining = allow_chaining
        self._max_tool_chain_turns = max_turns
        
    def _get_tools_config(self) -> List[Dict]:
        """Convert tool map to aisuite tools format"""
        if not self._tool_function_map:
            return []
            
        return [{
            "type": "function",
            "function": {
                "name": name,
                "description": meta["description"],
                "parameters": meta["parameters"]
            }
        } for name, meta in self._tool_function_map.items()]

    async def _execute_tool(self, tool_call: ToolCall) -> Any:
        """Execute a tool and get its result"""
        if tool_call.name not in self._tool_function_map:
            raise ValueError(f"Unknown tool: {tool_call.name}")
            
        function = self._tool_function_map[tool_call.name]["function"]
        try:
            # Handle different types of functions
            if isinstance(function, str):
                # If function is a string, just return it (legacy behavior)
                return function
            elif callable(function):
                if asyncio.iscoroutinefunction(function):
                    result = await function(**tool_call.arguments)
                else:
                    result = function(**tool_call.arguments)
                return result
            else:
                raise ValueError(f"Invalid function type for tool {tool_call.name}")
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            raise

    def _create_tool_message(self, tool_result: ToolResult) -> Dict:
        """Create a message from a tool result"""
        return {
            "role": "tool",
            "tool_call_id": tool_result.call_id,  # This ID matches the original tool call
            "name": tool_result.name,
            "content": json.dumps({
                "result": tool_result.result,
                "arguments": tool_result.arguments  # Include original arguments for context
            })
        }

    async def generate_response(
        self,
        messages: List[Dict],
        model: str,
        temperature: float = 0.7
    ) -> AIResponse:
        """
        Generate a response using the AI model, handling both regular messages and tool calls.
        
        Args:
            messages: List of conversation messages
            model: Model identifier (e.g., "anthropic:claude-3")
            temperature: Sampling temperature
            
        Returns:
            AIResponse object containing the response and any tool interactions
        """
        conversation = messages.copy()
        tools = self._get_tools_config()
        response_id = str(uuid.uuid4())
        self._tool_chain_counter = 0
        
        try:
            # Initial model call
            response = self.client.chat.completions.create(
                model=model,
                messages=conversation,
                tools=tools,
                temperature=temperature
            )
            
            tool_calls = []
            tool_results = []
            final_content = response.choices[0].message.content
            
            # Handle tool calls if present
            if response.choices[0].message.tool_calls:
                while (self._allow_tool_chaining and 
                       self._tool_chain_counter < self._max_tool_chain_turns):
                    
                    self._tool_chain_counter += 1
                    current_tool_calls = []
                    
                    # Process tool calls
                    for tool_call_data in response.choices[0].message.tool_calls:
                        tool_call = ToolCall(
                            id=tool_call_data.id,
                            name=tool_call_data.function.name,
                            arguments=json.loads(tool_call_data.function.arguments)
                        )
                        current_tool_calls.append(tool_call)
                        
                        # Execute tool and create result
                        try:
                            result = await self._execute_tool(tool_call)
                            tool_result = ToolResult(
                                id=str(uuid.uuid4()),
                                call_id=tool_call.id,
                                name=tool_call.name,
                                arguments=tool_call.arguments,
                                result=result
                            )
                            tool_results.append(tool_result)
                            
                            # Add tool interaction to conversation with type field
                            conversation.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.name,
                                        "arguments": json.dumps(tool_call.arguments)
                                    }
                                }]
                            })
                            conversation.append(self._create_tool_message(tool_result))
                            
                        except Exception as e:
                            logger.error(f"Tool execution error for {tool_call.name}: {e}")
                            tool_result = ToolResult(
                                id=str(uuid.uuid4()),
                                call_id=tool_call.id,
                                name=tool_call.name,
                                arguments=tool_call.arguments,
                                result={"error": str(e)}
                            )
                            tool_results.append(tool_result)
                    
                    # Add all tool calls to the main list
                    tool_calls.extend(current_tool_calls)
                    
                    # Get final response after tool calls - remove await
                    final_response = self.client.chat.completions.create(
                        model=model,
                        messages=conversation,
                        tools=tools,
                        temperature=temperature
                    )
                    
                    final_content = final_response.choices[0].message.content
                    
                    # Check if more tool calls are needed
                    if not final_response.choices[0].message.tool_calls:
                        break
                    
                    response = final_response

            # Construct token usage if available
            token_usage = None
            if hasattr(response, 'usage'):
                token_usage = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }

            return AIResponse(
                id=response_id,
                content=final_content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                token_usage=token_usage,
                stop_reason=getattr(response.choices[0], 'finish_reason', None),
                conversation_messages=conversation
            )
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
