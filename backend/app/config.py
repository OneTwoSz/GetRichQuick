from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 1 week

    # Email (optional) — used for password-reset links. Gmail works free with
    # an app password (SMTP_HOST=smtp.gmail.com, SMTP_PORT=587). When unset,
    # reset links are written to the server log instead of emailed.
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None

    # Sessions (server-side, httpOnly cookie)
    SESSION_COOKIE: str = "gt_session"
    SESSION_IDLE_DAYS: int = 14     # signed out after this long unused
    SESSION_MAX_DAYS: int = 30      # signed out after this long regardless
    # None = secure cookies whenever PUBLIC_BASE_URL is https.
    COOKIE_SECURE: Optional[bool] = None

    # No-login links (buyer share, job-work, supplier data requests)
    SHARE_LINK_DAYS: int = 90
    JOBWORK_LINK_DAYS: int = 30
    JOBWORK_MAX_SUBMISSIONS: int = 5
    SUPPLIER_LINK_DAYS: int = 30
    SUPPLIER_MAX_SUBMISSIONS: int = 3

    # OCR
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_OCR_MODEL: str = "claude-sonnet-4-6"

    # Report signing
    REPORT_SIGNING_PROVIDER: str = "local"  # 'local' | 'kms'
    AWS_REGION: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_KMS_KEY_ID: Optional[str] = None

    # Public base URL (for verify links embedded in PDFs and passport QR
    # codes). On Render, RENDER_EXTERNAL_URL is used when this is left unset.
    PUBLIC_BASE_URL: Optional[str] = None
    RENDER_EXTERNAL_URL: Optional[str] = None

    # Generated reports directory. Defaults to /app/reports (the Docker path)
    # but can be overridden in dev to a path that exists on the host, e.g.
    # ./reports — set REPORTS_DIR in .env when running outside Docker.
    REPORTS_DIR: str = "/app/reports"

    # Hosted single-service mode: serve the built frontend from this
    # directory, and seed the demo factory when the database is empty
    # (hosts with ephemeral disks start fresh on every deploy).
    STATIC_DIR: Optional[str] = None
    # Uploaded product photos (served publicly at /api/media/<file>).
    MEDIA_DIR: str = "./media"
    DEMO_SEED: bool = False

    @model_validator(mode="after")
    def _resolve_public_base_url(self):
        if not self.PUBLIC_BASE_URL:
            self.PUBLIC_BASE_URL = self.RENDER_EXTERNAL_URL or "http://localhost:5173"
        return self

    class Config:
        env_file = ".env"
        # Tolerate env vars that the backend doesn't consume (BACKEND_PORT,
        # VITE_API_URL, POSTGRES_*) so the same .env can be shared across
        # backend, frontend, and docker-compose without booting failing.
        extra = "ignore"


settings = Settings()
