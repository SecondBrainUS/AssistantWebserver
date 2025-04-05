# AssistantWebserver

A real-time web server for AI assistants with flexible room-based architecture, socket.io chat system, and extensive tool integration.

## Features

### Real-time Chat System
- Socket.io-based real-time communication
- Room-based architecture for managing multiple chat sessions
- Support for multiple AI model sources
- Chat persistence in MongoDB
- User session management with Memcached

### Flexible AssistantRoom System
The system uses a flexible room-based architecture that allows for custom AI class implementations. The base `AssistantRoom` class provides core functionality that can be extended by specific implementations:

- `AssistantRoom` (Base Class)
  - Core room management
  - User connection handling
  - Message broadcasting
  - Tool integration
  - Metrics collection

- `AiSuiteRoom` (Implementation)
  - Custom AI suite integration
  - Advanced tool chaining
  - Session customization
  - Response handling

- `OpenAiRealTimeRoom` (Implementation)
  - Real-time OpenAI API integration
  - Streaming responses
  - Tool execution
  - Session management

### Tool System
The server integrates with various tools and services:

- **Media Services**
  - Spotify integration
  - Tidal music service
  - Media playback control

- **Finance Tools**
  - Stock data retrieval
  - Portfolio management
  - Watchlist functionality

- **Notion Integration**
  - Database operations
  - Page management
  - Content organization

- **Calendar Integration**
  - Google Calendar access
  - Event management
  - Schedule queries

- **Search and Research**
  - Perplexity search
  - Brightdata web search
  - Custom search tools

- **Sensor Data**
  - Real-time sensor readings
  - Data visualization
  - Monitoring tools

## Database Architecture

### MongoDB
- Stores chat messages
- Maintains conversation history
- Handles tool-specific data (e.g., finance data)

### PostgreSQL
- User authentication
- User profiles
- Session management
- Access control

### Memcached
- User session caching
- Temporary data storage
- Performance optimization

## Authentication

The system currently supports Google Sign-In as the only authentication method:

- OAuth 2.0 implementation
- JWT token management
- Session persistence
- Whitelist-based access control
- Secure token refresh mechanism

## API Endpoints

### Authentication
- `/api/v1/auth/google/login` - Initiate Google Sign-In
- `/api/v1/auth/google/callback` - Handle Google OAuth callback
- `/api/v1/auth/validate-token` - Validate authentication tokens
- `/api/v1/auth/me` - Get current user information

### Chat System
- Socket.io namespace: `/assistant/realtime`
- Events:
  - `create_room` - Create new chat room
  - `join_room` - Join existing room
  - `leave_room` - Leave room
  - `send_message` - Send message to room
  - `receive_message` - Receive message from room
  - `room_created` - Room creation confirmation
  - `room_joined` - Room join confirmation
  - `room_left` - Room leave confirmation

## Security Features

- JWT-based authentication
- CSRF protection
- Rate limiting
- Input validation
- Secure session management
- Whitelist-based access control
- Secure token storage and refresh

## Monitoring and Metrics

The system includes comprehensive monitoring through Prometheus metrics:

- Authentication metrics
- Function call tracking
- Response monitoring
- Error tracking
- Room event monitoring
- User message tracking

## Dependencies

- FastAPI
- Socket.io
- MongoDB
- PostgreSQL
- Memcached
- Google OAuth
- Various API clients for integrated services

## Configuration

The server requires configuration for:
- Database connections
- API keys
- OAuth credentials
- Service endpoints
- Security settings

## Development

To set up the development environment:
1. Install dependencies
2. Configure environment variables
3. Set up required databases
4. Configure OAuth credentials
5. Start the development server