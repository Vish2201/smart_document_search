from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI Configuration
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4-turbo-preview"
    
    # Typesense Configuration
    typesense_host: str = "localhost"
    typesense_port: int = 8108
    typesense_protocol: str = "http"
    typesense_api_key: str = "xyz"
    
    # Database Configuration
    database_url: str = "sqlite:///./smart_qa.db"
    
    # Application Settings
    max_context_tokens: int = 4000
    max_search_results: int = 10
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # Memory Settings
    max_conversation_history: int = 20
    context_compression_threshold: int = 3000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
