#!/usr/bin/env python3
"""
Example client for server-to-server authentication with the Assistant API
Use this as reference for your Discord bot implementation
"""

import jwt
import requests
import datetime
from typing import Optional

class AssistantServerClient:
    def __init__(self, private_key_path: str, client_id: str, base_url: str):
        """
        Initialize the client with RSA private key for JWT signing
        
        Args:
            private_key_path: Path to the RSA private key file
            client_id: Your client identifier (e.g., "discord_bot")
            base_url: Base URL of the Assistant API
        """
        self.client_id = client_id
        self.base_url = base_url.rstrip('/')
        
        # Load private key
        try:
            with open(private_key_path, 'r') as f:
                self.private_key = f.read()
        except FileNotFoundError:
            raise ValueError(f"Private key file not found: {private_key_path}")
        except Exception as e:
            raise ValueError(f"Error loading private key: {str(e)}")
        
        # Token management
        self._cached_token = None
        self._token_expires_at = None
    
    def _is_token_expired(self) -> bool:
        """Check if current token is expired or will expire soon (30s buffer)"""
        if not self._token_expires_at:
            return True
        
        buffer_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
        return self._token_expires_at <= buffer_time
    
    def _create_new_token(self, expire_minutes: int = 15) -> str:
        """Create a new signed JWT token and cache it"""
        now = datetime.datetime.utcnow()
        expires_at = now + datetime.timedelta(minutes=expire_minutes)
        
        payload = {
            "client_id": self.client_id,
            "token_type": "server",
            "exp": expires_at,
            "iat": now
        }
        
        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        
        # Cache the token and expiry
        self._cached_token = token
        self._token_expires_at = expires_at
        
        print(f"[AUTH] Generated new token, expires at {expires_at}")
        return token
    
    def get_valid_token(self) -> str:
        """Get a valid token, creating new one if needed"""
        if self._is_token_expired():
            print("[AUTH] Token expired or missing, generating new one...")
            return self._create_new_token()
        
        print("[AUTH] Using cached token")
        return self._cached_token
    
    def test_auth(self) -> dict:
        """Test server authentication with a simple GET request"""
        try:
            token = self.get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            url = f"{self.base_url}/assistant/api/v1/run/server/test"
            response = requests.get(url, headers=headers)
            
            print(f"[TEST] Status: {response.status_code}")
            if response.status_code != 200:
                print(f"[TEST] Error response: {response.text}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"[TEST] Request failed: {e}")
            return {"error": str(e)}
    
    def call_assistant(self, text: Optional[str] = None, audio_file: Optional[str] = None, max_retries: int = 2) -> dict:
        """
        Call the assistant API with automatic token management
        
        Args:
            text: Text prompt to send
            audio_file: Path to audio file to upload
            max_retries: Max retries on auth failure
            
        Returns:
            API response as dictionary
        """
        
        for attempt in range(max_retries + 1):
            try:
                token = self.get_valid_token()
                headers = {
                    "Authorization": f"Bearer {token}"
                }
                
                # Prepare the request
                data = {}
                files = {}
                
                if text:
                    data["text"] = text
                
                if audio_file:
                    files["audio"] = open(audio_file, 'rb')
                
                url = f"{self.base_url}/assistant/api/v1/run/server"
                response = requests.post(url, data=data, files=files, headers=headers)
                
                # If auth failed, clear token cache and retry
                if response.status_code == 401 and attempt < max_retries:
                    print(f"[AUTH] Token rejected (attempt {attempt + 1}), clearing cache and retrying...")
                    self._cached_token = None
                    self._token_expires_at = None
                    continue
                
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    print(f"Error calling API after {max_retries + 1} attempts: {e}")
                    return {"error": str(e)}
                print(f"Request failed (attempt {attempt + 1}), retrying...")
            
            finally:
                # Close any opened files
                for file in files.values():
                    if hasattr(file, 'close'):
                        file.close()
        
        return {"error": "Max retries exceeded"}

# Example usage showing token management
if __name__ == "__main__":
    client = AssistantServerClient(
        private_key_path="secrets/server_private_key.pem",
        client_id="discord_bot",
        base_url="http://localhost:8900"
    )
    
    # Test authentication first
    print("=== Testing Authentication ===")
    test_result = client.test_auth()
    print("Auth Test Result:", test_result)
    
    if test_result.get("status") == "success":
        print("✓ Authentication working!")
        
        # First call - creates new token
        print("\n=== First call ===")
        response1 = client.call_assistant(text="Hello 1")
        print("Response:", response1.get("text", "No text"))
        
        # Second call - uses cached token
        print("\n=== Second call (should use cached token) ===")
        response2 = client.call_assistant(text="Hello 2") 
        print("Response:", response2.get("text", "No text"))
        
        # Simulate token expiry by clearing cache
        print("\n=== Simulating expired token ===")
        client._cached_token = None
        response3 = client.call_assistant(text="Hello 3")
        print("Response:", response3.get("text", "No text"))
    else:
        print("❌ Authentication failed!")
        print("Check your configuration and server logs for details.") 