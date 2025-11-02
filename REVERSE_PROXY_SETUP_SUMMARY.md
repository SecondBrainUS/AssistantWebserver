# Reverse Proxy Setup Summary

## ✅ You Were Right!

Your current setup doesn't use double `/api` because:
- **BASE_PATH** should be `/assistant` (not `/assistant/api`)
- The `/api` part comes from your API router's prefix: `prefix="/api/v1"`
- Final public URLs: `https://sb-phl.xelaxer.com/assistant/api/v1/...`

## Configuration

### Environment Variables

```bash
BASE_PATH=/assistant               # ← Shared NGINX location prefix
BASE_URL=https://sb-phl.xelaxer.com
FRONTEND_URL=https://sb-phl.xelaxer.com
COOKIE_PATH=/assistant
SYSTEM_MODE=prod
```

### Public API URLs

| Endpoint | URL |
|----------|-----|
| OAuth Login | `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/login` |
| OAuth Callback | `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback` |
| User Profile | `https://sb-phl.xelaxer.com/assistant/api/v1/auth/me` |
| Socket.IO | `https://sb-phl.xelaxer.com/assistant/socket.io` |
| Health Check | `https://sb-phl.xelaxer.com/assistant/internal/health` |
| API Docs | `https://sb-phl.xelaxer.com/assistant/docs` |

### NGINX Configuration

```nginx
location /assistant/ {
    proxy_pass http://backend:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Prefix /assistant;
    
    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### Google OAuth Redirect URI

Add to Google Cloud Console:
```
https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback
```

## How Request Routing Works

```
Browser Request: https://sb-phl.xelaxer.com/assistant/api/v1/auth/me
                                            └───┬────┘ └────┬─────────┘
                                          NGINX strips  Backend receives
                                                        
NGINX strips:    /assistant
Backend gets:    /api/v1/auth/me
FastAPI matches: /api/v1/auth/me (from router prefix)
root_path adds:  /assistant (for URL generation in responses)
```

## Code Changes Made

1. **CORS**: Now uses `settings.CORS_ALLOWED_ORIGINS` instead of `["*"]`
2. **Cookies**: Use `path=settings.COOKIE_PATH` (`/assistant`) and `samesite="lax"`
3. **Config**: Added `COOKIE_PATH` setting for explicit cookie path control

## Quick Test

```bash
# Verify it's working
curl https://sb-phl.xelaxer.com/assistant/internal/health

# Check OpenAPI server URL
curl https://sb-phl.xelaxer.com/assistant/openapi.json | jq '.servers[0].url'
# Should return: "https://sb-phl.xelaxer.com/assistant"
```

## Full Documentation

See [docs/REVERSE_PROXY_CONFIGURATION.md](docs/REVERSE_PROXY_CONFIGURATION.md) for complete details.
