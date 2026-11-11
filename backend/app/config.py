import os


class Settings:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://member_admin:member_admin@localhost:5432/member_admin",
    )
    jwt_secret = os.getenv("JWT_SECRET", "dev-only-secret-change-me-dev-only-secret")
    access_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
    refresh_days = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    # day boundaries for date filters and daily reports (Myanmar = Asia/Yangon, Thailand = Asia/Bangkok)
    timezone = os.getenv("APP_TIMEZONE", "Asia/Yangon")
    export_max_rows = int(os.getenv("EXPORT_MAX_ROWS", "100000"))


settings = Settings()
