# Tidal Authentication API

API endpoints for managing Tidal OAuth authentication in the FastAPI server.

## Base URL
```
/api/v1/tidal
```

## Endpoints

### 1. Initialize Authentication
**POST** `/api/v1/tidal/init`

Starts a new Tidal OAuth authentication flow.

**Response:**
```json
{
  "auth_id": "uuid-string",
  "verification_uri": "https://link.tidal.com/XXXXX",
  "verification_uri_complete": "https://link.tidal.com/XXXXX",
  "user_code": "XXXXX",
  "device_code": "device-code-string",
  "expires_in": 300
}
```

**Usage:**
1. Call this endpoint
2. Display the `verification_uri_complete` to the user (or open it in a browser)
3. Show the `user_code` if needed
4. Poll the status endpoint with the `auth_id`

---

### 2. Check Authentication Status
**GET** `/api/v1/tidal/status/{auth_id}`

Check if the user has completed authentication.

**Response:**
```json
{
  "status": "pending|completed|error",
  "message": "Optional status message"
}
```

**Usage:**
- Poll this endpoint every 2-3 seconds until status is "completed" or "error"
- When completed, the session is automatically saved

---

### 3. Complete Authentication (Alternative)
**POST** `/api/v1/tidal/complete/{auth_id}`

Manually trigger completion check instead of polling status.

**Response:**
```json
{
  "status": "completed|pending",
  "message": "Status message"
}
```

---

### 4. Get Session Info
**GET** `/api/v1/tidal/session/info`

Get information about the current Tidal session.

**Response:**
```json
{
  "authenticated": true,
  "expiry_time": "2025-11-03T02:46:45.771452",
  "user_id": 12345678,
  "message": "Valid Tidal session"
}
```

---

### 5. Refresh Session
**POST** `/api/v1/tidal/session/refresh`

Refresh the current Tidal session using the refresh token.

**Response:**
```json
{
  "status": "success",
  "message": "Tidal session refreshed successfully",
  "expiry_time": "2025-11-03T03:46:45.771452"
}
```

---

### 6. Delete Session (Logout)
**DELETE** `/api/v1/tidal/session`

Delete the current Tidal session and backup to old_tidal_session.json.

**Response:**
```json
{
  "status": "success",
  "message": "Tidal session deleted. Backup saved to old_tidal_session.json"
}
```

---

## Frontend Integration Example

### JavaScript/TypeScript Example

```javascript
// Initialize authentication
async function initTidalAuth() {
  const response = await fetch('/api/v1/tidal/init', {
    method: 'POST'
  });
  const data = await response.json();
  
  // Open the verification URL in a new window
  window.open(data.verification_uri_complete, '_blank');
  
  // Show the code to the user
  console.log('Enter this code:', data.user_code);
  
  // Start polling for completion
  pollAuthStatus(data.auth_id);
}

// Poll for authentication completion
async function pollAuthStatus(authId) {
  const maxAttempts = 60; // 3 minutes with 3-second intervals
  let attempts = 0;
  
  const interval = setInterval(async () => {
    attempts++;
    
    const response = await fetch(`/api/v1/tidal/status/${authId}`);
    const data = await response.json();
    
    if (data.status === 'completed') {
      clearInterval(interval);
      console.log('Authentication successful!');
      // Proceed with your app logic
    } else if (data.status === 'error') {
      clearInterval(interval);
      console.error('Authentication failed:', data.message);
    } else if (attempts >= maxAttempts) {
      clearInterval(interval);
      console.error('Authentication timeout');
    }
  }, 3000); // Poll every 3 seconds
}

// Check current session status
async function checkTidalSession() {
  const response = await fetch('/api/v1/tidal/session/info');
  const data = await response.json();
  
  if (data.authenticated) {
    console.log('Already authenticated, expires:', data.expiry_time);
  } else {
    console.log('Not authenticated:', data.message);
    // Prompt user to authenticate
    initTidalAuth();
  }
}

// Refresh session
async function refreshTidalSession() {
  const response = await fetch('/api/v1/tidal/session/refresh', {
    method: 'POST'
  });
  const data = await response.json();
  console.log('Session refreshed:', data);
}
```

### React Component Example

```jsx
import { useState, useEffect } from 'react';

function TidalAuthButton() {
  const [authStatus, setAuthStatus] = useState(null);
  const [isPolling, setIsPolling] = useState(false);

  const initAuth = async () => {
    try {
      const response = await fetch('/api/v1/tidal/init', { method: 'POST' });
      const data = await response.json();
      
      // Open verification URL
      window.open(data.verification_uri_complete, '_blank');
      
      // Start polling
      setIsPolling(true);
      pollStatus(data.auth_id);
    } catch (error) {
      console.error('Failed to initialize auth:', error);
    }
  };

  const pollStatus = async (authId) => {
    const maxAttempts = 60;
    let attempts = 0;

    const interval = setInterval(async () => {
      attempts++;
      
      try {
        const response = await fetch(`/api/v1/tidal/status/${authId}`);
        const data = await response.json();
        
        if (data.status === 'completed') {
          clearInterval(interval);
          setIsPolling(false);
          setAuthStatus('authenticated');
        } else if (data.status === 'error' || attempts >= maxAttempts) {
          clearInterval(interval);
          setIsPolling(false);
          setAuthStatus('error');
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 3000);
  };

  const checkSession = async () => {
    try {
      const response = await fetch('/api/v1/tidal/session/info');
      const data = await response.json();
      setAuthStatus(data.authenticated ? 'authenticated' : 'unauthenticated');
    } catch (error) {
      console.error('Failed to check session:', error);
    }
  };

  useEffect(() => {
    checkSession();
  }, []);

  return (
    <div>
      {authStatus === 'authenticated' ? (
        <button onClick={checkSession}>✓ Tidal Connected</button>
      ) : (
        <button onClick={initAuth} disabled={isPolling}>
          {isPolling ? 'Waiting for auth...' : 'Connect Tidal'}
        </button>
      )}
    </div>
  );
}
```

---

## Testing with cURL

```bash
# 1. Initialize authentication
curl -X POST http://localhost:8000/api/v1/tidal/init

# 2. Check status (replace {auth_id} with actual ID from step 1)
curl http://localhost:8000/api/v1/tidal/status/{auth_id}

# 3. Check session info
curl http://localhost:8000/api/v1/tidal/session/info

# 4. Refresh session
curl -X POST http://localhost:8000/api/v1/tidal/session/refresh

# 5. Delete session
curl -X DELETE http://localhost:8000/api/v1/tidal/session
```

---

## Notes

- The authentication session expires after 10 minutes if not completed
- Sessions are stored in `secrets/tidal_session.json`
- Old sessions are backed up to `secrets/old_tidal_session.json` when deleted
- Access tokens typically expire in 24 hours but are auto-refreshed when using the session
- The refresh token is long-lived and used to get new access tokens
