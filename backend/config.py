from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_DB_URL: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    SCRAPE_INTERVAL_MINUTES: int = 60

    @property
    def allowed_origins_list(self) -> list[str]:
        origins: list[str] = []
        for origin in self.ALLOWED_ORIGINS.split(","):
            candidate = origin.strip()
            if not candidate:
                continue
            if candidate.startswith(("http://", "https://")):
                origins.append(candidate)
            elif candidate.startswith("localhost"):
                origins.append(f"http://{candidate}")
            else:
                origins.append(f"https://{candidate}")
        return origins

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
