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

def create_fill_parameters_tool(parameters_schema):
	"""Creates a tool definition for filling parameters based on the existing schema"""
	properties = {}
	
	for param in parameters_schema:
		param_schema = {
			"type": param["type"],
			"description": param["description"]
		}
		
		# Only add enum if it exists and is not None
		if param.get("enum") is not None:
			param_schema["enum"] = param["enum"]
			
		# Handle array type parameters
		if param["type"] == "array":
			param_schema["type"] = "array"
			param_schema["items"] = {"type": "string"}
			
		properties[param["name"]] = param_schema

	return {
		"type": "function",
		"function": {
			"name": "fill_parameters",
			"description": "Fill out parameter values based on the user's prompt text",
			"parameters": {
				"type": "object",
				"properties": {
					"values": {
						"type": "object",
						"properties": properties,
						"required": [param["name"] for param in parameters_schema]
					}
				},
				"required": ["values"]
			}
		}
	}

# , dependencies=[Depends(verify_access_token), Depends(get_session)]
@router.post("/compile/form")
async def compile_form(
	prompt: str = Body(...),
	modelid: str = Body(...),
):
	"""Endpoint for compiling prompt with parameter form generation"""
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
		
		messages.append({
			"role": "user",
			"content": prompt
		})

		# Get parameter schema
		tool_response = client.chat.completions.create(
			model=modelid,
			messages=messages,
			tools=[create_parameter_schema_tool()],
			tool_choice={"type": "function", "function": {"name": "create_parameter_schema"}}
		)
		
		parameters = None
		if tool_response.choices[0].message.tool_calls:
			tool_call = tool_response.choices[0].message.tool_calls[0]
			parameters = json.loads(tool_call.function.arguments)
			
			messages.append({
				"role": "assistant",
				"content": "",
				"tool_calls": [{
					"id": tool_call.id,
					"type": "function",
					"function": {
						"name": tool_call.function.name,
						"arguments": tool_call.function.arguments
					}
				}]
			})
			
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

@router.post("/compile")
async def compile(
	prompt: str = Body(...),
	modelid: str = Body(...),
):
	"""Endpoint for simple prompt compilation without parameter form"""
	if not prompt:
		raise HTTPException(status_code=400, detail="prompt is required")
	if not modelid:
		raise HTTPException(status_code=400, detail="model_id is required")

	modelid = modelid.replace('aisuite.', '')

	try:
		client = aisuite.Client()
		client.configure(client_config)
		
		messages = [{
			"role": "system",
			"content": """You are an expert prompt engineer. You are tasked with rewriting and optimizing input prompts. When given a shorthand or unstructured prompt, transform it into a fully detailed, optimized prompt following these steps:
			Step 1: **Analyze the Input**
			- Read the provided prompt carefully.
			- Identify the core objective (Goal), the desired answer structure (Return Format), potential ambiguities or critical checks (Warnings), and any necessary supporting background (Context Dump).

			Step 2: **Rewrite and Structure**
			- Reformulate the prompt to include four clear sections:
			- **Goal:** Define exactly what is being requested.
			- **Return Format:** Specify the structure and format of the desired response (e.g., bullet lists, numbered steps, specific sections).
			- **Warnings:** Note any potential pitfalls, sensitive topics, or ambiguous language that needs special attention.
			- **Context Dump:** Provide any background context, definitions, or clarifications required for full understanding.
			- Use clear, concise, and plain language, ensuring that each section is distinct and easy to follow.

			Step 3: **Optimize and Validate**
			- Simplify and clarify sentence structures.
			- Remove redundant language and correct any ambiguities.
			- Ensure that the rewritten prompt is fully self-contained and requires no external references.
			- Confirm that the prompt adheres to high-quality prompt engineering practices: clarity, completeness, and specificity.

			Your final output should be a well-structured prompt that guides a downstream LLM to produce accurate, high-quality responses based on the provided input.

			"""
		}, {
			"role": "user",
			"content": prompt
		}]

		response = client.chat.completions.create(
			model=modelid,
			messages=messages,
			temperature=0.7
		)

		expanded_prompt = response.choices[0].message.content
		messages.append({
			"role": "assistant",
			"content": expanded_prompt
		})

		return JSONResponse(
			content={
				"expanded_prompt": expanded_prompt,
				"messages": messages
			},
			status_code=status.HTTP_200_OK
		)

	except Exception as e:
		logger.error(f"Error {e}", exc_info=True)
		raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/update_parameters")
async def update_parameters(
	prompt: str = Body(...),
	parameters_schema: List[Dict[str, Any]] = Body(...),
	original_prompt: str = Body(...),
	modelid: str = Body(...)
):
	try:
		client = aisuite.Client()
		client.configure(client_config)
		
		modelid = modelid.replace('aisuite.', '')
		
		messages = [{
			"role": "system",
			"content": "You are a parameter extraction assistant. Your task is to extract parameter values from the user's new prompt text based on the existing parameter schema."
		}, {
			"role": "user",
			"content": f"Original prompt: {original_prompt}\n\nNew prompt text: {prompt}\n\nPlease extract the parameter values from the new prompt text."
		}]

		response = client.chat.completions.create(
			model=modelid,
			messages=messages,
			tools=[create_fill_parameters_tool(parameters_schema)],
			tool_choice={"type": "function", "function": {"name": "fill_parameters"}}
		)

		if response.choices[0].message.tool_calls:
			tool_call = response.choices[0].message.tool_calls[0]
			filled_values = json.loads(tool_call.function.arguments)
			
			return JSONResponse(
				content={
					"values": filled_values["values"]
				},
				status_code=status.HTTP_200_OK
			)

	except Exception as e:
		logger.error(f"Error {e}", exc_info=True)
		raise HTTPException(status_code=500, detail="Internal server error")
