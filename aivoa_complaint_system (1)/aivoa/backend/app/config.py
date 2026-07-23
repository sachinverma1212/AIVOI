"""
Application configuration.
Reads values from environment variables (see .env.example).
"""
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Database ---
    # Works with Postgres or MySQL. Example values:
    #   postgresql+psycopg2://user:pass@localhost:5432/aivoa
    #   mysql+pymysql://user:pass@localhost:3306/aivoa
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./aivoa_dev.db"  # local fallback so the app boots with zero setup
    )

    # --- Groq / LLMs ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_EXTRACTION_MODEL: str = os.getenv("GROQ_EXTRACTION_MODEL", "gemma2-9b-it")
    GROQ_REASONING_MODEL: str = os.getenv("GROQ_REASONING_MODEL", "llama-3.3-70b-versatile")

    # --- App ---
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    MAX_UPLOAD_MB: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
