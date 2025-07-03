# API Overview

This document provides a comprehensive overview of all available APIs in your FastAPI application.

## Base URL Structure

- **Base Path**: Configured via `settings.BASE_PATH`
- **API Version 1**: `/api/v1`
- **Internal APIs**: `/internal`
- **Socket.IO**: `/socket.io` (real-time communication)

---

## REST API Endpoints

### 🔐 Authentication APIs (`/api/v1/auth`)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `GET` | `/{provider}/login` | Redirect to OAuth provider login (supports `google`) | ❌ |
| `GET` | `/{provider}/callback` | OAuth callback handler | ❌ |
| `GET` | `/login-success-redirect` | Post-login redirect handler | ❌ |
| `GET` | `/validate-token` | Validate temporary token and set auth cookies | ❌ |
| `GET` | `/me` | Get current user profile | ✅ |
| `POST` | `/logout` | Logout and clear auth cookies | ❌ |
| `POST` | `/refresh` | Refresh access token using refresh token | ✅ |

### 💬 Chat Management APIs (`/api/v1/chat`)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `GET` | `` | Get paginated list of user's chats | ✅ |
| `POST` | `` | Create a new chat | ✅ |
| `GET` | `/{chat_id}` | Get specific chat details | ✅ |
| `DELETE` | `/{chat_id}` | Delete a chat and its messages | ✅ |
| `GET` | `/{chat_id}/messages` | Get messages for a chat | ✅ |
| `POST` | `/{chat_id}/upload` | Upload files to a chat | ✅ |
| `GET` | `/{chat_id}/files` | List files in a chat | ✅ |
| `GET` | `/{chat_id}/files/{file_id}` | Download a specific file | ✅ |
| `DELETE` | `/{chat_id}/files/{file_id}` | Delete a file from a chat | ✅ |

### 🤖 AI Execution APIs (`/api/v1/run`)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `POST` | `/` | Execute AI assistant with multimodal input (text, audio, images, video) | ✅ |
| `POST` | `/audio` | Execute AI assistant and return audio response | ✅ |

### 🧠 AI Suite LLM APIs (`/api/v1/aisuite`)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `POST` | `/chat` | Chat completion using configurable AI models (OpenAI, Anthropic, Groq, AWS) | ✅ |

### 📝 Prompt Engineering APIs (`/api/v1/prompt_compiler`)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `POST` | `/compile/form` | Compile prompt and generate parameter form schema | ✅ |
| `POST` | `/compile` | Simple prompt compilation and optimization | ✅ |
| `POST` | `/update_parameters` | Extract parameter values from prompt text | ✅ |

### 🎯 Model Management APIs (`/api/v1/model`)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `GET` | `` | Get list of available models with pagination | ✅ |

### 🔧 Internal APIs (`/internal`)

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `GET` | `/health` | Health check endpoint for monitoring | ❌ |
| `GET` | `/metrics` | Prometheus metrics endpoint | ❌ |

---

## Socket.IO Real-Time APIs

### Base Socket.IO Connection
- **URL**: `/socket.io`
- **Protocol**: WebSocket with Socket.IO
- **Authentication**: Required for most namespaces

### 🏠 Default Namespace (`/`)
Basic Socket.IO connection handling and user management.

### 🤖 Assistant Realtime Namespace (`/assistant/realtime`)
Real-time AI assistant interactions with the following events:

#### Client → Server Events
- `connect` - Establish authenticated connection
- `create_room` - Create new assistant room
- `join_room` - Join existing assistant room
- `leave_room` - Leave assistant room
- `send_message` - Send message to assistant
- `disconnect` - Close connection

#### Server → Client Events
- `room_created` - Room creation confirmation
- `room_joined` - Room join confirmation
- `message_received` - New message from assistant
- `error` - Error notifications
- `user_joined` - Another user joined room
- `user_left` - User left room

#### Assistant Room Types
1. **OpenAI Realtime**: Streaming OpenAI API integration
2. **AI Suite**: Multi-provider AI integration (OpenAI, Anthropic, Groq, AWS)

---

## Authentication Flow

### OAuth Login Flow
1. `GET /api/v1/auth/google/login` - Redirect to Google OAuth
2. `GET /api/v1/auth/google/callback` - Handle OAuth callback
3. `GET /api/v1/auth/login-success-redirect` - Process temporary token
4. `GET /api/v1/auth/validate-token` - Validate token and set cookies

### Token Management
- **Access Token**: Short-lived (configurable minutes), stored in HTTP-only cookie
- **Refresh Token**: Long-lived (configurable days), stored in HTTP-only cookie  
- **Session ID**: Maps to user data in cache and database

---

## Data Models

### Chat Structure
```json
{
  "chat_id": "uuid",
  "user_id": "string",
  "current_model_id": "string",
  "current_model_api_source": "string",
  "created_timestamp": "datetime",
  "files": [...]
}
```

### Message Structure
```json
{
  "message_id": "uuid",
  "chat_id": "string",
  "role": "user|assistant|system",
  "content": "string",
  "files": ["file_id_array"],
  "timestamp": "datetime"
}
```

### File Structure
```json
{
  "fileid": "uuid",
  "filename": "string",
  "uploaded_at": "datetime",
  "userid": "string",
  "content_type": "string",
  "size": "integer",
  "object_key": "string"
}
```

---

## Supported AI Providers

### Via AI Suite (`/api/v1/aisuite`)
- **OpenAI**: GPT models (requires `OPENAI_API_KEY`)
- **Anthropic**: Claude models (requires `ANTHROPIC_API_KEY`)
- **Groq**: Fast inference models (requires `GROQ_API_KEY`)
- **AWS**: Bedrock models (requires AWS credentials)

### Via Direct Integration (`/api/v1/run`)
- **OpenAI**: GPT models with function calling
- **Google Calendar**: Integration via service account
- **Notion**: Integration for notes and task management

---

## File Upload & Storage

### Supported Operations
- Upload files to chats (multiple file support)
- Download files with proper content types
- Delete files (idempotent)
- List files in a chat

### Storage Backend
- **S3-compatible storage** for file persistence
- **MongoDB** for file metadata
- **Automatic cleanup** when chats are deleted

---

## Error Handling

### HTTP Status Codes
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid/expired token)
- `404` - Not Found (resource doesn't exist)
- `500` - Internal Server Error

### Socket.IO Error Events
- Connection errors sent via `error` event
- Room-specific errors broadcast to room members
- Authentication failures close connection

---

## Rate Limiting & Security

### Security Features
- **JWT-based authentication** with access/refresh tokens
- **HTTP-only cookies** for token storage
- **CORS middleware** with configurable origins
- **User whitelist** for email-based access control
- **Session management** with database persistence

### Monitoring
- **Prometheus metrics** at `/internal/metrics`
- **Health checks** at `/internal/health`
- **Comprehensive logging** with structured format

---

## Configuration

Key environment variables:
- `OPENAI_API_KEY` - OpenAI API access
- `ANTHROPIC_API_KEY` - Anthropic API access
- `GROQ_API_KEY` - Groq API access
- `JWT_SECRET_KEY` - JWT token signing
- `BASE_URL` - Application base URL
- `BASE_PATH` - API base path
- Database and storage credentials

---

## Usage Examples

### Create Chat and Send Message
```bash
# 1. Create chat
curl -X POST "/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "gpt-4", "model_api_source": "openai"}'

# 2. Upload file
curl -X POST "/api/v1/chat/{chat_id}/upload" \
  -F "files=@document.pdf"

# 3. Get messages
curl -X GET "/api/v1/chat/{chat_id}/messages"
```

### AI Suite Chat
```bash
curl -X POST "/api/v1/aisuite/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "model": "anthropic:claude-3-sonnet",
    "temperature": 0.7
  }'
```

### Prompt Compilation
```bash
curl -X POST "/api/v1/prompt_compiler/compile" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Find good restaurants",
    "modelid": "gpt-4"
  }'
```