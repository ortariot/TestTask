from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Coordinate calculation"
    version: str = "0.0.1"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    is_dev: bool = True


settings = ApiConfig()
