from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/applynow"

    # Auth
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Anthropic
    anthropic_api_key: str = ""

    # Job APIs
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jsearch_api_key: str = ""

    # Google Custom Search
    google_api_key: str = ""
    google_search_engine_id: str = ""

    # People Data Labs (people search for networking agent)
    pdl_api_key: str = ""

    # Exa.ai (neural web search for LinkedIn profile discovery)
    exa_api_key: str = ""

    # Email
    resend_api_key: str = ""
    resend_from_email: str = "noreply@apply-now-ai.com"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""

    # Storage
    upload_dir: str = "./uploads"

    # App
    frontend_url: str = "http://localhost:3000"
    environment: str = "development"

    # Plan limits
    free_jobs_per_month: int = 5
    free_contacts_per_month: int = 3


settings = Settings()
