# Tools Directory

This directory contains the tools and integrations that extend the AI assistants' capabilities. Each tool provides functionality that can be accessed by AI models through a standardized interface.

## Overview

The tools system is designed to be:

- **Extensible**: Easy to add new tools
- **Standardized**: Consistent interface for all tools
- **Documented**: Clear documentation for each tool
- **Discoverable**: Tools self-describe their capabilities

## Tool Structure

Each tool follows a common structure:

1. **Function Implementation**: The actual code that performs the task
2. **Function Map**: A function that returns metadata about the tool's capabilities
3. **System Prompt Description**: Information for the AI about how to use the tool

## Available Tools

### Finance Tools

#### `stocks.py`

Provides stock portfolio and watchlist management:

- `create_watchlist`: Create a stock watchlist
- `delete_watchlist`: Delete a stock watchlist
- `list_watchlists`: List all watchlists
- `get_watchlist`: Get watchlist details
- `add_tickers_to_watchlist`: Add tickers to a watchlist
- `remove_tickers_from_watchlist`: Remove tickers from a watchlist
- `create_portfolio`: Create a stock portfolio
- `delete_portfolio`: Delete a stock portfolio
- `list_portfolios`: List all portfolios
- `get_portfolio`: Get portfolio details
- `add_position_to_portfolio`: Add a position to a portfolio
- `remove_position_from_portfolio`: Remove a position from a portfolio

#### `finance.py`

Provides financial data access:

- `get_stock_data`: Get historical stock data
- `get_current_stock_price`: Get current stock price

### Productivity Tools

#### `notion.py`

Enables interaction with Notion workspaces:

- `notion_get_database_properties`: Get properties of a Notion database
- `notion_search_database`: Search for a Notion database by name
- `notion_get_database`: Get a Notion database by ID
- `notion_query_database`: Query a Notion database with filters
- `notion_add_item`: Add a new item to a Notion database
- `notion_list_databases`: List all accessible Notion databases

#### `google_calendar_helper.py`

Provides Google Calendar integration:

- `gcal_get_events`: Get calendar events in a date range
- `gcal_create_event`: Create a new calendar event
- `gcal_update_event`: Update an existing event
- `gcal_delete_event`: Delete an event
- `gcal_get_calendars`: List available calendars

### Media Tools

#### `spotify.py`

Controls Spotify playback:

- `spotify_get_devices`: Get available Spotify devices
- `spotify_play`: Start playback
- `spotify_pause`: Pause playback
- `spotify_next_track`: Skip to next track
- `spotify_previous_track`: Go to previous track
- `spotify_search`: Search for tracks, albums, or artists
- `spotify_create_playlist`: Create a new playlist
- `spotify_add_to_playlist`: Add tracks to a playlist

#### `tidal.py`

Controls Tidal music service:

- `tidal_search`: Search for music on Tidal
- `tidal_play`: Play a track, album, or playlist
- `tidal_pause`: Pause playback
- `tidal_resume`: Resume playback
- `tidal_next_track`: Skip to next track
- `tidal_previous_track`: Go to previous track

### Search Tools

#### `perplexity.py`

Provides advanced search capabilities:

- `perplexity_search`: Perform a search query using Perplexity API
- `perplexity_summarize`: Summarize a webpage or document

#### `brightdata_search_tool.py`

Performs web scraping and search:

- `brightdata_search`: Perform a web search
- `brightdata_get_webpage`: Get content from a webpage
- `brightdata_extract_data`: Extract structured data from a webpage

### IoT Tools

#### `sensor_values.py`

Interacts with sensor systems:

- `get_sensor_values`: Get current sensor readings
- `get_sensor_history`: Get historical sensor data
- `get_sensor_alerts`: Get alerts from sensors

## Standard Implementation Pattern

Each tool file follows a standard implementation pattern:

```python
# Import section
from typing import Dict, List, Any, Optional
import logging
from webserver.config import settings

logger = logging.getLogger(__name__)

# Function implementations
def example_function(param1: str, param2: int = 0) -> Dict[str, Any]:
    """
    Example function description
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        
    Returns:
        Dictionary with results
        
    Raises:
        Exception: When something goes wrong
    """
    # Function implementation
    result = {"param1": param1, "param2": param2}
    return result

# Tool map function
def get_tool_function_map() -> Dict[str, Dict[str, Any]]:
    """Get the tool function map for this tool's functions"""
    return {
        "example_function_name": {
            "function": example_function,
            "description": "Human-readable description",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Description of parameter 1"
                    },
                    "param2": {
                        "type": "integer",
                        "description": "Description of parameter 2",
                        "default": 0
                    }
                },
                "required": ["param1"]
            },
            "system_prompt_description": "Use example_function_name when you need to do X with Y and Z."
        },
        # Additional functions...
    }
```

## Integration with AssistantRoom

Tools are integrated with the AssistantRoom class in `assistant_room.py`:

```python
# Import tool maps
from webserver.tools.stocks import get_tool_function_map as get_stocks_tool_map
from webserver.tools.finance import get_tool_function_map as get_finance_tool_map
# ...other imports

class AssistantRoom:
    def __init__(self, ...):
        # ...other initialization
        
        # Get tool maps from all sources
        stocks_tool_map = get_stocks_tool_map()
        finance_tool_map = get_finance_tool_map()
        # ...other tool maps
        
        # Merge all tool maps
        self.tool_map = {
            **stocks_tool_map,
            **finance_tool_map,
            # ...other tool maps
        }
```

## Creating New Tools

To create a new tool:

1. Create a new Python file in this directory
2. Implement your tool functions
3. Create a `get_tool_function_map()` function
4. Import and add your tool map in `assistant_room.py`

For more detailed instructions on creating new tools, see the [Tools Documentation](../../docs/TOOLS.md).

## Tool Function Map Format

The function map follows this format:

```python
{
    "tool_name": {
        "function": actual_function_reference,
        "description": "Human-readable description for documentation",
        "parameters": {
            # OpenAI-style function definition (JSON Schema)
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Description of param1"
                },
                # ... more parameters
            },
            "required": ["param1"]
        },
        "system_prompt_description": "Description used in AI system prompts"
    }
}
```

## Best Practices

1. **Error Handling**: Always handle errors gracefully within tool functions
2. **Type Hints**: Use proper Python type hints
3. **Documentation**: Include detailed docstrings
4. **Statelessness**: Design tools to be stateless when possible
5. **Configuration**: Use environment variables for API keys and config
6. **Logging**: Include appropriate logging for debugging
7. **Testing**: Write unit tests for your tools 