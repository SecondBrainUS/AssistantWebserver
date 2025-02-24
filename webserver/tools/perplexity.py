import requests
from webserver.config import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

async def query_perplexity(
    query: str,
    max_tokens: Optional[int] = None,
    temperature: float = 0.2,
    top_p: float = 0.9,
    search_domain_filter: Optional[list] = None,
    return_images: bool = False,
    return_related_questions: bool = False,
    search_recency_filter: str = "month",
    top_k: int = 0,
    stream: bool = False,
    presence_penalty: float = 0,
    frequency_penalty: float = 1,
) -> Dict:
    """Perform a live internet search query using Perplexity AI"""
    try:
        url = "https://api.perplexity.ai/chat/completions"
        
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "Be precise and concise."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "temperature": temperature,
            "top_p": top_p,
            "return_images": return_images,
            "return_related_questions": return_related_questions,
            "search_recency_filter": search_recency_filter,
            "top_k": top_k,
            "stream": stream,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty
        }

        # Add optional parameters if provided
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if search_domain_filter:
            payload["search_domain_filter"] = search_domain_filter

        headers = {
            "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        return {
            "result": data["choices"][0]["message"]["content"],
            "citations": data.get("citations", []),
            "usage": data.get("usage", {}),
            "success": True
        }
    except Exception as e:
        logger.error(f"Error querying Perplexity: {e}")
        return {
            "error": str(e),
            "success": False
        }

def get_tool_function_map():
    """Get the tool function map for Perplexity-related functions"""
    return {
        "query_perplexity": {
            "function": query_perplexity,
            "description": ( "Perform a live search query using Perplexity AI to get up-to-date information from the internet."
                            "If the user specified time or recency, use the argument for it instead of including it in the query."
                            "Do NOT apply max tokens unless specified by the user" 
                            "When asked about multiple topics or a list of items, perform one search per item instead of searching them all at once."
                            ),

            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to perform",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum number of tokens to generate",
                        "optional": True
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature (0-1)",
                        "default": 0.2,
                        "optional": True
                    },
                    "top_p": {
                        "type": "number",
                        "description": "Nucleus sampling parameter",
                        "default": 0.9,
                        "optional": True
                    },
                    "search_domain_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of domains to filter search results",
                        "optional": True
                    },
                    "search_recency_filter": {
                        "type": "string",
                        "description": "Time filter for search results",
                        "default": "month",
                        "optional": True
                    }
                },
                "required": ["query"],
            },
        },
    }