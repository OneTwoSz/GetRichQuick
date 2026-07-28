from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 1 week

    # Email (optional)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # OCR
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_OCR_MODEL: str = "claude-sonnet-4-6"

    # Report signing
    REPORT_SIGNING_PROVIDER: str = "local"  # 'local' | 'kms'
    AWS_REGION: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_KMS_KEY_ID: Optional[str] = None

    # Public base URL (for verify links embedded in PDFs)
    PUBLIC_BASE_URL: str = "http://localhost:5173"

    # Generated reports directory. Defaults to /app/reports (the Docker path)
    # but can be overridden in dev to a path that exists on the host, e.g.
    # ./reports — set REPORTS_DIR in .env when running outside Docker.
    REPORTS_DIR: str = "/app/reports"

    class Config:
        env_file = ".env"
        # Tolerate env vars that the backend doesn't consume (BACKEND_PORT,
        # VITE_API_URL, POSTGRES_*) so the same .env can be shared across
        # backend, frontend, and docker-compose without booting failing.
        extra = "ignore"


settings = Settings()
