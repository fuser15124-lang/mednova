from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "MedNova AI"
    database_url: str = "sqlite:///./mednova.db"
    jwt_secret: str = "dev-only-change-me-change-this-secret-please"
    jwt_expire_minutes: int = 720
    max_upload_mb: int = 10
    ai_base_url: str = "https://api.groq.com/openai/v1"
    ai_api_key: str = "gsk_ZEuUHxoKr2rc30GFRLsWWGdyb3FYUjZLHcFiZnnrEArGJDPGxfso0"
    ai_model: str = "llama-3.3-70b-versatile"
    ai_timeout_seconds: int = 45
    ncbi_tool: str = "MedNovaAI"
    ncbi_email: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()
