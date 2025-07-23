import logging
from openai import OpenAI
from webserver.config import settings
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from typing import List, Dict, Any, Optional
from webserver.api.dependencies import verify_server_token
from webserver.tools.stocks import get_tool_function_map as get_stocks_tool_map
from webserver.tools.spotify import get_tool_function_map as get_spotify_tool_map
from webserver.tools.tidal import get_tool_function_map as get_tidal_tool_map
from webserver.tools.notion import get_tool_function_map as get_notion_tool_map
from webserver.tools.google_calendar_helper import get_tool_function_map as get_gcal_tool_map
from webserver.tools.sensor_values import get_tool_function_map as get_sensor_tool_map
from webserver.tools.finance import get_tool_function_map as get_finance_tool_map
# from webserver.tools.brightdata_search_tool import get_tool_function_map as get_brightdata_tool_map
# from webserver.tools.perplexity import get_tool_function_map as get_perplexity_tool_map

router = APIRouter()
logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)

@router.post("/raw", dependencies=[Depends(verify_server_token)])
async def chat_completion_server(
    request: Request,
):
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Failed to parse request body: %s", e)
        raise HTTPException(status_code=400, detail="Failed to parse request body") from e

    model = body.get("model", "gpt-4o-search-preview")
    messages = body.get("messages", None)
    if not messages:
        raise HTTPException(status_code=401, detail="No messages provided.")
    web_search_options = body.get("web_search_options", {})

    # system_message = {
    #     "role": "system",
    #     "content": "Limit the message to...",
    # }
    # messages.insert(0, system_message)

    completion = client.chat.completions.create(
      model=model,
      web_search_options=web_search_options,
      messages=messages,
    )
    return {"content": completion.choices[0].message.content}
