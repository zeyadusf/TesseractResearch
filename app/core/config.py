from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict,Optional,Set
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME:str
    APP_VERSION:str

    DEBUG:bool = False

    POSTGRES_USERNAME:str
    POSTGRES_PASSWORD:str
    POSTGRES_DB:str
    POSTGRES_PORT:int
    POSTGRES_HOST:str
    DATABASE_URL:str
# POSTGRES_HOST = "localhost" #Local
# POSTGRES_HOST = "db.xxxx.supabase.co" #Production
    
    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_setting()->Settings:
    return Settings()