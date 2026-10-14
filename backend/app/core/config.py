
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Real-Time Multiplayer Drawing & Guessing Game"
    APP_ENV: str = "development"
    DEBUG: bool = True

    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str

    CORS_ORIGINS: str = "http://localhost:5173"

    DEFAULT_TOTAL_ROUNDS: int = 3
    ROUND_DURATION_SECONDS: int = 80
    MIN_PLAYERS: int = 2
    MAX_PLAYERS: int = 8

    # JWT authentication
    SECRET_KEY: str = "replace-this-with-a-long-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
