from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gitlab_secret: str
    gitlab_token: str
    gitlab_base_url: str = "https://gitlab.com/api/v4"
    # User id of the account the bot posts as. Without it the bot's own summary
    # comment retriggers the webhook.
    gitlab_bot_user_id: Optional[int] = None

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    app_env: str = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
