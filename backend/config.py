import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=False)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'email_sender_pro.db'}"

class Settings:
    app_name: str = "Email Sender Pro"
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    cors_origins: list[str] = [origin.strip() for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3001,http://127.0.0.1:3001",
    ).split(",") if origin.strip()]

settings = Settings()
