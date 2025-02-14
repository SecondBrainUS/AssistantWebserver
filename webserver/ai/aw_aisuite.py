import json
import uuid
import logging
import asyncio
from typing import Dict, List, Optional, Any
import aisuite.framework
from pydantic import BaseModel
import aisuite

logger = logging.getLogger(__name__)

class AiSuiteAsstBase(BaseModel):
    model_id: str
    model_api_source: str = "aisuite"

class AiSuiteAsstTextMessage(AiSuiteAsstBase):
    content: str | None
    token_usage: Optional[Dict[str, Optional[int]]]
    stop_reason: Optional[str]

class AiSuiteAsstFunctionCall(AiSuiteAsstBase):
    name: str
    arguments: Any
    call_id: str
    token_usage: Optional[Dict[str, Optional[int]]]

class AiSuiteAsstFunctionResult(AiSuiteAsstBase):
    call_id: str
    name: str
    arguments: Any
    result: Any

class AiSuiteResponse(BaseModel):
    """Standardized response format for both regular messages and tool-using conversations"""
    id: str
    content: str
    tool_calls: List[AiSuiteAsstFunctionCall]
    tool_results: List[AiSuiteAsstFunctionResult]
    token_usage: Optional[Dict[str, Optional[int]]]
    stop_reason: Optional[str]

class AiSuiteAssistant:
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
            "final_response": set(),
            "error": set()
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
        
    # anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "tools.0: Input tag 'function' found using 'type' does not match any of the expected tags: 'bash_20250124', 'custom', 'text_editor_20250124'"}}
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

    async def _execute_tool(self, tool_call: AiSuiteAsstFunctionCall) -> Any:
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

    def _create_tool_message(self, tool_result: AiSuiteAsstFunctionResult) -> Dict:
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

    def add_event_callback(self, event_type: str, callback):
        """
        Add a callback function for a specific event type.
        
        Args:
            event_type: Type of event ("tool_call", "tool_result", or "final_response")
            callback: Async function to call when event occurs
        """
        logger.info(f"Adding event callback for {event_type}")
        if event_type not in self._event_callbacks:
            raise ValueError(f"Unknown event type: {event_type}")
        self._event_callbacks[event_type].add(callback)

    async def _trigger_event(self, event_type: str, data: Any):
        """Trigger all callbacks for a given event type"""
        logger.info(f"Triggering event {event_type} with data {data}")
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
        history_length: Optional[int] = None
    ) -> AiSuiteResponse:
        """
        Generate a response using the AI model, handling both regular messages and tool calls.
        
        Args:
            messages: List of conversation messages
            model: Model identifier (e.g., "anthropic:claude-3")
            temperature: Sampling temperature
            history_length: Number of most recent messages to include in context (default: None, uses entire history)
            
        Returns:
            AiSuiteResponse object containing the response and any tool interactions
        """
        # Add system prompt for tool usage
        system_prompt = {
            "role": "system",
            "content": (
                "After using the tools to get results for the user, provide a simple concise natural language response to the user."
            )
        }

        # Take entire history if history_length is None, otherwise take most recent messages
        conversation = messages[-history_length:].copy() if history_length else messages.copy()
        
        # Insert system prompt at the beginning
        conversation.insert(0, system_prompt)
        
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

            logger.info(f"[AISUITE] [GENERATE RESPONSE] Response: {response}")
            
            tool_calls = []
            tool_results = []
            final_content = response.choices[0].message.content
            token_usage = None
            if hasattr(response, 'usage') and response.usage:
                try:
                    token_usage = {
                        'prompt_tokens': getattr(response.usage, 'prompt_tokens', None),
                        'completion_tokens': getattr(response.usage, 'completion_tokens', None),
                        'total_tokens': getattr(response.usage, 'total_tokens', None)
                    }
                except AttributeError:
                    logger.warning("Could not access token usage attributes")
                    token_usage = None

            final_response = response
            
            # Handle tool calls if present
            if response.choices[0].message.tool_calls:

                while (self._allow_tool_chaining and 
                       self._tool_chain_counter < self._max_tool_chain_turns):
                    
                    self._tool_chain_counter += 1
                    current_tool_calls = []
                    
                    # Process tool calls
                    for tool_call_data in response.choices[0].message.tool_calls:
                        tool_call = AiSuiteAsstFunctionCall(
                            model_id=model,
                            name=tool_call_data.function.name,
                            arguments=json.loads(tool_call_data.function.arguments),
                            call_id=tool_call_data.id,
                            token_usage=token_usage
                        )

                        current_tool_calls.append(tool_call)

                        logger.info(f"[AISUITE] [GENERATE RESPONSE] Tool call: {tool_call}")
                        
                        # Trigger tool call event
                        await self._trigger_event("tool_call", tool_call)
                        
                        # Execute tool and create result
                        try:
                            result = await self._execute_tool(tool_call)
                            tool_result = AiSuiteAsstFunctionResult(
                                model_id=model,
                                call_id=tool_call.call_id,
                                name=tool_call.name,
                                arguments=tool_call.arguments,
                                result=result
                            )

                            logger.info(f"[AISUITE] [GENERATE RESPONSE] Tool result: {tool_result}")
                            tool_results.append(tool_result)
                            
                            # Trigger tool result event
                            await self._trigger_event("tool_result", tool_result)
                            
                            # Add tool interaction to conversation with type field
                            conversation.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id": tool_call.call_id,
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
                                model_id=model,
                                id=str(uuid.uuid4()),
                                call_id=tool_call.call_id,
                                name=tool_call.name,
                                arguments=tool_call.arguments,
                                result={"error": str(e)}
                            )

                            tool_results.append(tool_result)
                    
                    # Add all tool calls to the main list
                    tool_calls.extend(current_tool_calls)

                    
                    # Get final response after tool calls
                    final_response = self.client.chat.completions.create(
                        model=model,
                        messages=conversation,
                        tools=tools,
                        temperature=temperature
                    )
                    
                    final_content = final_response.choices[0].message.content
                    
                    # Construct token usage if available
                    token_usage = None
                    if hasattr(final_response, 'usage') and final_response.usage:
                        try:
                            token_usage = {
                                'prompt_tokens': getattr(final_response.usage, 'prompt_tokens', None),
                                'completion_tokens': getattr(final_response.usage, 'completion_tokens', None),
                                'total_tokens': getattr(final_response.usage, 'total_tokens', None)
                            }
                        except AttributeError:
                            logger.warning("Could not access token usage attributes in final response")
                            token_usage = None
                    
                    # Trigger final response event when no more tool calls
                    if not final_response.choices[0].message.tool_calls:
                        break

                    response = final_response

            # Create text message for final response
            final_message: AiSuiteAsstTextMessage = AiSuiteAsstTextMessage(
                model_id=model,
                content=final_content,
                token_usage=token_usage,
                stop_reason=getattr(final_response.choices[0], 'finish_reason', None)
            )
            await self._trigger_event("final_response", final_message)

            logger.info(f"[AISUITE] [GENERATE RESPONSE] Final response: {final_content}")

            return AiSuiteResponse(
                id=response_id,
                content=final_content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                token_usage=token_usage,
                stop_reason=getattr(final_response.choices[0], 'finish_reason', None),
                conversation_messages=conversation
            )
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

#TODO: Need an "is_processing" variable