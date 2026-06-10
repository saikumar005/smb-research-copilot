import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Business Research Copilot"
    API_V1_STR: str = "/api/v1"
    
    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@db:5432/research_copilot_db",
        validation_alias="DATABASE_URL"
    )
    
    # Security Configurations
    JWT_SECRET: str = Field(
        default="super-secret-jwt-key-change-in-production",
        validation_alias="JWT_SECRET"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    
    # External API Keys
    OPENAI_API_KEY: str = Field(
        default="",
        validation_alias="OPENAI_API_KEY"
    )
    GEMINI_API_KEY: str = Field(
        default="",
        validation_alias="GEMINI_API_KEY"
    )
    SERPER_API_KEY: str = Field(
        default="",
        validation_alias="SERPER_API_KEY"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
