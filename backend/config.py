"""
Configuration module for the Instagram Automation Tool.

All settings are loaded from environment variables with sensible defaults.
Copy .env.example to .env and fill in your credentials.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # ── FastAPI ──────────────────────────────────────────────
    APP_NAME: str = "ReelForge - Instagram Automation"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-to-a-random-secret")

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./reelforge.db")

    # ── File Uploads ─────────────────────────────────────────
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
    REEL_DURATION_SECONDS: int = int(os.getenv("REEL_DURATION_SECONDS", "30"))

    # ── Instagram / Facebook Graph API ───────────────────────
    FACEBOOK_APP_ID: str = os.getenv("FACEBOOK_APP_ID", "")
    FACEBOOK_APP_SECRET: str = os.getenv("FACEBOOK_APP_SECRET", "")
    FACEBOOK_REDIRECT_URI: str = os.getenv(
        "FACEBOOK_REDIRECT_URI", "http://localhost:8000/api/auth/instagram/callback"
    )
    INSTAGRAM_API_VERSION: str = os.getenv("INSTAGRAM_API_VERSION", "v22.0")
    INSTAGRAM_GRAPH_URL: str = "https://graph.facebook.com"

    # ── AI Caption Generation ────────────────────────────────
    # Supported providers: "openai", "anthropic", "ollama", "none"
    CAPTION_PROVIDER: str = os.getenv("CAPTION_PROVIDER", "openai")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # ── Scheduling ───────────────────────────────────────────
    SCHEDULER_DB_URL: str = os.getenv(
        "SCHEDULER_DB_URL", "sqlite:///./scheduler_jobs.db"
    )

    # ── CORS ─────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500"
    ).split(",")

    @property
    def instagram_api_base(self) -> str:
        return f"{self.INSTAGRAM_GRAPH_URL}/{self.INSTAGRAM_API_VERSION}"

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
