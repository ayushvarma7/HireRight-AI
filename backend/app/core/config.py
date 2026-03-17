"""
Application Configuration

Load settings from environment variables using Pydantic Settings.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "HireRight API"
    debug: bool = False
    log_level: str = "INFO"
    
    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    
    # CORS
    cors_origins: List[str] = ["http://localhost:8501", "http://localhost:3000"]
    
    # Google Gemini
    google_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_embedding_model: str = "models/embedding-001"
    embedding_dimension: int = 768
    
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    
    # GitHub
    github_token: str = ""
    
    # Tavily
    tavily_api_key: str = ""
    
    # Database (Legacy/External)
    database_url: str = ""
    
    # MCP Servers
    mcp_github_server_url: str = "http://localhost:8001"
    mcp_jobmarket_server_url: str = "http://localhost:8002"
    
    # Agent Configuration
    max_debate_rounds: int = 3
    redebate_threshold: float = 0.30  # Redebate if score difference > 30%


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
