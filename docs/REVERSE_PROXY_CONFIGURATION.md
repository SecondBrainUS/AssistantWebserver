# Reverse Proxy Configuration Guide

## Overview

This backend is configured to run behind NGINX at:
- **Public Base URL**: `https://sb-phl.xelaxer.com`
- **Base Path**: `/assistant` (shared prefix for frontend and API)
- **API Routes**: `/assistant/api/v1/...` (BASE_PATH + router prefix)
- **Frontend**: `/assistant` (separate app, same NGINX location)

## Environment Configuration

### Required Environment Variables

Create or update your environment file (e.g., `env/.env.prod`) with these values:

```bash
# ============================================================================
# REVERSE PROXY CONFIGURATION
# ============================================================================

# System Mode - CRITICAL: Set to 'prod' for production deployment
SYSTEM_MODE=prod

# Base Path - The root path where the application is mounted behind the reverse proxy
# This is the shared prefix for both frontend and backend under NGINX
# The /api part comes from the API router prefix, not from BASE_PATH
BASE_PATH=/assistant

# Base URL - The public external URL where the API is accessible
# Used for constructing OAuth redirect URIs and absolute URLs
BASE_URL=https://sb-phl.xelaxer.com

# Frontend URL - The public external URL where the frontend is accessible
# Must be same origin for CORS to work correctly
FRONTEND_URL=https://sb-phl.xelaxer.com

# Cookie Path - The path scope for authentication cookies
# Should match BASE_PATH to allow cookies to be shared between frontend and API
COOKIE_PATH=/assistant

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

PORT=8000

# ============================================================================
# DATABASE CONNECTIONS
# ============================================================================

ASSISTANTDB_URL=postgresql://user:password@host:5432/dbname
ASSISTANTDB_AUTH_SCHEMA=public
ASSISTANTDB_INTEGRATIONS_SCHEMA=public

MONGODB_URI=mongodb://host:27017
MONGODB_DB_NAME=assistant

MEMCACHE_HOST=memcache-host
MEMCACHE_PORT=11211

# ============================================================================
# AUTHENTICATION
# ============================================================================

JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ALGORITHM=HS256
JWT_REFRESH_SECRET_KEY=your-refresh-secret-key-here

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Token Expiration Settings
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7
SESSION_ID_EXPIRE_MINUTES=10080

# Server-to-Server Authentication (optional)
SERVER_AUTH_PUBLIC_KEY_PATH=/path/to/public.pem
SERVER_AUTH_ALGORITHM=RS256
SERVER_AUTH_TOKEN_EXPIRE_MINUTES=15
ALLOWED_SERVER_CLIENTS=discord_bot

# ============================================================================
# S3 STORAGE
# ============================================================================

S3_ENDPOINT=s3.amazonaws.com
S3_ACCESS_KEY=your-s3-access-key
S3_SECRET_KEY=your-s3-secret-key

# ============================================================================
# AI MODEL API KEYS
# ============================================================================

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
PERPLEXITY_API_KEY=pplx-...
GROQ_API_KEY=gsk_...
XAI_API_KEY=xai-...

# AWS Bedrock (optional)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1

# ============================================================================
# INTEGRATION API KEYS (Optional - only if using these features)
# ============================================================================

# Notion
NOTION_API_KEY=secret_...
NOTION_RUNNING_LIST_DATABASE_ID=...
NOTION_NOTES_PAGE_ID=...

# Spotify
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=https://sb-phl.xelaxer.com/assistant/api/v1/spotify/callback
SPOTIFY_SCOPES=user-read-playback-state,user-modify-playback-state

# Tidal
TIDAL_USERNAME=...
TIDAL_PASSWORD=...
TIDAL_SECRETS_FILEPATH=/secrets/tidal.json

# Google Calendar
GCAL_CREDENTIALS_PATH=/secrets/google_credentials.json
GCAL_TOKEN_PATH=/secrets/google_token.json

# Sensor Values (IoT)
SENSOR_VALUES_HOST_CRITTENDEN=http://...
SENSOR_VALUES_METRICS=temperature,humidity
SENSOR_VALUES_CRITTENDEN_GROUP_ID=...

# BrightData Search
BRIGHT_DATA_UNLOCKER_API_KEY=...
BRIGHT_DATA_UNLOCKER_ZONE=...
BRIGHT_DATA_SERP_API_KEY=...
BRIGHT_DATA_SERP_ZONE=...

# User Access Control
USER_WHITELIST=user1@example.com,user2@example.com
```

## How It Works

### FastAPI Root Path

The application uses FastAPI's `root_path` parameter (set in `webserver/main.py`):

```python
app = FastAPI(root_path=f"{settings.BASE_PATH}")
```

This automatically:
- ✅ Adds the base path prefix to all routes in OpenAPI docs
- ✅ Generates correct URLs in responses and redirects
- ✅ Respects `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Forwarded-Prefix` headers
- ✅ Updates OpenAPI JSON with correct server URLs

### Route Structure

With `BASE_PATH=/assistant`, your routes will be:

| Route Type | Application Route | Full Public URL |
|------------|-------------------|------------------|
| OAuth Login | `/api/v1/auth/google/login` | `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/login` |
| OAuth Callback | `/api/v1/auth/google/callback` | `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback` |
| User Profile | `/api/v1/auth/me` | `https://sb-phl.xelaxer.com/assistant/api/v1/auth/me` |
| Socket.IO | `/socket.io` | `https://sb-phl.xelaxer.com/assistant/socket.io` |
| Health Check | `/internal/health` | `https://sb-phl.xelaxer.com/assistant/internal/health` |
| Metrics | `/internal/metrics` | `https://sb-phl.xelaxer.com/assistant/internal/metrics` |
| OpenAPI Docs | `/docs` | `https://sb-phl.xelaxer.com/assistant/docs` |
| OpenAPI JSON | `/openapi.json` | `https://sb-phl.xelaxer.com/assistant/openapi.json` |

**Note**: The `/api` in `/api/v1/...` comes from the API router's `prefix="/api/v1"` setting, not from `BASE_PATH`.

### OAuth Redirect Flow

The auth endpoint automatically constructs callback URLs using:

```python
redirect_uri = f"{settings.BASE_URL}{settings.BASE_PATH}/api/v1/auth/{provider}/callback"
```

For Google OAuth:
- **Redirect URI**: `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback`

⚠️ **Important**: Add this exact URL to your Google OAuth 2.0 Client configuration:
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Edit your OAuth 2.0 Client ID
3. Add to "Authorized redirect URIs": `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback`

### Cookie Configuration

Cookies are now configured to work across frontend and backend:

- **Path**: `/assistant` (shared prefix for frontend and API routes)
- **Secure**: `true` in production (HTTPS only)
- **HttpOnly**: `true` (prevents JavaScript access)
- **SameSite**: `lax` (allows cookies across sub-paths)
- **Domain**: `None` (browser auto-determines from request)

This allows:
✅ Frontend at `/assistant` to receive auth cookies  
✅ Backend API routes at `/assistant/api/v1/...` to validate auth cookies  
✅ Secure transmission over HTTPS  
✅ Protection against XSS attacks (httpOnly)

### CORS Configuration

CORS is automatically configured using:

```python
settings.CORS_ALLOWED_ORIGINS = [settings.FRONTEND_URL, settings.BASE_URL]
```

Which resolves to: `["https://sb-phl.xelaxer.com", "https://sb-phl.xelaxer.com"]`

This allows:
✅ Frontend to make API requests  
✅ Credentials (cookies) to be included in requests  
✅ Secure same-origin policy enforcement

## NGINX Configuration

Your NGINX reverse proxy should be configured with:

```nginx
location /assistant/ {
    proxy_pass http://backend-service:8000/;
    
    # Proxy headers - REQUIRED
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Prefix /assistant;
    
    # WebSocket support for Socket.IO
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    
    # Timeouts for long-lived connections
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

**Critical Notes**:
- The trailing slash in `proxy_pass http://backend-service:8000/` is **required**
- This strips `/assistant` from the request before passing to the backend
- The backend receives clean paths (e.g., `/api/v1/auth/me`, `/socket.io`, etc.)
- FastAPI's `root_path` adds the `/assistant` prefix back for URL generation
- Both frontend static files and backend API are served from the same location block

## Code Changes Applied

### 1. Fixed CORS Configuration (`webserver/main.py`)

**Before**:
```python
allow_origins=["*"],  # ❌ Wide open
```

**After**:
```python
allow_origins=settings.CORS_ALLOWED_ORIGINS,  # ✅ Restricted to configured origins
```

### 2. Fixed Cookie Configuration (`webserver/api/api_v1/endpoints/auth.py`)

**Before**:
```python
path="/",                                               # ❌ Too broad
samesite="lax" if settings.SYSTEM_MODE == "dev" else "strict",  # ❌ Strict breaks sub-paths
```

**After**:
```python
path=settings.COOKIE_PATH,  # ✅ /assistant (shared prefix)
samesite="lax",              # ✅ Works with sub-path routing
```

### 3. Added COOKIE_PATH Setting (`webserver/config.py`)

```python
COOKIE_PATH: str = "/assistant"  # Cookie path shared with frontend
```

## Validation Checklist

Use this checklist to validate your deployment:

### Pre-Deployment Checks

- [ ] `BASE_PATH=/assistant` in environment config
- [ ] `BASE_URL=https://sb-phl.xelaxer.com` in environment config
- [ ] `FRONTEND_URL=https://sb-phl.xelaxer.com` in environment config
- [ ] `COOKIE_PATH=/assistant` in environment config
- [ ] `SYSTEM_MODE=prod` in environment config
- [ ] Google OAuth redirect URI includes: `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback`
- [ ] NGINX proxy headers configured (especially `X-Forwarded-Proto` and `X-Forwarded-Host`)
- [ ] NGINX WebSocket support enabled for Socket.IO

### Post-Deployment Validation

#### 1. OpenAPI Documentation
```bash
curl https://sb-phl.xelaxer.com/assistant/openapi.json | jq '.servers'
```
**Expected**: Should show `https://sb-phl.xelaxer.com/assistant`

#### 2. Health Check
```bash
curl https://sb-phl.xelaxer.com/assistant/internal/health
```
**Expected**: `{"status": "healthy"}` or similar

#### 3. OAuth Flow
- [ ] Visit: `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/login`
- [ ] Redirects to Google OAuth consent screen
- [ ] After consent, redirects back to: `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback`
- [ ] Then redirects to: `https://sb-phl.xelaxer.com/assistant/login-success?temp_token=...`
- [ ] Cookies are set with correct attributes in browser DevTools

#### 4. Cookie Attributes (Chrome DevTools → Application → Cookies)
- [ ] Domain: `sb-phl.xelaxer.com` (or `.sb-phl.xelaxer.com`)
- [ ] Path: `/assistant`
- [ ] Secure: ✓ (checked)
- [ ] HttpOnly: ✓ (checked)
- [ ] SameSite: `Lax`

#### 5. CORS Preflight
```bash
curl -X OPTIONS https://sb-phl.xelaxer.com/assistant/api/v1/auth/me \
  -H "Origin: https://sb-phl.xelaxer.com" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v
```
**Expected**: `Access-Control-Allow-Origin: https://sb-phl.xelaxer.com`

#### 6. Socket.IO Connection
From browser console (on frontend at `/assistant`):
```javascript
const socket = io('https://sb-phl.xelaxer.com/assistant');
socket.on('connect', () => console.log('Connected!'));
```
**Expected**: Socket connects successfully

#### 7. Authenticated Request
```bash
# First login and copy cookies, then:
curl https://sb-phl.xelaxer.com/assistant/api/v1/auth/me \
  -H "Cookie: access_token=...; session_id=..." \
  -v
```
**Expected**: Returns user profile JSON

## Troubleshooting

### Issue: 404 Not Found on all routes

**Cause**: NGINX `proxy_pass` directive incorrect  
**Fix**: Ensure trailing slash in `proxy_pass http://backend:8000/`

### Issue: OAuth callback fails with "Invalid redirect URI"

**Cause**: Google OAuth client not configured with correct callback URL  
**Fix**: Add exact URL to Google Cloud Console: `https://sb-phl.xelaxer.com/assistant/api/v1/auth/google/callback`

### Issue: Cookies not being sent from frontend to API

**Causes**:
1. Cookie `path` doesn't match the shared prefix (must be `/assistant`)
2. `SameSite=Strict` blocking cross-path requests
3. Frontend and API on different domains

**Fix**: 
- Verify `COOKIE_PATH=/assistant` matches `BASE_PATH=/assistant`
- Ensure `samesite=lax` (already configured)
- Verify frontend and API are same origin

### Issue: CORS errors in browser console

**Cause**: CORS not configured correctly  
**Fix**: Verify `FRONTEND_URL=https://sb-phl.xelaxer.com` matches the origin

### Issue: Socket.IO fails to connect

**Causes**:
1. WebSocket headers not proxied correctly
2. Timeout too short for long-lived connections
3. Incorrect Socket.IO path

**Fix**:
- Add WebSocket headers to NGINX config (see example above)
- Increase proxy timeouts
- Verify Socket.IO connects to: `https://sb-phl.xelaxer.com/assistant/socket.io`

### Issue: OpenAPI docs show `localhost` URLs

**Cause**: `BASE_PATH` or `BASE_URL` not set correctly  
**Fix**: Verify environment variables are loaded and app is restarted

### Issue: "insecure" cookies over HTTPS

**Cause**: `SYSTEM_MODE` not set to `prod`  
**Fix**: Set `SYSTEM_MODE=prod` in environment config

## Security Considerations

### Production Checklist

- [x] ✅ CORS restricted to specific origins (not `*`)
- [x] ✅ Cookies use `Secure` flag in production
- [x] ✅ Cookies use `HttpOnly` flag (prevents XSS)
- [x] ✅ Cookies use `SameSite=lax` (CSRF protection)
- [ ] ⚠️ Consider adding `HSTS` header in NGINX
- [ ] ⚠️ Consider adding rate limiting in NGINX
- [ ] ⚠️ Consider adding Web Application Firewall (WAF)

### Recommended NGINX Security Headers

Add to your NGINX config:

```nginx
# Security headers
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
```

## Summary

Your backend is **fully configured** for reverse proxy deployment with:

✅ **Environment-driven configuration** via `BASE_PATH`, `BASE_URL`, `FRONTEND_URL`, `COOKIE_PATH`  
✅ **FastAPI `root_path` support** for automatic URL generation  
✅ **Proxy header awareness** via Starlette's built-in support  
✅ **OAuth redirect URLs** dynamically constructed from settings  
✅ **Cookie sharing** between frontend and API via correct path scope  
✅ **CORS configuration** restricted to configured origins  
✅ **Socket.IO path** automatically prefixed with `BASE_PATH`

**No additional code changes required** - just set the environment variables and deploy!
