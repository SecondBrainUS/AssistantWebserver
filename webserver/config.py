from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    SYSTEMMODE: str
    DISCORD_TOKEN: str
    OPENAI_API_KEY: str
    OPENAI_REALTIME_ENDPOINT_URL: str
    NOTION_API_KEY: str
    NOTION_RUNNING_LIST_DATABASE_ID: str
    PICOVOICE_ACCESS_KEY: str
    NOTION_NOTES_PAGE_ID: str
    TIDAL_USERNAME: str
    TIDAL_PASSWORD: str
    TIDAL_SECRETS_FILEPATH: str
    GCAL_CREDENTIALS_PATH: str
    GCAL_TOKEN_PATH: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    ASSISTANTDB_URL: str
    BASE_URL: str
    FRONTEND_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    
dotenv_path = os.getenv('ENVPATH', 'env/.env.local')
print(dotenv_path)
load_dotenv(dotenv_path=dotenv_path)

settings = Settings()
