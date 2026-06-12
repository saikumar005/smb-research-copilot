import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices

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
        default=1440,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    
    # External API Keys
    MEMORI_API_KEY: str = Field(
        default="",
        validation_alias="MEMORI_API_KEY"
    )
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
    COMPOSIO_API_KEY: str = Field(
        default="",
        validation_alias="COMPOSIO_API_KEY"
    )
    # Google OAuth 2.0 — used to verify id_tokens from the GIS popup flow
    GOOGLE_CLIENT_ID: str = Field(
        default="",
        validation_alias="GOOGLE_CLIENT_ID"
    )
    # Frontend origin — used for CORS and Trusted-Origin checks
    FRONTEND_ORIGIN: str = Field(
        default="http://localhost:5173",
        validation_alias="FRONTEND_ORIGIN"
    )
    
    # Langfuse Telemetry Configurations
    LANGFUSE_PUBLIC_KEY: str = Field(
        default="",
        validation_alias="LANGFUSE_PUBLIC_KEY"
    )
    LANGFUSE_SECRET_KEY: str = Field(
        default="",
        validation_alias="LANGFUSE_SECRET_KEY"
    )
    LANGFUSE_HOST: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL")
    )
    
    # Toggle JSON Structured Logging (e.g. True in production)
    LOG_JSON: bool = Field(
        default=False,
        validation_alias="LOG_JSON"
    )


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
