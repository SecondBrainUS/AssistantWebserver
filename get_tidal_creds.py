#!/usr/bin/env python3
"""
Quick throwaway script to get Tidal OAuth credentials in JSON format.
Run this once, authenticate in the browser, and it will save the credentials.
"""

import json
import tidalapi
import webbrowser

def get_tidal_credentials():
    """Perform OAuth login and save credentials to JSON."""
    print("=" * 60)
    print("TIDAL OAuth Credential Generator")
    print("=" * 60)
    
    session = tidalapi.Session()
    
    try:
        login, fut = session.login_oauth()
        
        print("\n🔐 Authentication Required")
        print("-" * 60)
        print(f"Verification URL: {login.verification_uri_complete}")
        print(f"\nOr visit: {login.verification_uri}")
        print(f"And enter code: {login.user_code}")
        print("-" * 60)
        
        # Try to open browser automatically
        try:
            webbrowser.open(login.verification_uri_complete)
            print("\n✓ Browser opened automatically")
        except Exception as e:
            print(f"\n⚠ Could not open browser automatically: {e}")
            print("Please open the URL manually.")
        
        print("\nWaiting for you to complete authentication...")
        fut.result()  # Block until user completes auth
        
        print("\n✓ Authentication successful!\n")
        
        # Extract credentials
        creds = {
            "token_type": session.token_type,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expiry_time": session.expiry_time.isoformat(),
        }
        
        # Save to file
        output_file = "tidal_oauth.json"
        with open(output_file, "w") as f:
            json.dump(creds, f, indent=2)
        
        print("=" * 60)
        print(f"✓ Credentials saved to: {output_file}")
        print("=" * 60)
        print("\nCredentials (for reference):")
        print("-" * 60)
        print(json.dumps(creds, indent=2))
        print("-" * 60)
        
        # Also print masked version for safety
        print("\nMasked version (safe to share):")
        print("-" * 60)
        masked = {
            "token_type": creds["token_type"],
            "access_token": creds["access_token"][:10] + "..." + creds["access_token"][-10:] if len(creds["access_token"]) > 20 else "***",
            "refresh_token": creds["refresh_token"][:10] + "..." + creds["refresh_token"][-10:] if len(creds["refresh_token"]) > 20 else "***",
            "expiry_time": creds["expiry_time"],
        }
        print(json.dumps(masked, indent=2))
        print("-" * 60)
        
        print("\n✓ You can now use these credentials in your app!")
        print(f"✓ Copy '{output_file}' to your secrets folder if needed.")
        
        return creds
        
    except Exception as e:
        print(f"\n❌ Error during authentication: {e}")
        raise

if __name__ == "__main__":
    try:
        get_tidal_credentials()
    except KeyboardInterrupt:
        print("\n\n⚠ Authentication cancelled by user.")
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        exit(1)
