# Quick Start: Reverse Proxy Configuration

## TL;DR - What You Need to Set

### Environment Variables (Required)

```bash
# Core configuration for reverse proxy
BASE_PATH=/assistant
BASE_URL=https://sb-phl.xelaxer.com
FRONTEND_URL=https://sb-phl.xelaxer.com
COOKIE_PATH=/assistant
SYSTEM_MODE=prod

# Keep your existing database, auth, and API key configs
# (No changes needed to existing settings)
```

### Google OAuth Configuration

Add this redirect URI to your Google OAuth 2.0 Client:
```
https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback
```

### NGINX Configuration

```nginx
location /assistant/ {
    proxy_pass http://your-backend:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Prefix /assistant;
    
    # WebSocket support for Socket.IO
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## Code Changes Made

✅ **Fixed CORS** - Now uses configured origins instead of `*`  
✅ **Fixed cookies** - Now use `/assistant` path and `lax` SameSite  
✅ **Added COOKIE_PATH** - New config variable for cookie path scope

## Your Public URLs

| Service | URL |
|---------|-----|
| API Docs | `https://sb-phl.xelaxer.com/assistant/docs` |
| Health Check | `https://sb-phl.xelaxer.com/assistant/internal/health` |
| OAuth Login | `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/login` |
| Socket.IO | `https://sb-phl.xelaxer.com/assistant/socket.io` |

## Quick Test

```bash
# Health check
curl https://sb-phl.xelaxer.com/assistant/internal/health

# OpenAPI docs
curl https://sb-phl.xelaxer.com/assistant/docs
```

## Full Documentation

See [REVERSE_PROXY_CONFIGURATION.md](docs/REVERSE_PROXY_CONFIGURATION.md) for complete details, troubleshooting, and validation checklist.
