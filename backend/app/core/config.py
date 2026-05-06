from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    whisper_model: str = "base"
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()
