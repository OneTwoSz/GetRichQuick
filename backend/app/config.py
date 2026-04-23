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

    class Config:
        env_file = ".env"


settings = Settings()
