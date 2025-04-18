from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # System Variables
    SYSTEM_MODE: str
    PORT: int

    # AssistantDB
    ASSISTANTDB_URL: str

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
    
    @property
    def CORS_ALLOWED_ORIGINS(self) -> list:
        return [self.FRONTEND_URL, self.BASE_URL]

dotenv_path = os.getenv('ENVPATH', 'env/.env.local')
print(dotenv_path)
load_dotenv(dotenv_path=dotenv_path)

settings = Settings()

