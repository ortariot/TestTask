from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Coordinate calculation"
    version: str = "0.0.1"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    is_dev: bool = True

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"  # noqa: S105
    postgres_db: str = "app_db"
    db_host: str = "localhost"
    db_port: int = 5432
    db_dsl: URL | None = None

    @model_validator(mode="after")
    def set_db_dsl(self):
        self.db_dsl = URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )

        return self


settings = ApiConfig()
