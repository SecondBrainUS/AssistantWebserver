import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, status, Depends, Request, Body
from fastapi.responses import JSONResponse
from webserver.config import settings
from typing import Optional, Dict, List, Any
from webserver.api.dependencies import verify_access_token, get_session
import aisuite
import json

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize aisuite client with API configurations
client_config = {
	"openai": {
		"api_key": settings.OPENAI_API_KEY,
	},
	"anthropic": {
		"api_key": settings.ANTHROPIC_API_KEY
	},
}

def serialize_message(message):
	"""Convert a message object to a serializable dictionary"""
	if hasattr(message, 'model_dump'):
		return message.model_dump()
	
	result = {
		"role": message.get("role", ""),
		"content": message.get("content", "") or ""  # Ensure content is never null
	}
	
	# Handle tool calls
	if hasattr(message, 'tool_calls') and message.tool_calls:
		result["tool_calls"] = [
			{
				"id": tool_call.id,
				"type": "function",
				"function": {
					"name": tool_call.function.name,
					"arguments": tool_call.function.arguments
				}
			}
			for tool_call in message.tool_calls
		]
	
	# Handle tool responses
	if message.get("tool_call_id"):
		result["tool_call_id"] = message["tool_call_id"]
		result["name"] = message.get("name")
	
	return result

def create_parameter_schema_tool():
	return {
		"type": "function",
		"function": {
			"name": "create_parameter_schema",
			"description": "Create a structured parameter schema for a user's prompt. This helps break down the prompt into specific parameters that can be collected from the user.",
			"parameters": {
				"type": "object",
				"properties": {
					"parameters": {
						"type": "array",
						"items": {
							"type": "object",
							"properties": {
								"name": {
									"type": "string",
									"description": "The name of the parameter"
								},
								"type": {
									"type": "string",
									"enum": ["string", "number", "array", "date"],
									"description": "The data type of the parameter"
								},
								"description": {
									"type": "string",
									"description": "A clear description of what this parameter represents"
								},
								"enum": {
									"type": "array",
									"items": {
										"type": "string"
									},
									"description": "Optional list of predefined values for this parameter",
									"default": None
								},
								"default": {
									"oneOf": [
										{"type": "string"},
										{"type": "number"},
										{"type": "array", "items": {"type": "string"}},
										{"type": "null"}
									],
									"description": "Default value for this parameter"
								}
							},
							"required": ["name", "type", "description"]
						}
					}
				},
				"required": ["parameters"]
			}
		}
	}
# , dependencies=[Depends(verify_access_token), Depends(get_session)]
@router.post("/compile")
async def compile(
	prompt: str = Body(...),
	modelid: str = Body(...),
	use_tools: bool = Body(default=True)
):
	if not prompt:
		raise HTTPException(status_code=400, detail="prompt is required")
	if not modelid:
		raise HTTPException(status_code=400, detail="model_id is required")

	modelid = modelid.replace('aisuite.', '')

	try:
		# Create client with API configurations
		client = aisuite.Client()
		client.configure(client_config)
		
		# Initial system message
		messages = [{
			"role": "system",
			"content": ("You are a prompt engineering assistant. Your task is to help users create well-structured, detailed prompts from their initial ideas."
			"Here is an example:"
			"""
			[
				{
					"name": "price",
					"type": "array",
					"items": {"type": "string"},
					"description": "Restaraunt price categories represented by dollar signs",
					"enum": ["$", "$$", "$$$", "$$$$"],
					"default": ["$", "$$"]
				},
				{
					"name": "cuisine",
					"type": "array",
					"items": {"type": "string"},
					"description": "Category of restaruant food offerings",
					"enum": null,
					"default": []
				},
				{
					"name": "location",
					"type": "string",
					"description": "User's current city or area",
					"default": null
				},
				{
					"name": "max_distance",
					"type": "number",
					"description": "Distance in miles from user's location",
					"default": null
				},
				{
					"name": "open_on",
					"type": "date",
					"description": "Date the restaraunt needs to be open",
					"default": null
				}
			]
			"""
			)
		}]
		
		# Add the user's prompt
		messages.append({
			"role": "user",
			"content": prompt
		})

		# First, get parameter schema if tools are enabled
		parameters = None
		if use_tools:
			tool_response = client.chat.completions.create(
				model=modelid,
				messages=messages,
				tools=[create_parameter_schema_tool()],
				tool_choice={"type": "function", "function": {"name": "create_parameter_schema"}}
			)
			
			if tool_response.choices[0].message.tool_calls:
				tool_call = tool_response.choices[0].message.tool_calls[0]
				parameters = json.loads(tool_call.function.arguments)
				
				# Add assistant's tool call message
				messages.append({
					"role": "assistant",
					"content": "",  # Empty string instead of None
					"tool_calls": [{
						"id": tool_call.id,
						"type": "function",
						"function": {
							"name": tool_call.function.name,
							"arguments": tool_call.function.arguments
						}
					}]
				})
				
				# Add tool response message
				messages.append({
					"role": "tool",
					"tool_call_id": tool_call.id,
					"name": "create_parameter_schema",
					"content": json.dumps(parameters)
				})

		# Get the final expanded prompt
		final_response = client.chat.completions.create(
			model=modelid,
			messages=messages,
			temperature=0.7
		)

		expanded_prompt = final_response.choices[0].message.content
		
		# Add final response to messages
		messages.append({
			"role": "assistant",
			"content": expanded_prompt
		})

		return JSONResponse(
			content={
				"expanded_prompt": expanded_prompt,
				"parameters": parameters["parameters"] if parameters else None,
				"messages": messages
			},
			status_code=status.HTTP_200_OK
		)

	except Exception as e:
		logger.error(f"Error {e}", exc_info=True)
		raise HTTPException(status_code=500, detail="Internal server error")
