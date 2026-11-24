from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"  # development | test | production
    database_url: str = "postgresql+psycopg://roanwick:roanwick_dev@localhost:5432/roanwick"
    jwt_secret: str = Field(default="dev-only-change-me-dev-only-change-me", min_length=32)
    access_token_minutes: int = 20
    refresh_token_days: int = 30
    cors_origins: str = "http://localhost:3000"
    public_web_url: str = "http://localhost:3000"

    # Payments: "sandbox" needs no credentials. "stripe" needs the keys below.
    payment_provider: str = "sandbox"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    sandbox_webhook_secret: str = "sandbox-webhook-secret-change-me"

    # Notifications: "console" records and logs only.
    email_provider: str = "console"  # console | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "Roanwick <hello@roanwick.example>"
    sms_provider: str = "console"  # console | twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""

    storage_dir: str = "./storage"
    max_upload_bytes: int = 5 * 1024 * 1024
    postcode_lookup: bool = False  # optional live validation via postcodes.io
    rate_limit_enabled: bool = True
    seed_admin_password: str = ""  # set explicitly to seed demo accounts

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and s.jwt_secret.startswith("dev-only"):
        raise RuntimeError("JWT_SECRET must be set to a strong random value in production")
    return s
