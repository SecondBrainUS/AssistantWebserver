# Tidal Authentication API - Quick Start

## Overview
A complete FastAPI-based Tidal OAuth authentication system with browser-based re-authentication flow.

## Files Added/Modified

### New Files:
1. **`webserver/api/api_v1/endpoints/tidal_auth.py`** - Main authentication API endpoints
2. **`webserver/static/tidal_auth_test.html`** - Interactive test interface
3. **`docs/TIDAL_AUTH_API.md`** - Complete API documentation

### Modified Files:
1. **`webserver/api/api_v1/router.py`** - Added Tidal auth router
2. **`webserver/main.py`** - Added static files support
3. **`webserver/tools/tidal.py`** - Updated to use modern OAuth format

## Quick Start

### 1. Start your FastAPI server
```bash
cd AssistantWebserver
python -m webserver.main
# or
poetry run python -m webserver.main
```

### 2. Access the test interface
Open in browser: **http://localhost:8000/static/tidal_auth_test.html**

### 3. Authenticate
1. Click "Start Authentication"
2. A browser window opens with Tidal login
3. Log in to Tidal
4. The page will automatically detect when authentication is complete
5. Session is saved to `secrets/tidal_session.json`

## API Endpoints

All endpoints are under `/api/v1/tidal`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/init` | Start authentication flow |
| GET | `/status/{auth_id}` | Check auth status (poll this) |
| POST | `/complete/{auth_id}` | Manual completion trigger |
| GET | `/session/info` | Get current session info |
| POST | `/session/refresh` | Refresh session tokens |
| DELETE | `/session` | Delete/logout session |

## Using the API

### cURL Examples

```bash
# Check if already authenticated
curl http://localhost:8000/api/v1/tidal/session/info

# Start authentication
curl -X POST http://localhost:8000/api/v1/tidal/init

# Check status (replace AUTH_ID)
curl http://localhost:8000/api/v1/tidal/status/AUTH_ID

# Refresh session
curl -X POST http://localhost:8000/api/v1/tidal/session/refresh
```

### JavaScript Example

```javascript
// Initialize authentication
const response = await fetch('/api/v1/tidal/init', { method: 'POST' });
const { auth_id, verification_uri_complete, user_code } = await response.json();

// Open browser
window.open(verification_uri_complete, '_blank');

// Poll for completion
const pollInterval = setInterval(async () => {
  const statusRes = await fetch(`/api/v1/tidal/status/${auth_id}`);
  const { status } = await statusRes.json();
  
  if (status === 'completed') {
    clearInterval(pollInterval);
    console.log('Authenticated!');
  }
}, 3000);
```

## Integration with Existing Code

The `webserver/tools/tidal.py` has been updated to use the new OAuth format. The `get_session()` function now:
- Loads credentials from `secrets/tidal_session.json`
- Auto-refreshes tokens when needed
- Falls back to browser authentication if session is invalid

No changes needed to your existing tool functions like:
- `create_playlist()`
- `get_playlist_by_name()`
- `add_song_to_playlist()`
- etc.

They all use `get_session()` internally and will work automatically.

## Session File Format

The new format (in `secrets/tidal_session.json`):
```json
{
  "token_type": "Bearer",
  "access_token": "...",
  "refresh_token": "...",
  "expiry_time": "2025-11-03T02:46:45.771452"
}
```

## Testing

### Test with the Web Interface
1. Go to http://localhost:8000/static/tidal_auth_test.html
2. Click buttons to test each endpoint
3. Watch the status messages

### Test with FastAPI Docs
1. Go to http://localhost:8000/docs
2. Find the "Tidal" section
3. Try each endpoint interactively

### Test from Your Frontend
Use the JavaScript examples in `docs/TIDAL_AUTH_API.md`

## Troubleshooting

### "Session not found" error
- The auth session expired (10 min timeout)
- Start a new authentication with `/init`

### "Authentication failed" error
- User didn't complete login in Tidal
- Tidal service is down
- Try again with a fresh `/init` call

### Tokens expired
- Call `/session/refresh` to get new tokens
- If refresh fails, start new authentication

### Can't access test page
- Make sure `webserver/static/` directory exists
- Restart the FastAPI server
- Check server logs for errors

## Security Notes

- Session files contain sensitive tokens - keep `secrets/` folder secure
- In production, consider:
  - Encrypting the session file
  - Using environment variables
  - Implementing user-specific sessions
  - Adding authentication to these endpoints

## Next Steps

1. **Add to your frontend**: Integrate the auth flow into your React/Vue app
2. **Add user association**: Link Tidal sessions to your user accounts
3. **Add error handling**: Show user-friendly error messages
4. **Add analytics**: Track authentication success/failure rates
5. **Add notifications**: Alert users when session is about to expire

## Support

For detailed API documentation, see: `docs/TIDAL_AUTH_API.md`

For frontend integration examples, check the JavaScript/React examples in the docs.
