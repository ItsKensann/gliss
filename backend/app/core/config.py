from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Optional now — the mock feedback provider doesn't need it. Required only
    # when feedback_provider="claude" (not implemented yet).
    anthropic_api_key: str = ""
    whisper_model: str = "base"
    host: str = "0.0.0.0"
    port: int = 8000
    # Which post-session coaching backend to use. "mock" returns heuristic-derived
    # feedback for free during development. Future values: "claude", "ollama".
    feedback_provider: str = "mock"

    class Config:
        env_file = ".env"


settings = Settings()
