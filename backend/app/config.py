import os

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root:123456@localhost:3306/sleep_manager"
    SECRET_KEY: str = "change-this-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080
    ALGORITHM: str = "HS256"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    # Production mode flag — set to True to disable docs and enable stricter CORS
    PRODUCTION: bool = False

    class Config:
        env_file = ".env"


settings = Settings()

# Warn if using default secret key in non-dev context
if settings.SECRET_KEY == "change-this-in-production" and settings.PRODUCTION:
    import warnings
    warnings.warn("SECRET_KEY is still using the default value! Set it in .env for production.")
