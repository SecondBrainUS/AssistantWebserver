from typing import Literal, Optional, Any, Dict
from pydantic import BaseModel

# TODO: use both a client_message_id and then an id from the server

#sbaw.text_message.user or incoming
class SBAWUserTextMessage(BaseModel):
	id: str
	content: str
	model_id: str
	role: str = 'user'
	type: str = 'message'
	modality: str = 'text'
	created_timestamp: Optional[str]

#sbaw.text_message.assistant
class SBAWAssistantTextMessage(BaseModel):
	id: str
	content: str
	model_id: str
	token_usage: Optional[Any]
	stop_reason: Optional[str]
	role: str = 'assistant'
	type: str = 'message'
	modality: str = 'text'
	created_timestamp: Optional[str]

#sbaw.function_call
class SBAWFunctionCall(BaseModel):
	id: str
	call_id: str
	name: str
	arguments: Dict
	role: str = 'assistant'
	type: str = 'function_call'
	created_timestamp: Optional[str]
	# TODO: serialize method for arguments to JSON

#sbaw.function_result
class SBAWFunctionResult(BaseModel):
	id: str
	call_id: str
	name: str
	result: Any
	role: str = 'system'
	type: str = 'function_result'
	created_timestamp: Optional[str]