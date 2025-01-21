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
    OPENAI_API_KEY: str
    OPENAI_REALTIME_ENDPOINT_URL: str

    MODELS_FILEPATH: str

    # Assistant Functions Integration Variable sets
    # Notion
    NOTION_API_KEY: str
    NOTION_RUNNING_LIST_DATABASE_ID: str
    NOTION_NOTES_PAGE_ID: str

    # Tidal
    TIDAL_USERNAME: str
    TIDAL_PASSWORD: str
    TIDAL_SECRETS_FILEPATH: str

    # Google Calendar
    GCAL_CREDENTIALS_PATH: str
    GCAL_TOKEN_PATH: str

    # SensorValues
    SENSOR_VALUES_HOST_CRITTENDEN: str
    SENSOR_VALUES_METRICS: str
    SENSOR_VALUES_CRITTENDEN_GROUP_ID: str

    # User Whitelist
    USER_WHITELIST: Optional[str]
    
    @property
    def CORS_ALLOWED_ORIGINS(self) -> list:
        return [self.FRONTEND_URL, self.BASE_URL]

dotenv_path = os.getenv('ENVPATH', 'env/.env.local')
print(dotenv_path)
load_dotenv(dotenv_path=dotenv_path)

settings = Settings()

