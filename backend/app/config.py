from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = Path("data")
    max_upload_mb: int = 20
    max_pages: int = 500
    cors_origins: list[str] = ["http://localhost:5173"]
    # When set, the API also serves the built React app from this folder.
    web_dist_dir: Path | None = None

    # Chat model: any OpenAI-compatible API (OpenAI, Groq, Gemini, OpenRouter, Ollama, ...).
    llm_provider: Literal["openai", "extractive"] = "openai"
    llm_base_url: str | None = None  # e.g. https://api.groq.com/openai/v1
    llm_api_key: str | None = None
    llm_model: str = "gpt-5-mini"
    # Left unset by default: some models (e.g. the GPT-5 family) only accept their default temperature.
    llm_temperature: float | None = None

    # Embeddings: "local" runs on CPU for free, "openai" uses an OpenAI-compatible endpoint,
    # "hash" is a deterministic stand-in used by the test suite (no semantic meaning).
    embedding_provider: Literal["local", "openai", "hash"] = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None

    # Retrieval
    chunk_size: int = 900
    chunk_overlap: int = 150
    top_k: int = 6

    @property
    def db_path(self) -> Path:
        return self.data_dir / "docmind.sqlite3"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
