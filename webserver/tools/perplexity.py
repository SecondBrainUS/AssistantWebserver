from openai import OpenAI
from webserver.config import settings
from typing import Dict
import logging

logger = logging.getLogger(__name__)

async def query_perplexity(query: str) -> Dict:
    """Perform a live internet search query using Perplexity AI"""
    try:
        client = OpenAI(
            api_key=settings.PERPLEXITY_API_KEY, 
            base_url="https://api.perplexity.ai"
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an artificial intelligence assistant and you need to "
                    "engage in a helpful, detailed, polite conversation with a user."
                ),
            },
            {   
                "role": "user",
                "content": query,
            },
        ]

        response = client.chat.completions.create(
            model="sonar-pro",
            messages=messages,
        )
        
        return {
            "result": response.choices[0].message.content,
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
            "description": "Perform a live search query using Perplexity AI to get up-to-date information from the internet",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to perform",
                    }
                },
                "required": ["query"],
            },
        },
    }