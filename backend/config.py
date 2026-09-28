"""CTQ application settings, loaded from backend/.env.

Never hard-code secrets: the Groq API key is read from the GROQ_API_KEY
environment variable (see .env.example).
"""
import os
from pathlib import Path

from pydantic_settings import BaseSettings

# backend/ directory (this file lives there)
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    # --- LLM (Groq) ---
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    llm_enabled: bool = True  # set false to run the rule engine only

    # --- Embeddings ---
    embedding_model: str = "all-MiniLM-L6-v2"

    # --- Matching pipeline ---
    top_k_trials: int = 0  # 0 = check ALL retrieved trials (no top-K cut)

    class Config:
        env_file = str(BACKEND_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def llm_available() -> bool:
    """True when Groq access is configured and enabled."""
    return bool(settings.groq_api_key) and settings.llm_enabled
