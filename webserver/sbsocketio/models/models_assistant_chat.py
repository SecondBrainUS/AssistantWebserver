from typing import Literal, Optional, Any, Dict
from pydantic import BaseModel

class SBAWUserTextMessage(BaseModel):
	id: str
	content: str
	model_id: str
	role: str = 'user'
	type: str = 'message'
	modality: str = 'text'

class SBAWAssistantTextMessage(BaseModel):
	id: str
	content: str
	model_id: str
	token_usage: Optional[Any]
	stop_reason: Optional[str]
	role: str = 'assistant'
	type: str = 'message'
	modality: str = 'text'

class SBAWFunctionCall(BaseModel):
	id: str
	call_id: str
	name: str
	arguments: Dict
	role: str = 'assistant'
	type: str = 'function_call'
	# TODO: serialize method for arguments to JSON

class SBAWFunctionResult(BaseModel):
	id: str
	call_id: str
	name: str
	result: Any
	role: str = 'system'
	type: str = 'function_result'