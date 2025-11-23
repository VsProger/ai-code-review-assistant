from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gitlab_secret: str
    gitlab_token: str
    gitlab_base_url: str = "https://gitlab.com/api/v4"

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    app_env: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"  # игнорировать лишние переменные в .env


settings = Settings()
