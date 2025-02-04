import json
import uuid
import logging
import asyncio
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import aisuite

logger = logging.getLogger(__name__)

class AiSuiteAsstTextMessage(BaseModel):
    content: str
    token_usage: Optional[Dict[str, int]]
    stop_reason: Optional[str]

class AiSuiteAsstFunctionCall(BaseModel):
    name: str
    arguments: str
    call_id: str

class AiSuiteAsstFunctionResult(BaseModel):
    call_id: str
    result: Any

class AiSuiteResponse(BaseModel):
    """Standardized response format for both regular messages and tool-using conversations"""
    id: str
    content: str
    tool_calls: List[AiSuiteAsstFunctionCall]
    tool_results: List[AiSuiteAsstFunctionResult]
    token_usage: Optional[Dict[str, int]]
    stop_reason: Optional[str]

class AISuiteAssistant:
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
        self._max_tool_chain_turns = 20
        self._allow_tool_chaining = True
        self._tool_chain_counter = 0
        
        self._event_callbacks = {
            "tool_call": set(),
            "tool_result": set(),
            "final_response": set()
        }

    def set_tool_function_map(self, tool_map: Dict[str, Dict]):
        """
        Set the available tools and their implementations.
        
        Args:
            tool_map: Dictionary mapping tool names to their metadata and implementations
        """
        self._tool_function_map = tool_map
        
    def set_tool_chain_config(self, allow_chaining: bool = True, max_turns: int = 20):
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
            "role": "assistant",
            "tool_call_id": tool_result.call_id,  # This ID matches the original tool call
            "name": tool_result.name,
            "content": json.dumps({
                "result": tool_result.result,
                "arguments": tool_result.arguments  # Include original arguments for context
            })
        }

    def add_event_callback(self, event_type: str, callback):
        """
        Add a callback function for a specific event type.
        
        Args:
            event_type: Type of event ("tool_call", "tool_result", or "final_response")
            callback: Async function to call when event occurs
        """
        if event_type not in self._event_callbacks:
            raise ValueError(f"Unknown event type: {event_type}")
        self._event_callbacks[event_type].add(callback)

    async def _trigger_event(self, event_type: str, data: Any):
        """Trigger all callbacks for a given event type"""
        for callback in self._event_callbacks[event_type]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in {event_type} callback: {e}")

    async def generate_response(
        self,
        messages: List[Dict],
        model: str,
        temperature: float = 0.7,
        history_length: int = 20
    ) -> AiSuiteResponse:
        """
        Generate a response using the AI model, handling both regular messages and tool calls.
        
        Args:
            messages: List of conversation messages
            model: Model identifier (e.g., "anthropic:claude-3")
            temperature: Sampling temperature
            history_length: Number of most recent messages to include in context (default: 20)
            
        Returns:
            AiSuiteResponse object containing the response and any tool interactions
        """

        # Take only the most recent messages based on history_length
        conversation = messages[-history_length:].copy()
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
                        tool_call = AiSuiteAsstFunctionCall(
                            id=tool_call_data.id,
                            name=tool_call_data.function.name,
                            arguments=json.loads(tool_call_data.function.arguments)
                        )

                        current_tool_calls.append(tool_call)
                        
                        # Trigger tool call event
                        await self._trigger_event("tool_call", tool_call)
                        
                        # Execute tool and create result
                        try:
                            result = await self._execute_tool(tool_call)
                            tool_result = AiSuiteAsstFunctionResult(
                                id=str(uuid.uuid4()),
                                call_id=tool_call.id,
                                name=tool_call.name,
                                arguments=tool_call.arguments,
                                result=result
                            )

                            tool_results.append(tool_result)
                            
                            # Trigger tool result event
                            await self._trigger_event("tool_result", tool_result)
                            
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
                            tool_result = AiSuiteAsstFunctionResult(
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
                    
                    # Trigger final response event when no more tool calls
                    if not final_response.choices[0].message.tool_calls:
                        await self._trigger_event("final_response", final_content)
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

            return AiSuiteResponse(
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

"""
Need to "stream" tool calls as them come out
Need an "is_processing" variable
then trigger "done" when final response is triggered


"""