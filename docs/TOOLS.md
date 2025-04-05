# Tools System

The AssistantWebserver includes a comprehensive tools system that enables AI assistants to perform various actions and access external services. This document explains the architecture, available tools, and how to extend the system with new tools.

## Architecture

The tools system follows a modular architecture where each tool:

1. Implements one or more functions that perform specific actions
2. Provides metadata about its functions (parameters, descriptions, etc.)
3. Exposes a standard interface for AI models to discover and use

### Tool Function Map

Each tool exposes its capabilities through a `get_tool_function_map()` function that returns a dictionary mapping function names to metadata:

```python
{
    "tool_function_name": {
        "function": actual_function_reference,
        "description": "Human-readable description",
        "parameters": {
            # OpenAI-style function definition
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
        "system_prompt_description": "Description for the system prompt"
    }
}
```

### Integration with AssistantRoom

The `AssistantRoom` base class integrates all available tools:

1. On initialization, it imports tool maps from all registered tools
2. It merges these maps into a single `tool_map` dictionary
3. It generates a tool usage guide from the system prompt descriptions
4. When AI calls a function, it routes the call to the appropriate tool

## Available Tools

### Finance Tools

#### Stocks Tool (`stocks.py`)

Provides stock market functionality:

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

#### Finance Tool (`finance.py`)

Provides financial data access:

- `get_stock_data`: Get historical stock data
- `get_current_stock_price`: Get current stock price

### Productivity Tools

#### Notion Tool (`notion.py`)

Enables interaction with Notion workspaces:

- `notion_get_database_properties`: Get properties of a Notion database
- `notion_search_database`: Search for a Notion database by name
- `notion_get_database`: Get a Notion database by ID
- `notion_query_database`: Query a Notion database with filters
- `notion_add_item`: Add a new item to a Notion database
- `notion_list_databases`: List all accessible Notion databases

#### Google Calendar Tool (`google_calendar_helper.py`)

Provides Google Calendar integration:

- `gcal_get_events`: Get calendar events in a date range
- `gcal_create_event`: Create a new calendar event
- `gcal_update_event`: Update an existing event
- `gcal_delete_event`: Delete an event
- `gcal_get_calendars`: List available calendars

### Media Tools

#### Spotify Tool (`spotify.py`)

Controls Spotify playback:

- `spotify_get_devices`: Get available Spotify devices
- `spotify_play`: Start playback
- `spotify_pause`: Pause playback
- `spotify_next_track`: Skip to next track
- `spotify_previous_track`: Go to previous track
- `spotify_search`: Search for tracks, albums, or artists
- `spotify_create_playlist`: Create a new playlist
- `spotify_add_to_playlist`: Add tracks to a playlist

#### Tidal Tool (`tidal.py`)

Controls Tidal music service:

- `tidal_search`: Search for music on Tidal
- `tidal_play`: Play a track, album, or playlist
- `tidal_pause`: Pause playback
- `tidal_resume`: Resume playback
- `tidal_next_track`: Skip to next track
- `tidal_previous_track`: Go to previous track

### Search Tools

#### Perplexity Tool (`perplexity.py`)

Provides advanced search capabilities:

- `perplexity_search`: Perform a search query using Perplexity API
- `perplexity_summarize`: Summarize a webpage or document

#### Brightdata Search Tool (`brightdata_search_tool.py`)

Performs web scraping and search:

- `brightdata_search`: Perform a web search
- `brightdata_get_webpage`: Get content from a webpage
- `brightdata_extract_data`: Extract structured data from a webpage

### IoT Tools

#### Sensor Values Tool (`sensor_values.py`)

Interacts with sensor systems:

- `get_sensor_values`: Get current sensor readings
- `get_sensor_history`: Get historical sensor data
- `get_sensor_alerts`: Get alerts from sensors

## Creating New Tools

To create a new tool:

1. Create a new Python file in the `webserver/tools/` directory
2. Implement your tool functions
3. Create a `get_tool_function_map()` function that returns a dictionary mapping function names to their metadata
4. Import and add your tool in the `AssistantRoom` initialization

### Example: Creating a Weather Tool

```python
# webserver/tools/weather.py
import requests
from typing import Dict, Any

def get_current_weather(location: str, units: str = "metric") -> Dict[str, Any]:
    """
    Get current weather for a location
    
    Args:
        location: City name or coordinates
        units: Units system (metric/imperial)
        
    Returns:
        Weather data dictionary
    """
    # Implementation
    api_key = "your_api_key"
    response = requests.get(
        f"https://api.example.com/weather?location={location}&units={units}&key={api_key}"
    )
    return response.json()

def get_forecast(location: str, days: int = 5, units: str = "metric") -> Dict[str, Any]:
    """
    Get weather forecast for a location
    
    Args:
        location: City name or coordinates
        days: Number of days for forecast
        units: Units system (metric/imperial)
        
    Returns:
        Forecast data dictionary
    """
    # Implementation
    api_key = "your_api_key"
    response = requests.get(
        f"https://api.example.com/forecast?location={location}&days={days}&units={units}&key={api_key}"
    )
    return response.json()

def get_tool_function_map():
    """Get the tool function map for weather-related functions"""
    return {
        "weather_get_current": {
            "function": get_current_weather,
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or coordinates"
                    },
                    "units": {
                        "type": "string",
                        "description": "Units system (metric/imperial)",
                        "enum": ["metric", "imperial"],
                        "default": "metric"
                    }
                },
                "required": ["location"]
            },
            "system_prompt_description": "Use weather_get_current to get the current weather conditions for a specific location."
        },
        "weather_get_forecast": {
            "function": get_forecast,
            "description": "Get weather forecast for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or coordinates"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days for forecast",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "units": {
                        "type": "string",
                        "description": "Units system (metric/imperial)",
                        "enum": ["metric", "imperial"],
                        "default": "metric"
                    }
                },
                "required": ["location"]
            },
            "system_prompt_description": "Use weather_get_forecast to get a weather forecast for a specific location for multiple days."
        }
    }
```

### Integrating Your Tool

To integrate your new tool, modify the `AssistantRoom` initialization in `assistant_room.py`:

```python
# Import your tool
from webserver.tools.weather import get_tool_function_map as get_weather_tool_map

# In the AssistantRoom.__init__ method
weather_tool_map = get_weather_tool_map()

# Add to the tool_map dictionary
self.tool_map = {
    # Existing tools...
    **weather_tool_map
}
```

## Best Practices

1. **Error Handling**: Each tool function should handle errors gracefully and return informative error messages
2. **Documentation**: Provide detailed docstrings and parameter descriptions
3. **Type Hinting**: Use Python type hints for better IDE support and documentation
4. **Statelessness**: Design tools to be stateless when possible
5. **Security**: Never expose API keys directly in code, use environment variables
6. **Testing**: Write tests for your tool functions to ensure reliability
7. **Monitoring**: Include appropriate logging for easier debugging 