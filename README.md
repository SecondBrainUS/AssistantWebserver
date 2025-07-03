# AssistantWebserver

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=flat&logo=python)](https://www.python.org)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-5.11.4-black.svg?style=flat&logo=socket.io)](https://socket.io/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.9.0-47A248.svg?style=flat&logo=mongodb)](https://www.mongodb.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-2.9.10-336791.svg?style=flat&logo=postgresql)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?style=flat&logo=docker)](https://www.docker.com)

</div>

A real-time web server for AI assistants with a flexible room-based architecture, Socket.IO chat system, and extensive tool integration. Designed to provide a seamless, real-time AI assistant experience with support for multiple models and a robust tooling system.

- [📚 Documentation](#-documentation)
- [✨ Features](#-features)
- [🏗️ Architecture](#-architecture)
- [🔧 Installation and Setup](#-installation-and-setup)
- [🚀 Deployment](#-deployment)
- [🧰 Development](#-development)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)

## 📚 Documentation

- [API Documentation](#) - Detailed API documentation (when server is running)
- [Socket.IO Events](docs/SOCKETIO_EVENTS.md) - Documentation for all Socket.IO events
- [Tool System](docs/TOOLS.md) - Details about the available tools and how to implement new ones
- [Authentication System](docs/AUTH.md) - Details about the Google Sign-In authentication system
- [Database Schema](docs/DATABASE.md) - Information about database schemas and relationships

## ✨ Features

### Real-time Chat System

The AssistantWebserver provides a powerful real-time chat system built with Socket.IO. The system features:

- **Real-time Communication**: Seamless Socket.IO-based chat with immediate responses and updates
- **Room-based Architecture**: Flexible system for managing multiple concurrent chat sessions
- **Multiple Model Support**: Compatible with various AI models like OpenAI, Anthropic, and custom implementations
- **Persistent Chat History**: All conversations are stored in MongoDB for future reference
- **Session Management**: User sessions are efficiently managed with Memcached
- **User Authentication**: Google Sign-In integration for secure access

### Flexible AssistantRoom System

The core of the system is the `AssistantRoom` architecture which provides a flexible framework that can be extended to support various AI implementations:

```
AssistantRoom (Abstract Base Class)
├── OpenAiRealTimeRoom
└── AiSuiteRoom
```

#### Base AssistantRoom Class

The `AssistantRoom` class provides the foundation with:

- Core room management for handling user connections
- Message broadcasting to all connected clients
- Tool integration for extending assistant capabilities
- Metrics collection for monitoring performance
- Abstracted interfaces for derived classes

#### Implementations

- **AiSuiteRoom**: Integrates with custom AI suite for advanced capabilities:
  - Custom tool chaining and function calling
  - Session customization for specific use cases
  - Specialized response handling

- **OpenAiRealTimeRoom**: Provides real-time interaction with OpenAI models:
  - Streaming responses for better user experience
  - Tool execution with automatic function calling
  - Session state management

### Comprehensive Tool System

The AssistantWebserver includes a robust tool system that extends the assistant's capabilities:

| Category | Tools | Description |
|----------|-------|-------------|
| **Finance** | `stocks.py`, `finance.py` | Stock data, portfolio management, watchlists |
| **Productivity** | `notion.py`, `google_calendar_helper.py` | Notion integration, calendar management |
| **Media** | `spotify.py`, `tidal.py` | Music service integration and control |
| **Search** | `perplexity.py`, `brightdata_search_tool.py` | Web search capabilities |
| **IoT** | `sensor_values.py` | Sensor data integration |

Each tool is designed to be:
- **Modular**: Easy to add or remove without affecting other parts of the system
- **Well-documented**: Clear documentation on how to use each tool
- **Function Mapped**: Exposed through a consistent interface for AI models to use
- **Error Resilient**: Proper error handling for robust operation

## 🏗️ Architecture

### System Overview

```mermaid
graph TD
    Client[Client Browser] <-->|Socket.IO| SIO[Socket.IO Server]
    Client <-->|HTTP| API[FastAPI Server]
    SIO --> RM[Room Manager]
    RM --> AR1[AssistantRoom 1]
    RM --> AR2[AssistantRoom 2]
    AR1 --> Tools[Tools System]
    AR2 --> Tools
    API --> Auth[Auth System]
    Auth --> DB1[(PostgreSQL)]
    Auth --> MC[(Memcached)]
    AR1 --> DB2[(MongoDB)]
    AR2 --> DB2
```

### Database Architecture

The system utilizes multiple databases for different purposes:

#### MongoDB
- **Purpose**: Stores chat messages and conversation history
- **Collections**: 
  - `messages`: Individual messages with metadata
  - `chats`: Grouped conversations
  - `tool_data`: Specific data for various tools
- **Benefits**: Flexible schema for storing varied message types and tool outputs

#### PostgreSQL
- **Purpose**: User authentication and profile management
- **Tables**:
  - `users`: Core user information
  - `auth_google`: Google authentication details
  - `user_sessions`: Active sessions
- **Benefits**: Strong relational integrity for user data and auth relationships

#### Memcached
- **Purpose**: Temporary session storage and caching
- **Keys**:
  - `session:{session_id}`: User session data
  - `token:{token_id}`: Short-lived authentication tokens
- **Benefits**: Fast, in-memory caching for session data

### Authentication Flow

```mermaid
sequenceDiagram
    Client->>Server: Request login (Google)
    Server->>Google: Redirect to OAuth
    Google->>Client: OAuth consent
    Client->>Google: Approve
    Google->>Server: Callback with code
    Server->>Google: Exchange code for token
    Google->>Server: Return user info & token
    Server->>DB: Create/update user
    Server->>Memcached: Store session
    Server->>Client: Set cookies & redirect
```

## 🔧 Installation and Setup

### Prerequisites

- Python 3.11+
- PostgreSQL
- MongoDB
- Memcached
- Google OAuth credentials

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/AssistantWebserver.git
   cd AssistantWebserver
   ```

2. Set up a virtual environment with Poetry:
   ```bash
   pip install poetry
   poetry install
   ```

3. Create your environment file:
   ```bash
   cp env/.env.example env/.env.local
   ```

4. Configure the required environment variables in `.env.local`:

   ```
   # System
   SYSTEM_MODE=development
   PORT=8000

   # Database URLs
   ASSISTANTDB_URL=postgresql://user:password@localhost:5432/assistant
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DB_NAME=assistant
   
   # Memcache
   MEMCACHE_HOST=localhost
   MEMCACHE_PORT=11211
   
   # Authentication
   BASE_URL=http://localhost:8000
   FRONTEND_URL=http://localhost:3000
   JWT_SECRET_KEY=your-secret-key
   JWT_ALGORITHM=HS256
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   ACCESS_TOKEN_EXPIRE_MINUTES=1440
   REFRESH_TOKEN_EXPIRE_DAYS=7
   
   # API Keys (only configure what you need)
   OPENAI_API_KEY=your-openai-key
   ANTHROPIC_API_KEY=your-anthropic-key
   NOTION_API_KEY=your-notion-key
   # ... other API keys as needed
   ```

### Database Setup

1. PostgreSQL initialization:
   ```bash
   # Create the database
   createdb assistant
   
   # The tables will be created automatically on first run
   ```

2. MongoDB initialization:
   ```bash
   # No specific setup required, MongoDB will create collections as needed
   ```

3. Memcached:
   ```bash
   # Start memcached server
   memcached -d -p 11211
   ```

### Running the Server

```bash
# Development mode with auto-reload
poetry run dev

# Or
poetry run serve
```

The server will be available at `http://localhost:8000`

## 🚀 Deployment

### Docker Deployment

A Dockerfile is provided for containerized deployment:

```bash
# Build the Docker image
docker build -t assistant-webserver .

# Run the container
docker run -p 8000:8000 --env-file env/.env.docker assistant-webserver
```

### Production Deployment
CMD:
load-env.bat
PS:
$env:GITHUB_TOKEN = (Get-Content .env.build | Select-String "^GITHUB_TOKEN=") -replace "GITHUB_TOKEN=", ""

docker build -t assistant-webserver --build-arg GITHUB_TOKEN=%GITHUB_TOKEN% .



## 🧰 Development

### Project Structure

```
AssistantWebserver/
├── webserver/                # Main application code
│   ├── api/                  # FastAPI endpoints
│   │   └── api_v1/           # API version 1
│   ├── db/                   # Database connections
│   │   ├── assistantdb/      # PostgreSQL models
│   │   ├── chatdb/           # MongoDB connection
│   │   └── memcache/         # Memcached client
│   ├── middleware/           # FastAPI middleware
│   ├── sbsocketio/           # Socket.IO implementation
│   │   ├── namespaces/       # Socket.IO namespaces
│   │   └── models/           # Socket.IO models
│   ├── tools/                # AI assistant tools
│   └── util/                 # Utility functions
├── docs/                     # Documentation
├── logs/                     # Log files
├── secrets/                  # Secret files (.gitignored)
├── env/                      # Environment files
├── .venv/                    # Poetry virtual environment
├── pyproject.toml            # Project dependencies
└── poetry.lock               # Locked dependencies
```

### Creating New Tools

To create a new tool:

1. Create a new file in the `webserver/tools/` directory
2. Implement the required functions
3. Create a `get_tool_function_map()` function that returns the tool's interface
4. Add the tool to the AssistantRoom implementation

Example:

```python
# webserver/tools/example_tool.py
def do_something(param1: str, param2: int) -> dict:
    """
    Does something useful with the parameters.
    
    Args:
        param1: First parameter
        param2: Second parameter
        
    Returns:
        Dictionary with the result
    """
    result = {"done": True, "value": f"{param1}: {param2}"}
    return result

def get_tool_function_map():
    """Get the tool function map for example tool"""
    return {
        "example_do_something": {
            "function": do_something,
            "description": "Does something useful",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "First parameter"
                    },
                    "param2": {
                        "type": "integer",
                        "description": "Second parameter"
                    }
                },
                "required": ["param1", "param2"]
            },
            "system_prompt_description": "Use example_do_something when you need to do something useful."
        }
    }
```

### Creating a New AssistantRoom Implementation

To create a new AssistantRoom implementation:

1. Create a new file in the `webserver/sbsocketio/` directory
2. Extend the `AssistantRoom` base class
3. Implement the required abstract methods
4. Register the new room type in the `AssistantRoomManager`

## 📜 License

This project is licensed under the [MIT License](LICENSE).


def create_server_token(self, expire_minutes: int = 15) -> str:
    """Create a signed JWT token for server authentication"""
    payload = {
        "client_id": self.client_id,
        "token_type": "server",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=expire_minutes),
        "iat": datetime.datetime.utcnow()
    }
    
    return jwt.encode(payload, self.private_key, algorithm="RS256")
    token = self.create_server_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }