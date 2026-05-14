from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Optional now — the mock feedback provider doesn't need it. Required only
    # when feedback_provider="claude" (not implemented yet).
    anthropic_api_key: str = ""
    whisper_model: str = "base"
    host: str = "0.0.0.0"
    port: int = 8000
    # Which post-session coaching backend to use. "mock" returns heuristic-derived
    # feedback for free during development. "ollama" calls a locally-hosted LLM
    # via the Ollama HTTP API; on any failure it falls back to mock internally.
    feedback_provider: str = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    class Config:
        env_file = ".env"


settings = Settings()
