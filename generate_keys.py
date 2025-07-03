#!/usr/bin/env python3
"""
Generate RSA key pair for server-to-server authentication
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import os

def generate_rsa_keypair():
    """Generate RSA private and public key pair"""
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_pem.decode('utf-8'), public_pem.decode('utf-8')

if __name__ == "__main__":
    print("Generating RSA key pair for server-to-server authentication...")
    
    private_key, public_key = generate_rsa_keypair()
    
    # Create secrets directory if it doesn't exist
    os.makedirs('secrets', exist_ok=True)
    
    # Save to files in secrets directory
    private_key_path = 'secrets/server_private_key.pem'
    public_key_path = 'secrets/server_public_key.pem'
    
    with open(private_key_path, 'w') as f:
        f.write(private_key)
    
    with open(public_key_path, 'w') as f:
        f.write(public_key)
    
    print("✓ Keys generated successfully!")
    print(f"✓ Private key saved to: {private_key_path}")
    print(f"✓ Public key saved to: {public_key_path}")
    print()
    print("Configuration Options:")
    print()
    print("📁 OPTION 1 - File Path (Recommended):")
    print(f'   Add to .env: SERVER_AUTH_PUBLIC_KEY_PATH="{public_key_path}"')
    print('   Add to .env: ALLOWED_SERVER_CLIENTS="discord_bot,other_client"')
    print()
    print("📝 OPTION 2 - Direct Content:")
    print("   Add to .env: SERVER_AUTH_PUBLIC_KEY=\"" + public_key.replace('\n', '\\n') + "\"")
    print('   Add to .env: ALLOWED_SERVER_CLIENTS="discord_bot,other_client"')
    print()
    print("🚀 For Discord Bot:")
    print(f"   Use private key file: {private_key_path}")
    print()
    print("⚠️  Keep the private key secure and never commit it to version control!") 