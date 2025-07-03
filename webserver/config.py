from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import Optional, List
import os
import json
import boto3

class Settings(BaseSettings):
    # System Variables
    SYSTEM_MODE: str
    PORT: int

    # NEW
    BASE_PATH: str = "/assistant"

    # AssistantDB
    ASSISTANTDB_URL: str
        
    # Database Schema Configuration
    ASSISTANTDB_AUTH_SCHEMA: str = "public"
    ASSISTANTDB_INTEGRATIONS_SCHEMA: str = "public"

    # ChatDB
    MONGODB_URI: str
    MONGODB_DB_NAME: str

    # Memcache
    MEMCACHE_HOST: str
    MEMCACHE_PORT: int

    # S3
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str

    # Authentication
    BASE_URL: str
    FRONTEND_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    JWT_REFRESH_SECRET_KEY: str
    SESSION_ID_EXPIRE_MINUTES: int

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_REALTIME_ENDPOINT_URL: Optional[str] = None

    # AWS
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None

    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None

    # Perplexity
    PERPLEXITY_API_KEY: Optional[str] = None

    # Groq
    GROQ_API_KEY: Optional[str] = None

    # XAI
    XAI_API_KEY: Optional[str] = None

    MODELS_FILEPATH: Optional[str] = None

    # Assistant Functions Integration Variable
    AWS_SSM_SPOTIFY_CACHE_PARAM: Optional[str] = None
    AWS_REGION: Optional[str] = None

    # Notion
    NOTION_API_KEY: Optional[str] = None
    NOTION_RUNNING_LIST_DATABASE_ID: Optional[str] = None
    NOTION_NOTES_PAGE_ID: Optional[str] = None

    # Tidal
    TIDAL_USERNAME: Optional[str] = None
    TIDAL_PASSWORD: Optional[str] = None
    TIDAL_SECRETS_FILEPATH: Optional[str] = None

    # Google Calendar
    GCAL_CREDENTIALS_PATH: Optional[str] = None
    GCAL_TOKEN_PATH: Optional[str] = None

    # SensorValues
    SENSOR_VALUES_HOST_CRITTENDEN: Optional[str] = None
    SENSOR_VALUES_METRICS: Optional[str] = None
    SENSOR_VALUES_CRITTENDEN_GROUP_ID: Optional[str] = None

    # Spotify
    SPOTIFY_CLIENT_ID: Optional[str] = None
    SPOTIFY_CLIENT_SECRET: Optional[str] = None
    SPOTIFY_REDIRECT_URI: Optional[str] = None
    SPOTIFY_SCOPES: Optional[str] = None

    # BrightData
    BRIGHT_DATA_UNLOCKER_API_KEY: Optional[str]
    BRIGHT_DATA_UNLOCKER_ZONE: Optional[str]
    BRIGHT_DATA_SERP_API_KEY: Optional[str]
    BRIGHT_DATA_SERP_ZONE: Optional[str] = None

    # User Whitelist
    USER_WHITELIST: Optional[str] = None
    
    # Add these settings for server-to-server authentication
    SERVER_AUTH_PUBLIC_KEY: str = ""
    SERVER_AUTH_PUBLIC_KEY_PATH: str = ""  # Alternative: path to key file
    SERVER_AUTH_ALGORITHM: str = "RS256"
    SERVER_AUTH_TOKEN_EXPIRE_MINUTES: int = 15
    ALLOWED_SERVER_CLIENTS: str = "discord_bot"  # Comma-separated list

    @property
    def CORS_ALLOWED_ORIGINS(self) -> list:
        return [self.FRONTEND_URL, self.BASE_URL]

    @property
    def get_server_public_key(self) -> str:
        """Get the server public key from either direct content or file path"""
        if self.SERVER_AUTH_PUBLIC_KEY:
            return self.SERVER_AUTH_PUBLIC_KEY
        elif self.SERVER_AUTH_PUBLIC_KEY_PATH:
            try:
                with open(self.SERVER_AUTH_PUBLIC_KEY_PATH, 'r') as f:
                    return f.read()
            except FileNotFoundError:
                raise ValueError(f"Public key file not found: {self.SERVER_AUTH_PUBLIC_KEY_PATH}")
        else:
            raise ValueError("No server public key configured (set SERVER_AUTH_PUBLIC_KEY or SERVER_AUTH_PUBLIC_KEY_PATH)")

    @property  
    def get_allowed_server_clients(self) -> List[str]:
        """Parse comma-separated list of allowed server clients"""
        if not self.ALLOWED_SERVER_CLIENTS:
            return []
        return [client.strip() for client in self.ALLOWED_SERVER_CLIENTS.split(",")]

dotenv_path = os.getenv('ENVPATH', 'env/.env.local')
print(dotenv_path)
load_dotenv(dotenv_path=dotenv_path)

secret_blob = os.getenv("SECONDBRAIN_SECRET_BLOB")
if secret_blob and secret_blob.startswith("{"):
    try:
        secrets = json.loads(secret_blob)

        # Inject into environment so Pydantic can use it
        for key, value in secrets.items():
            if key not in os.environ:
                os.environ[key] = str(value)

        print(f"[config] Loaded {len(secrets)} secrets from ECS-injected blob")

    except Exception as e:
        print(f"[config] Failed to parse injected secrets: {e}")
else:
    print("[config] No secret JSON blob found in SECONDBRAIN_SECRET_BLOB")

# # Inject values from AWS Secrets Manager (if running in ECS)
# secret_arn = os.getenv("SECONDBRAIN_SECRET_BLOB")
# aws_region = os.getenv("AWS_REGION", "us-east-1")

# if secret_arn:
#     try:
#         client = boto3.client("secretsmanager", region_name=aws_region)
#         response = client.get_secret_value(SecretId=secret_arn)
#         secrets = json.loads(response["SecretString"])

#         # Inject each key into the environment so Pydantic can use it
#         for key, value in secrets.items():
#             if key not in os.environ:
#                 os.environ[key] = str(value)  # convert non-string values

#         print(f"[config] Loaded secrets from Secrets Manager: {secret_arn}")

#     except Exception as e:
#         print(f"[config] Failed to load secrets from {secret_arn}: {e}")

settings = Settings()

