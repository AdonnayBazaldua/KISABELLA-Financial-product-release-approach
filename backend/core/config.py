from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    database_url: str
    app_user_id: str = "00000000-0000-0000-0000-000000000001"
    banxico_token: str = ""
    tavily_api_key: str = ""
    secret_key: str = "dev-secret-change-in-production"


settings = Settings()
